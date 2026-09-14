"""Carregamento: o lote de pedidos que sai junto, de uma origem, por uma
transportadora — e a credencial com que o entregador o acessa.

A senha existe em claro em exatamente DOIS lugares e por um instante só: o
retorno de `criar_carregamento` e o payload de `shipment.created`. Nada aqui a
loga, e nenhuma leitura posterior a devolve.
"""

import hmac
import secrets
import uuid
from datetime import UTC, datetime

from edu_common.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    CarregamentoNotFoundError,
    CarregamentoOrigemDivergenteError,
    CredencialCarregamentoInvalidaError,
    OrderNotFoundError,
    PedidoJaCarregadoError,
    TransportadoraNotFoundError,
)
from app.models.carregamento import Carregamento
from app.models.pedido import Order
from app.models.transportadora import Carrier, CarrierStatus

# Sem I, O, 0 e 1: o código é ditado por telefone e digitado por quem está com
# a carga na mão. Ambiguidade visual aqui vira uma tentativa de login perdida.
ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_CODIGO = 8
TAMANHO_SENHA = 12

# Quantas vezes tentar um código novo diante de colisão. Com 32^8 (~1.1e12)
# combinações e dezenas de lotes, três tentativas é folga absurda; o laço
# existe para o caso patológico, não para o caso normal.
TENTATIVAS_CODIGO = 3


def gerar_codigo() -> str:
    return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(TAMANHO_CODIGO))


def gerar_senha() -> str:
    """`secrets`, nunca `random`: `random` é um Mersenne Twister previsível a
    partir de saídas anteriores, e isto é credencial."""
    return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(TAMANHO_SENHA))


async def criar_carregamento(
    db: AsyncSession, *, transportadora_id: int, criado_por: uuid.UUID
) -> tuple[Carregamento, str]:
    """Cria o lote e devolve `(carregamento, senha_em_claro)`.

    A colisão de `codigo` é detectada pelo ÍNDICE ÚNICO, não por um SELECT
    prévio: SELECT-depois-INSERT é uma corrida, e o índice é a única coisa que
    resolve duas criações simultâneas. Mesmo idioma de
    `services/produtos.py::criar_produto` com `sku`.
    """
    carrier = await db.get(Carrier, transportadora_id)
    if carrier is None:
        raise TransportadoraNotFoundError()

    senha = gerar_senha()
    senha_hash = hash_password(senha)

    for tentativa in range(TENTATIVAS_CODIGO):
        carregamento = Carregamento(
            transportadora_id=carrier.id,
            codigo=gerar_codigo(),
            senha_hash=senha_hash,
            criado_por=criado_por,
        )
        db.add(carregamento)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            if tentativa == TENTATIVAS_CODIGO - 1:
                raise
            continue
        await db.refresh(carregamento)
        return carregamento, senha

    raise RuntimeError("inalcançável: o laço acima só sai por return ou raise")


# ── Frota própria ──────────────────────────────────────────────────────────
#
# A coleta de um pedido SEM carregamento (o caminho da demonstração: ninguém
# cadastrou transportadora nem montou lote) anexa o pedido a um carregamento
# criado na hora, de uma transportadora interna única. Sem isso
# `congelar_destino` e o simulador de posição ignoram o pedido — os dois
# precisam da origem de um carregamento — e o mapa do aluno nunca mostra o
# entregador.

NOME_FROTA_PROPRIA = "Frota própria Edu"
LOCAL_FROTA_PROPRIA = "Operação própria"
# `.invalid` é TLD reservado (RFC 2606): nunca resolve, então nenhum envio
# futuro para "a transportadora" desta frota chega a caixa de ninguém. E
# nenhum sai hoje: `shipment.created` não é publicado para estes lotes.
EMAIL_FROTA_PROPRIA = "frota-propria@edu.invalid"

# `criado_por` é NOT NULL e não há pessoa quando a rede de segurança coleta.
# O UUID nulo (RFC 9562, "Nil UUID") é o valor que nenhum id de conta desta
# frota assume — o auth-users gera v7/v4 — e por isso não se passa por
# ninguém. `CarregamentoOut` não expõe a coluna.
CRIADO_PELO_SISTEMA = uuid.UUID(int=0)

