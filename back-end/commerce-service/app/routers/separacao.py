from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import requer_papel
from app.events.publisher import publish_event
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Pedido, PedidoStatusHistorico
from app.schemas.pedido import PedidoFilaOut, PedidoOut
from app.services.priorizacao_fila import priorizar_fila
from app.services.status_pedido import StatusPedido, validar_transicao

router = APIRouter(prefix="/picking", tags=["picking"])


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
    """
    result = await db.execute(
        select(Pedido).where(Pedido.status == StatusPedido.AGUARDANDO_SEPARACAO.value)
    )
    pedidos = result.scalars().all()

    pedidos_pontuados = await priorizar_fila(db, list(pedidos))
    pagina = pedidos_pontuados[offset : offset + limit]

    return [
        PedidoFilaOut(**PedidoOut.model_validate(pedido).model_dump(), score_risco=score)
        for pedido, score in pagina
    ]


@router.patch("/{pedido_id}/start", response_model=PedidoOut)
async def iniciar_separacao(
    pedido_id: int,
    user: dict = Depends(requer_papel("separador")),
    db: AsyncSession = Depends(get_db),
):
    """
    Claim-on-first-action: o primeiro separador a chamar esta rota vira o
    `separador_id` do pedido, sem checar posse prévia — não há posse prévia
    a checar, é exatamente o ato de reivindicar o pedido. A máquina de
    estados protege contra uma segunda reivindicação (só
    AGUARDANDO_SEPARACAO -> EM_SEPARACAO é uma transição válida; uma
    segunda chamada, de outro separador, encontra o pedido já em
    EM_SEPARACAO e `validar_transicao` rejeita com 400). Mesmo desenho de
    `confirmar_coleta` em entrega.py — ver a nota lá para o raciocínio
    completo.
    """
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    pedido.separador_id = user["sub"]
    await db.flush()

    return await transicionar_pedido(db, pedido_id, StatusPedido.EM_SEPARACAO.value, user["sub"])


@router.patch("/{pedido_id}/finish", response_model=PedidoOut)
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
