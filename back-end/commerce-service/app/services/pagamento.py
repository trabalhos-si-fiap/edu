"""Serviço de formas de pagamento. Porte de
`legacy/app/modules/payment_methods/services.py` (task B9).

Nomes de função em português (`listar_metodos`, `obter_metodo`,
`criar_metodo`, `definir_padrao`, `apagar_metodo`) — mesmo critério de
B6/B7/B8 (`listar_produtos`, `criar_review`, `obter_carrinho`,
`adicionar_item`): a seção "Interfaces" do brief especifica os nomes em
português mesmo o legacy usando inglês (correção 3 do CONTEXTO DO
CONTROLADOR do brief B9, ratificando o precedente da B8).

Read→write sem lock (regra 3 do CLAUDE.md) — MEDIDO e CORRIGIDO na rodada
de correção 1, não mais um achado só registrado. O legacy não tem lock
nenhum aqui (`grep -rn "with_for_update|FOR UPDATE"
legacy/app/modules/payment_methods/` não acha nada — comando re-confirmado
no task-B9-report.md), e a task B9 original replicou isso por instrução do
brief. Um revisor independente mediu, depois disso, que a corrida produz
DOIS defaults simultâneos de verdade (não é hipotético): duas transações
concorrentes veem `existing=[]`/`remaining` desatualizado e as duas decidem
"eu sou o default". Decisão do usuário de 2026-08-07: pôr o lock — a regra
3 do CLAUDE.md é inviolável, e o lock não muda o contrato HTTP (ver
task-B9-report.md, seção "Divergência do lock").

Dois mecanismos, não um só, porque são DUAS classes de corrida diferentes
(mesma dualidade de `app/services/carrinho.py`, B8):

1. `criar_metodo`/`apagar_metodo`/`definir_padrao` fazem `.with_for_update()`
   nas linhas EXISTENTES do usuário antes de decidir quem é o default —
   serializa corridas quando já existe pelo menos 1 linha (ex.: DELETE do
   default concorrente com POST de um novo default). `definir_padrao` entrou
   nesta lista na rodada de correção 2 (ver o fim desta docstring).
2. Quando NÃO existe nenhuma linha ainda (a corrida mais dura: dois
   `criar_metodo` concorrentes, usuário zerado), não há o que
   `with_for_update()` travar — o Postgres nunca bloqueia um INSERT novo por
   causa de lock em linha inexistente. Esse caso é fechado pelo índice único
   PARCIAL `ix_payment_methods_one_default_per_user` (`app/models/pagamento.py`)
   — igual em espírito ao `carts.user_id UNIQUE` que já protege
   `get_or_create_cart` em `carrinho.py`: o segundo INSERT concorrente que
   tentaria violar o índice bloqueia esperando o primeiro, e falha com
   `IntegrityError` depois — capturado abaixo e refeito sem `is_default`.

Achado da prova por mutação ISOLADA de cada mecanismo (task-B9-report.md,
20 execuções por combinação): removendo só o índice (`with_for_update`
mantido), a corrida de POST/POST sem nenhuma linha VOLTA (20/20 vermelho) —
`with_for_update` sozinho não basta. Removendo só o `with_for_update` (índice
mantido), as DUAS corridas continuam protegidas (20/20 verde nas duas) — o
índice, combinado com o catch de `IntegrityError` em `criar_metodo` e a
guarda `not remaining[0].is_default` em `apagar_metodo`, já é suficiente
sozinho PARA AQUELAS DUAS CORRIDAS. Mantido `with_for_update` mesmo assim —
decisão explícita do usuário ("PÔR O LOCK"), consistente com o idioma já
usado em `carrinho.py`, e ele reduz quantas vezes uma corrida precisa cair
no caminho de retry via `IntegrityError` em vez de serializar antes de
chegar lá.

RODADA DE CORREÇÃO 2 — o parágrafo acima NÃO se generaliza, e a medição que
o derrubou está aqui: existe uma TERCEIRA corrida, em `definir_padrao`
(PATCH), na qual o índice sozinho não só é insuficiente como é a CAUSA do
dano. Dois PATCH concorrentes com ≥3 métodos e os DOIS alvos não-default
faziam o segundo estourar `UniqueViolationError` no commit e devolver 500
(medido: `(200, 500)` em 19/20 rodadas; a rota nunca tinha sido tocada pela
rodada 1). O conserto é o mesmo `_listar_metodos_com_lock` — aqui o
`with_for_update` é ESTRITAMENTE necessário: removendo só ele (índice
mantido), o teste de regressão dá 20/20 vermelho. Ver task-B9-report.md,
"RODADA DE CORREÇÃO 2".
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import PaymentMethodNotFoundError
from app.models.pagamento import PaymentMethod
from app.schemas.pagamento import PaymentMethodIn, PaymentMethodPatch


async def listar_metodos(db: AsyncSession, user_id: uuid.UUID) -> list[PaymentMethod]:
    stmt = (
        select(PaymentMethod)
        .where(PaymentMethod.user_id == user_id)
        .order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _listar_metodos_com_lock(db: AsyncSession, user_id: uuid.UUID) -> list[PaymentMethod]:
    """Mesma consulta de `listar_metodos`, com `.with_for_update()` — trava
    as linhas EXISTENTES do usuário antes de
    `criar_metodo`/`apagar_metodo`/`definir_padrao` decidirem quem é o
    default (regra 3 do CLAUDE.md). Só serializa quando
    já existe pelo menos 1 linha; ver docstring do módulo para o caso de
    zero linhas (fechado pelo índice único parcial, não por este lock)."""
    stmt = (
        select(PaymentMethod)
        .where(PaymentMethod.user_id == user_id)
        .order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at)
        .with_for_update()
    )
    return list((await db.execute(stmt)).scalars().all())


async def obter_metodo(db: AsyncSession, user_id: uuid.UUID, method_id: uuid.UUID) -> PaymentMethod:
    stmt = select(PaymentMethod).where(
        PaymentMethod.id == method_id, PaymentMethod.user_id == user_id
    )
    method = (await db.execute(stmt)).scalar_one_or_none()
    if method is None:
        raise PaymentMethodNotFoundError()
    return method


async def _limpar_outros_padroes(
    db: AsyncSession, user_id: uuid.UUID, manter_id: uuid.UUID | None
) -> None:
    stmt = (
        update(PaymentMethod)
        .where(PaymentMethod.user_id == user_id, PaymentMethod.is_default.is_(True))
        .values(is_default=False)
    )
    if manter_id is not None:
        stmt = stmt.where(PaymentMethod.id != manter_id)
    await db.execute(stmt)


async def criar_metodo(
    db: AsyncSession, user_id: uuid.UUID, data: PaymentMethodIn
) -> PaymentMethod:
    method = PaymentMethod(
        user_id=user_id, type=data.type.value, **data.model_dump(exclude={"type"})
    )

    # Lock nas linhas EXISTENTES do usuário antes de decidir se este método
    # é o primeiro/deve ser default — serializa com `apagar_metodo`
    # concorrente quando já existe pelo menos 1 linha (regra 3 do CLAUDE.md;
    # mesma técnica de `app/services/carrinho.py`, B8).
    existing = await _listar_metodos_com_lock(db, user_id)
    if not existing:
        method.is_default = True

    if method.is_default:
        await _limpar_outros_padroes(db, user_id, manter_id=None)

    db.add(method)
    try:
        await db.commit()
    except IntegrityError:
        # Corrida do caso SEM nenhuma linha existente: dois `criar_metodo`
        # concorrentes do mesmo usuário zerado não têm nada para o lock
        # acima travar (Postgres não bloqueia um INSERT novo por causa de
        # lock em linha inexistente) — os dois decidem "eu sou o default" e
        # o segundo a commitar esbarra em
        # `ix_payment_methods_one_default_per_user` (índice único parcial).
        # O primeiro já ganhou o default; este vira não-default e é
        # reinserido — mesmo padrão de `get_or_create_cart` (B8), que
        # captura `IntegrityError` do `UNIQUE(carts.user_id)`.
        await db.rollback()
        method = PaymentMethod(
            user_id=user_id,
            type=data.type.value,
            **{**data.model_dump(exclude={"type", "is_default"}), "is_default": False},
        )
        db.add(method)
        await db.commit()
    await db.refresh(method)
    return method


async def definir_padrao(
    db: AsyncSession,
    user_id: uuid.UUID,
    method_id: uuid.UUID,
    patch: PaymentMethodPatch,
) -> PaymentMethod:
    method = await obter_metodo(db, user_id, method_id)
    if patch.is_default is True:
        # Mesmo lock de `criar_metodo`/`apagar_metodo` — acrescentado na
        # rodada de correção 2. Sem ele, dois PATCH concorrentes do mesmo
        # usuário (≥3 métodos, os DOIS alvos não-default) esbarravam no
        # índice `ix_payment_methods_one_default_per_user` e o segundo
        # devolvia 500: medido em 19/20 rodadas `(200, 500)` com
        # `IntegrityError`/`UniqueViolationError` no `db.commit()` abaixo
        # (ver task-B9-report.md, "RODADA DE CORREÇÃO 2").
        #
        # POR QUE o lock resolve, medido e não suposto: sem ele, o
        # `_limpar_outros_padroes` do segundo PATCH já tinha começado (e
        # bloqueado na linha do default antigo) ANTES do primeiro commitar,
        # então sua snapshot READ COMMITTED não enxergava o novo default do
        # vencedor e não o limpava — restavam dois `is_default=true`, que é
        # exatamente o que o índice proíbe. Com o lock, o segundo PATCH
        # espera AQUI; seu `_limpar_outros_padroes` só começa depois do
        # commit do primeiro, tira uma snapshot nova, enxerga o default
        # recém-criado e o limpa. Resultado: último a commitar vence, sempre
        # exatamente 1 default (20/20 medido).
        #
        # O retorno é descartado de propósito: aqui só interessa o efeito
        # colateral do `FOR UPDATE` (a decisão de quem é o default sai de
        # `_limpar_outros_padroes`, não da lista). É o único uso da função
        # que ignora o resultado.
        await _listar_metodos_com_lock(db, user_id)
        await _limpar_outros_padroes(db, user_id, manter_id=method.id)
        method.is_default = True
    elif patch.is_default is False:
        method.is_default = False
    await db.commit()
    await db.refresh(method)
    return method


async def apagar_metodo(db: AsyncSession, user_id: uuid.UUID, method_id: uuid.UUID) -> None:
    method = await obter_metodo(db, user_id, method_id)
    era_padrao = method.is_default
    await db.delete(method)
    await db.flush()

    # Lock nas linhas restantes do usuário antes de escolher quem promover —
    # serializa com `criar_metodo` concorrente (regra 3 do CLAUDE.md; mesma
    # técnica de `app/services/carrinho.py`, B8). Promove o mais antigo
    # remanescente a default, para o usuário sempre ter um método padrão.
    if era_padrao:
        remaining = await _listar_metodos_com_lock(db, user_id)
        if remaining and not remaining[0].is_default:
            remaining[0].is_default = True
    await db.commit()
