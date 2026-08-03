from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import requer_papel
from app.events.publisher import publish_event
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Pedido, PedidoStatusHistorico
from app.schemas.pedido import PedidoFilaOut, PedidoStaffOut
from app.services.priorizacao_fila import priorizar_fila
from app.services.status_pedido import StatusPedido, validar_transicao

router = APIRouter(prefix="/picking", tags=["picking"])

# Bound do fetch de candidatos da fila (fix round 1, reviewer finding #5):
# antes, a query buscava TODOS os pedidos AGUARDANDO_SEPARACAO, sem teto —
# a paginação (limit/offset) só corta a resposta DEPOIS de pontuar/ordenar
# (ver docstring de fila_separacao), então não limitava o que o banco
# devolvia. Busca-se aqui as CANDIDATOS_FILA_MAXIMO ordens mais antigas
# (`criado_em ASC`) — o componente de espera pesa 0.6 contra 0.4 do risco
# de estoque em priorizacao_fila.py, então qualquer pedido com espera
# normalizada >= 0.4/0.6 (~32h) já pontua tanto quanto o teto máximo
# possível só por risco (0.4, pedido novíssimo com risco=1); a pré-seleção
# pelas mais antigas preserva o ranking na prática sem reintroduzir um
# fetch sem teto. Não é uma garantia matemática absoluta em filas com mais
# de CANDIDATOS_FILA_MAXIMO pedidos pendentes simultaneamente (ver
# task-11-report.md, Fix round 1, item 5).
CANDIDATOS_FILA_MAXIMO = 500


async def transicionar_pedido(
    db: AsyncSession,
    pedido_id: int,
    novo_status: str,
    user_id: str | None,
    observacao: str | None = None,
) -> Pedido:
    """
    Função central de transição de estado do pedido — reutilizada pelos
    routers de separação, entrega e admin, para garantir que toda mudança
    de status passe pela mesma validação e publique o mesmo evento.
    """
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    if not validar_transicao(pedido.status, novo_status):
        raise HTTPException(400, f"Transição inválida: {pedido.status} → {novo_status}")

    pedido.status = novo_status
    db.add(
        PedidoStatusHistorico(
            pedido_id=pedido.id,
            status=novo_status,
            user_id=user_id,
            observacao=observacao,
        )
    )
    await db.commit()
    await db.refresh(pedido)

    await publish_event(
        "order.status_changed",
        {
            "pedido_id": pedido.id,
            "aluno_id": str(pedido.aluno_id),
            "status": novo_status,
        },
    )
    return pedido


