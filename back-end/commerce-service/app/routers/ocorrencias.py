from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_student_id, requer_papel
from app.events.publisher import publish_event
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Pedido, PedidoItem, PedidoStatusHistorico
from app.models.produto import Produto
from app.schemas.ocorrencia import (
    AtrasoEntregaIn,
    FaltaEstoqueIn,
    OcorrenciaDetalheOut,
    OcorrenciaOut,
    ProdutoSugeridoOut,
    ResolverOcorrenciaIn,
)
from app.services.status_pedido import StatusPedido, validar_transicao
from app.services.substituicao_ia import sugerir_substitutos

router = APIRouter(prefix="/ocorrencias", tags=["ocorrencias"])


@router.post("/falta-estoque", response_model=OcorrenciaDetalheOut, status_code=201)
async def reportar_falta_estoque(
    payload: FaltaEstoqueIn,
    user: dict = Depends(requer_papel("separador", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pedido).where(Pedido.id == payload.pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    produtos_sugeridos_ids = await sugerir_substitutos(db, payload.produto_id)

    ocorrencia = Ocorrencia(
        pedido_id=payload.pedido_id,
        tipo="FALTA_ESTOQUE",
        status="ABERTA",
        produto_id=payload.produto_id,
        produtos_sugeridos=produtos_sugeridos_ids,
        motivo=payload.motivo,
        criado_por=user["sub"],
    )
    db.add(ocorrencia)
    await db.commit()
    await db.refresh(ocorrencia)

    await publish_event(
        "order.stock_issue",
        {
            "pedido_id": pedido.id,
            "aluno_id": str(pedido.aluno_id),
            "ocorrencia_id": ocorrencia.id,
            "produto_id": payload.produto_id,
            "produtos_sugeridos": produtos_sugeridos_ids,
        },
    )

    return await _montar_detalhe(db, ocorrencia)


@router.post("/atraso-entrega", response_model=OcorrenciaDetalheOut, status_code=201)
async def reportar_atraso_entrega(
    payload: AtrasoEntregaIn,
    user: dict = Depends(requer_papel("entregador", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pedido).where(Pedido.id == payload.pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    ocorrencia = Ocorrencia(
        pedido_id=payload.pedido_id,
        tipo="ATRASO_ENTREGA",
        status="ABERTA",
        nova_data_sugerida=payload.nova_data_sugerida,
        motivo=payload.motivo,
        criado_por=user["sub"],
    )
    db.add(ocorrencia)
    await db.commit()
    await db.refresh(ocorrencia)

    await publish_event(
        "order.delivery_delayed",
        {
            "pedido_id": pedido.id,
            "aluno_id": str(pedido.aluno_id),
            "ocorrencia_id": ocorrencia.id,
            "nova_data_sugerida": payload.nova_data_sugerida.isoformat(),
            "motivo": payload.motivo,
        },
    )

    return await _montar_detalhe(db, ocorrencia)


@router.get("/pedido/{pedido_id}", response_model=list[OcorrenciaOut])
async def listar_ocorrencias_pedido(
    pedido_id: int,
    apenas_abertas: bool = False,
    user: dict = Depends(requer_papel("separador", "entregador", "admin", "student")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    # Aluno só pode ver ocorrências do próprio pedido
    if user["role"] == "student" and str(pedido.aluno_id) != user["sub"]:
        raise HTTPException(403, "Sem permissão para ver este pedido")

    query = select(Ocorrencia).where(Ocorrencia.pedido_id == pedido_id)
    if apenas_abertas:
        query = query.where(Ocorrencia.status == "ABERTA")
    query = query.order_by(Ocorrencia.criado_em.desc())

    result = await db.execute(query)
    return result.scalars().all()


async def _montar_detalhe(db: AsyncSession, ocorrencia: Ocorrencia) -> OcorrenciaDetalheOut:
    produto_original: ProdutoSugeridoOut | None = None
    if ocorrencia.produto_id:
        result = await db.execute(select(Produto).where(Produto.id == ocorrencia.produto_id))
        p = result.scalar_one_or_none()
        if p:
            produto_original = ProdutoSugeridoOut(
                id=p.id, nome=p.nome, preco=float(p.preco), imagem_url=p.imagem_url
            )

    produtos_sugeridos: list[ProdutoSugeridoOut] = []
    if ocorrencia.produtos_sugeridos:
        result = await db.execute(
            select(Produto).where(Produto.id.in_(ocorrencia.produtos_sugeridos))
        )
        produtos_sugeridos = [
            ProdutoSugeridoOut(id=p.id, nome=p.nome, preco=float(p.preco), imagem_url=p.imagem_url)
            for p in result.scalars().all()
        ]

    return OcorrenciaDetalheOut(
        **OcorrenciaOut.model_validate(ocorrencia).model_dump(),
        produto_original=produto_original,
        produtos_sugeridos=produtos_sugeridos,
    )


@router.get("/{ocorrencia_id}", response_model=OcorrenciaDetalheOut)
async def detalhe_ocorrencia(
    ocorrencia_id: int,
    user: dict = Depends(requer_papel("separador", "entregador", "admin", "student")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Ocorrencia).where(Ocorrencia.id == ocorrencia_id))
    ocorrencia = result.scalar_one_or_none()
    if not ocorrencia:
        raise HTTPException(404, "Ocorrência não encontrada")

    if user["role"] == "student":
        pedido_result = await db.execute(select(Pedido).where(Pedido.id == ocorrencia.pedido_id))
        pedido = pedido_result.scalar_one_or_none()
        if not pedido or str(pedido.aluno_id) != user["sub"]:
            raise HTTPException(403, "Sem permissão para ver esta ocorrência")

    return await _montar_detalhe(db, ocorrencia)


@router.post("/{ocorrencia_id}/resolver", response_model=OcorrenciaOut)
async def resolver_ocorrencia(
    ocorrencia_id: int,
    payload: ResolverOcorrenciaIn,
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Só o aluno dono do pedido pode resolver a ocorrência — é a decisão dele
    (aceitar substituto, remover item, aceitar nova data ou cancelar).
    """
    result = await db.execute(select(Ocorrencia).where(Ocorrencia.id == ocorrencia_id))
    ocorrencia = result.scalar_one_or_none()
    if not ocorrencia:
        raise HTTPException(404, "Ocorrência não encontrada")

    if ocorrencia.status != "ABERTA":
        raise HTTPException(400, "Esta ocorrência já foi resolvida")

    pedido_result = await db.execute(select(Pedido).where(Pedido.id == ocorrencia.pedido_id))
    pedido = pedido_result.scalar_one_or_none()
    if not pedido or str(pedido.aluno_id) != aluno_id:
        raise HTTPException(403, "Sem permissão para resolver esta ocorrência")

    resolucao = payload.resolucao

    # ── Resoluções de FALTA_ESTOQUE ──────────────────────────
    if resolucao == "substituir":
        if ocorrencia.tipo != "FALTA_ESTOQUE":
            raise HTTPException(400, "Resolução inválida para este tipo de ocorrência")
        if not payload.produto_escolhido_id:
            raise HTTPException(400, "produto_escolhido_id é obrigatório")

        item_result = await db.execute(
            select(PedidoItem).where(
                PedidoItem.pedido_id == pedido.id,
                PedidoItem.produto_id == ocorrencia.produto_id,
            )
        )
        item = item_result.scalar_one_or_none()
        if not item:
            raise HTTPException(404, "Item do pedido não encontrado")

        novo_produto_result = await db.execute(
            select(Produto).where(Produto.id == payload.produto_escolhido_id)
        )
        novo_produto = novo_produto_result.scalar_one_or_none()
        if not novo_produto:
            raise HTTPException(404, "Produto escolhido não encontrado")

        diferenca = (novo_produto.preco - item.preco_unitario) * item.quantidade
        item.produto_id = novo_produto.id
        item.preco_unitario = novo_produto.preco
        pedido.valor_total = pedido.valor_total + diferenca

        ocorrencia.produto_escolhido_id = novo_produto.id

    elif resolucao == "remover_item":
        if ocorrencia.tipo != "FALTA_ESTOQUE":
            raise HTTPException(400, "Resolução inválida para este tipo de ocorrência")

        item_result = await db.execute(
            select(PedidoItem).where(
                PedidoItem.pedido_id == pedido.id,
                PedidoItem.produto_id == ocorrencia.produto_id,
            )
        )
        item = item_result.scalar_one_or_none()
        if item:
            pedido.valor_total = pedido.valor_total - (item.preco_unitario * item.quantidade)
            await db.delete(item)

    # ── Resoluções de ATRASO_ENTREGA ─────────────────────────
    elif resolucao == "aceitar_nova_data":
        if ocorrencia.tipo != "ATRASO_ENTREGA":
            raise HTTPException(400, "Resolução inválida para este tipo de ocorrência")
        pedido.data_prevista_entrega = ocorrencia.nova_data_sugerida

    elif resolucao == "cancelar_pedido":
        if not validar_transicao(pedido.status, StatusPedido.CANCELADO.value):
            raise HTTPException(400, f"Não é possível cancelar um pedido em status {pedido.status}")
        pedido.status = StatusPedido.CANCELADO.value
        db.add(
            PedidoStatusHistorico(
                pedido_id=pedido.id,
                status=StatusPedido.CANCELADO.value,
                user_id=aluno_id,
                observacao=f"Cancelado pelo aluno via ocorrência #{ocorrencia.id}",
            )
        )
        await publish_event(
            "order.status_changed",
            {
                "pedido_id": pedido.id,
                "aluno_id": str(pedido.aluno_id),
                "status": StatusPedido.CANCELADO.value,
            },
        )

    ocorrencia.status = "RESOLVIDA"
    ocorrencia.resolucao = resolucao
    ocorrencia.resolvido_em = datetime.now(UTC)

    await db.commit()
    await db.refresh(ocorrencia)

    await publish_event(
        "order.occurrence_resolved",
        {
            "pedido_id": pedido.id,
            "aluno_id": str(pedido.aluno_id),
            "ocorrencia_id": ocorrencia.id,
            "resolucao": resolucao,
        },
    )

    return ocorrencia
