"""
Sugestão de produtos substitutos quando falta estoque, usando embeddings
(similaridade semântica de nome+descrição) em vez de só "mesma categoria
com estoque disponível" — isso permite encontrar substitutos conceitualmente
parecidos mesmo em categorias diferentes (ex: um caderno universitário e um
caderno colegial podem estar em categorias distintas mas serem substitutos
razoáveis um do outro).

IMPORTANTE — mesmo cuidado já validado no Learning Service: se o modelo de
embeddings falhar ao carregar (sem internet, timeout etc.), isso NUNCA pode
impedir o separador de reportar a falta de estoque. `sugerir_substitutos`
sempre degrada para a busca simples por categoria (`_buscar_por_categoria`)
em caso de qualquer falha — o aluno recebe sugestões um pouco menos
precisas, mas o fluxo nunca quebra.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.produto import Estoque, Produto
from app.services.embeddings import gerar_embedding, gerar_embeddings, similaridade_cosseno

LIMIAR_SIMILARIDADE = 0.35


async def _buscar_por_categoria(
    db: AsyncSession, produto_original: Produto, limite: int
) -> list[int]:
    """Fallback determinístico (sem IA) — mesma lógica que existia antes
    desta funcionalidade, usada quando os embeddings não estão disponíveis."""
    result = await db.execute(
        select(Produto.id)
        .join(Estoque, Estoque.produto_id == Produto.id)
        .where(
            Produto.categoria == produto_original.categoria,
            Produto.id != produto_original.id,
            Estoque.quantidade > 0,
        )
        .group_by(Produto.id)
        .limit(limite)
    )
    return [row[0] for row in result.all()]


async def sugerir_substitutos(db: AsyncSession, produto_id: int, limite: int = 3) -> list[int]:
    """
    Sugere até `limite` produtos substitutos para `produto_id`, ordenados
    por similaridade semântica (nome + descrição), entre os produtos com
    estoque disponível em algum fornecedor — não restrito à mesma
    categoria, diferente da busca antiga.
    """
    result = await db.execute(select(Produto).where(Produto.id == produto_id))
    produto_original = result.scalar_one_or_none()
    if not produto_original:
        return []

    # Candidatos: qualquer produto com estoque > 0, exceto o próprio.
    result = await db.execute(
        select(Produto)
        .join(Estoque, Estoque.produto_id == Produto.id)
        .where(Produto.id != produto_id, Estoque.quantidade > 0)
        .group_by(Produto.id)
    )
    candidatos = result.scalars().all()
    if not candidatos:
        return []

    try:
        texto_original = f"{produto_original.nome}. {produto_original.descricao or ''}".strip()
        textos_candidatos = [f"{c.nome}. {c.descricao or ''}".strip() for c in candidatos]

        embedding_original = gerar_embedding(texto_original)
        embeddings_candidatos = gerar_embeddings(textos_candidatos)

        pontuados = [
            (candidatos[i].id, similaridade_cosseno(embedding_original, embeddings_candidatos[i]))
            for i in range(len(candidatos))
        ]
        pontuados.sort(key=lambda par: par[1], reverse=True)

        relevantes = [pid for pid, sim in pontuados if sim >= LIMIAR_SIMILARIDADE]
        if relevantes:
            return relevantes[:limite]

        # Nenhum candidato passou do limiar de similaridade — cai para a
        # busca por categoria em vez de devolver uma lista vazia.
        return await _buscar_por_categoria(db, produto_original, limite)

    except Exception:
        # Falha ao carregar/rodar o modelo de embeddings (sem internet,
        # timeout etc.) — degrada para o comportamento determinístico
        # anterior, nunca propaga erro para quem está reportando a
        # ocorrência de falta de estoque.
        return await _buscar_por_categoria(db, produto_original, limite)