@router.get("/queue", response_model=list[PedidoFilaOut])
async def fila_separacao(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(requer_papel("separador", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Fila ordenada por risco (não FIFO) — prioriza pedidos que já esperam
    há mais tempo E pedidos com itens em risco de faltar no estoque, para
    separar esses antes que a falta vire uma ocorrência de verdade. Ver
    services/priorizacao_fila.py para o desenho do score.

    A paginação é aplicada em Python, DEPOIS de pontuar e ordenar por
    risco — não em SQL, como as demais listagens do serviço. Um
    `.limit()/.offset()` em SQL antes de `priorizar_fila` cortaria o
    conjunto de candidatos antes do score ser calculado, corrompendo o
    ranking (um pedido de alta prioridade poderia cair fora da primeira
    página só por não estar entre os N primeiros por `id`). O corte por
    página só pode acontecer depois que TODOS os candidatos elegíveis já
    foram pontuados e ordenados.

    O FETCH em si é limitado a `CANDIDATOS_FILA_MAXIMO` (os mais antigos
    por `criado_em`) — ver comentário da constante no topo do módulo para
    o porquê disso preservar o ranking na prática.
    """
    result = await db.execute(
        select(Pedido)
        .where(Pedido.status == StatusPedido.AGUARDANDO_SEPARACAO.value)
        .order_by(Pedido.criado_em.asc(), Pedido.id.asc())
        .limit(CANDIDATOS_FILA_MAXIMO)
    )
    pedidos = result.scalars().all()

    pedidos_pontuados = await priorizar_fila(db, list(pedidos))
    pagina = pedidos_pontuados[offset : offset + limit]

    return [
        PedidoFilaOut(**PedidoStaffOut.model_validate(pedido).model_dump(), score_risco=score)
        for pedido, score in pagina
    ]


@router.patch("/{pedido_id}/start", response_model=PedidoStaffOut)
async def iniciar_separacao(
    pedido_id: int,
    user: dict = Depends(requer_papel("separador")),
    db: AsyncSession = Depends(get_db),
):
    """
    Claim-on-first-action, COM uma exceção — corrigido no fix round 1
    (reviewer finding #2): a premissa original de que "não há posse prévia
    a checar" era falsa. `admin.py`'s `assign-picker` já pode setar
    `separador_id` SEM mudar o status do pedido — um admin pode atribuir o
    pedido X ao separador P1 enquanto ele ainda está em CRIADO/
    AGUARDANDO_SEPARACAO. Sem honrar essa atribuição, quando o pedido
    chegasse em AGUARDANDO_SEPARACAO, QUALQUER OUTRO separador P2 chamando
    `/start` sobrescreveria `separador_id` para si (a transição continua
    válida do ponto de vista da máquina de estados) e sequestraria o
    pedido de P1 silenciosamente — e o gap #3 fix em `finish` passaria a
    proteger o sequestrador, não P1. Por isso: se `separador_id` já está
    definido E é de outra pessoa, rejeita. Se está vazio (ninguém
    atribuiu) ou já é do próprio chamador (idempotente), segue o
    claim-on-first-action normal.

    A proteção contra DUAS chamadas concorrentes de `/start` no mesmo
    pedido (não sequencial — corrida de verdade) é o `.with_for_update()`
    abaixo: sem lock, duas transações sob READ COMMITTED podem ler o
    mesmo `separador_id`/status, ambas passarem nas checagens acima e
    ambas commitarem — CLAUDE.md regra 3 (fix round 1, reviewer finding
    #3). O `.with_for_update()` serializa a segunda transação atrás da
    primeira: ela só lê a linha depois que a primeira commita (ou
    reverte), e nesse ponto vê o `separador_id` já preenchido.
    """
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id).with_for_update())
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    if pedido.separador_id is not None and str(pedido.separador_id) != user["sub"]:
        raise HTTPException(403, "Este pedido já foi atribuído a outro separador")

    pedido.separador_id = user["sub"]
    await db.flush()

    return await transicionar_pedido(db, pedido_id, StatusPedido.EM_SEPARACAO.value, user["sub"])


@router.patch("/{pedido_id}/finish", response_model=PedidoStaffOut)
async def finalizar_separacao(
    pedido_id: int,
    user: dict = Depends(requer_papel("separador")),
    db: AsyncSession = Depends(get_db),
):
    """
    Fix do gap de autorização #3 do sweep de segurança: a rota original
    checava só o papel ("separador"), nunca se o chamador era o
    `separador_id` do pedido — qualquer separador podia finalizar a
    separação de um pedido reivindicado por outro. A checagem de posse
    roda ANTES de qualquer outra validação de negócio (ocorrência aberta),
    para não vazar estado do pedido a quem não tem relação com ele.
    """
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    if str(pedido.separador_id) != user["sub"]:
        raise HTTPException(403, "Apenas o separador responsável por este pedido pode finalizá-lo")

    ocorrencia_result = await db.execute(
        select(Ocorrencia).where(Ocorrencia.pedido_id == pedido_id, Ocorrencia.status == "ABERTA")
    )
    if ocorrencia_result.scalar_one_or_none():
        raise HTTPException(
            400,
            "Existe uma ocorrência aberta aguardando decisão do aluno. "
            "Aguarde a resolução antes de finalizar a separação.",
        )

    await transicionar_pedido(db, pedido_id, StatusPedido.SEPARADO.value, user["sub"])
    # Encadeia automaticamente para "aguardando coleta" — pronto para o entregador
    return await transicionar_pedido(
        db, pedido_id, StatusPedido.AGUARDANDO_COLETA.value, user["sub"]
    )