# Chave de `pg_advisory_xact_lock` que serializa o get-or-create da frota.
# `carriers.name` não é único, e duas primeiras coletas simultâneas criariam
# duas "Frota própria Edu". O lock é da TRANSAÇÃO: solta sozinho no commit ou
# rollback da coleta, sem `finally`. Número arbitrário, fixo, sem outro uso.
_TRAVA_FROTA_PROPRIA = 7_391_004_512


async def obter_frota_propria(db: AsyncSession) -> Carrier:
    """A transportadora interna, criada na primeira vez — sem seed. Não comita."""
    await db.execute(select(func.pg_advisory_xact_lock(_TRAVA_FROTA_PROPRIA)))
    frota = (
        (
            await db.execute(
                select(Carrier)
                .where(Carrier.name == NOME_FROTA_PROPRIA)
                .order_by(Carrier.id)
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if frota is None:
        frota = Carrier(
            name=NOME_FROTA_PROPRIA,
            location=LOCAL_FROTA_PROPRIA,
            email=EMAIL_FROTA_PROPRIA,
            status=CarrierStatus.ACTIVE.value,
        )
        db.add(frota)
        await db.flush()
    return frota


async def anexar_a_frota_propria(
    db: AsyncSession, pedido: Order, *, criado_por: uuid.UUID
) -> Carregamento:
    """Cria o carregamento da frota própria para `pedido` e o anexa. NÃO comita.

    Quem chama JÁ SEGURA `with_for_update()` no pedido e comita junto com a
    transição para EM_TRANSITO (regra 3 do CLAUDE.md): uma segunda coleta
    concorrente espera o lock, relê o pedido com `carregamento_id` preenchido
    e não cria outro lote; uma coleta recusada depois daqui desfaz o lote
    junto com o resto da transação.

    Origem copiada de `orders.origem_*`, como `atribuir_pedido` faz com o
    primeiro pedido de um lote. `aberto_em` agora: é o que o login do
    entregador grava num lote do admin, e aqui a coleta É a retirada da
    carga.

    A senha é sorteada e descartada. `senha_hash` é NOT NULL, e um hash que
    não fosse bcrypt faria `verify_password` estourar num login com este
    código; um hash de verdade de um segredo que ninguém recebe faz esse login
    responder 401 como qualquer senha errada. Ninguém usa credencial de lote
    aqui — quem coleta já está autenticado (entregador) ou é o sistema.
    """
    frota = await obter_frota_propria(db)
    senha_hash = hash_password(gerar_senha())

    for tentativa in range(TENTATIVAS_CODIGO):
        carregamento = Carregamento(
            transportadora_id=frota.id,
            codigo=gerar_codigo(),
            senha_hash=senha_hash,
            criado_por=criado_por,
            origem_rotulo=pedido.origem_rotulo or "",
            origem_lat=pedido.origem_lat,
            origem_lng=pedido.origem_lng,
            aberto_em=datetime.now(UTC),
        )
        # SAVEPOINT, não `rollback()` como em `criar_carregamento`: a
        # transação de fora já tem o lock do pedido e `deliverer_id`. Uma
        # colisão de código desfaz só o INSERT do lote.
        try:
            async with db.begin_nested():
                db.add(carregamento)
                await db.flush()
        except IntegrityError:
            if tentativa == TENTATIVAS_CODIGO - 1:
                raise
            continue
        break

    pedido.carregamento_id = carregamento.id
    pedido.carrier_name = frota.name
    return carregamento


async def atribuir_pedido(db: AsyncSession, *, carregamento_id: int, pedido_id: uuid.UUID) -> Order:
    """Põe o pedido no lote, congelando a origem do lote no primeiro pedido.

    `with_for_update()` nos dois (regra 3 do CLAUDE.md): sem ele, duas
    atribuições concorrentes leem o mesmo `origem_*` vazio, as duas congelam
    origens diferentes e a última vence — o lote passaria a alegar uma origem
    que não é a de todos os seus pedidos.
    """
    carregamento = (
        await db.execute(
            select(Carregamento).where(Carregamento.id == carregamento_id).with_for_update()
        )
    ).scalar_one_or_none()
    if carregamento is None:
        raise CarregamentoNotFoundError()

    pedido = (
        await db.execute(select(Order).where(Order.id == pedido_id).with_for_update())
    ).scalar_one_or_none()
    if pedido is None:
        raise OrderNotFoundError()

    if pedido.carregamento_id is not None and pedido.carregamento_id != carregamento.id:
        raise PedidoJaCarregadoError()

    # A sentinela de "origem ainda não congelada" é "este lote já tem algum
    # pedido?", não "o rótulo está vazio?". `orders.origem_rotulo` é
    # NULLABLE — checkout sem fornecedor resolvido deixa `origem_*` como
    # None (`app/services/pedidos.py`) — então um primeiro pedido de origem
    # nula fazia `origem_rotulo or ""` continuar vazio e o congelamento
    # nunca "pegava": um SEGUNDO pedido, de origem real, caía no mesmo ramo
    # "ainda não congelado" e sobrescrevia a origem do lote em silêncio, sem
    # 409 nenhum. Um lote de pedidos sem origem é um lote coerente — o
    # simulador de posição (task 6) e o rastreio degradam para posição
    # nula — só não pode se misturar com um lote de origem real, e é essa
    # mistura que a query abaixo, e não a string, detecta.
    ja_tem_pedido = (
        await db.execute(select(Order.id).where(Order.carregamento_id == carregamento.id).limit(1))
    ).scalar_one_or_none()

    if ja_tem_pedido is None:
        carregamento.origem_rotulo = pedido.origem_rotulo or ""
        carregamento.origem_lat = pedido.origem_lat
        carregamento.origem_lng = pedido.origem_lng
    elif (carregamento.origem_lat, carregamento.origem_lng) != (
        pedido.origem_lat,
        pedido.origem_lng,
    ):
        raise CarregamentoOrigemDivergenteError()

    carrier = await db.get(Carrier, carregamento.transportadora_id)
    pedido.carregamento_id = carregamento.id
    # O rastreio do aluno mostra este nome a partir da task 6 (D12) — antes
    # dela ele mostrava uma constante para todo pedido do sistema.
    pedido.carrier_name = carrier.name if carrier else pedido.carrier_name

    await db.commit()
    await db.refresh(pedido)
    return pedido


async def listar_carregamentos(
    db: AsyncSession, *, limit: int, offset: int
) -> tuple[list[Carregamento], int]:
    itens = (
        (
            await db.execute(
                select(Carregamento)
                .order_by(Carregamento.criado_em.desc(), Carregamento.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    total = (await db.execute(select(func.count()).select_from(Carregamento))).scalar_one()
    return list(itens), total


async def buscar_carregamento(db: AsyncSession, carregamento_id: int) -> Carregamento:
    carregamento = await db.get(Carregamento, carregamento_id)
    if carregamento is None:
        raise CarregamentoNotFoundError()
    return carregamento


async def autenticar_carregamento(
    db: AsyncSession, *, codigo: str, senha: str, nome: str, contato: str
) -> Carregamento:
    """Valida a credencial e registra quem pegou a carga no primeiro acesso.

    O SELECT é por código exato. A comparação com `hmac.compare_digest` logo
    abaixo parece redundante depois de um `WHERE codigo = :codigo` — e é, para
    o resultado; ela está lá porque a regra 9 do CLAUDE.md pede comparação em
    tempo constante de segredo, e porque uma reescrita futura que troque o
    filtro por uma busca case-insensitive ou por prefixo herdaria a proteção
    em vez de perdê-la em silêncio.
    """
    carregamento = (
        await db.execute(
            select(Carregamento).where(Carregamento.codigo == codigo).with_for_update()
        )
    ).scalar_one_or_none()

    if carregamento is None or not hmac.compare_digest(carregamento.codigo, codigo):
        # Gasta um bcrypt do MESMO custo antes de recusar: sem isto, um código
        # inexistente responderia em microssegundos e um código válido com
        # senha errada em ~100 ms, o que basta para enumerar lotes.
        verify_password(senha, DUMMY_PASSWORD_HASH)
        raise CredencialCarregamentoInvalidaError()

    if not verify_password(senha, carregamento.senha_hash):
        raise CredencialCarregamentoInvalidaError()

    if carregamento.aberto_em is None:
        carregamento.entregador_nome = nome
        carregamento.entregador_contato = contato
        carregamento.aberto_em = datetime.now(UTC)
        await db.commit()
        await db.refresh(carregamento)

    return carregamento


async def pedidos_do_carregamento(
    db: AsyncSession, *, carregamento_id: int, limit: int, offset: int
) -> list[Order]:
    resultado = await db.execute(
        select(Order)
        .where(Order.carregamento_id == carregamento_id)
        .order_by(Order.created_at.asc(), Order.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(resultado.scalars().all())
