"""
Ingestão de questões reais do ENEM via api.enem.dev, com classificação
automática por IA (embeddings) — sem mapeamento manual questão -> subtema.

Detalhes importantes da API real (confirmados na documentação oficial,
https://docs.enem.dev):

  - `GET /v1/exams/{ano}/questions` NÃO aceita filtro por disciplina na
    query — só `limit`, `offset` e `language`. A disciplina só vem no
    corpo de cada questão (`discipline`), então o filtro é feito aqui,
    no lado do cliente, depois de paginar por todas as questões da prova.
  - A prova de "Ciências da Natureza" mistura Biologia, Física e Química
    — é exatamente por isso que a classificação por IA é necessária aqui,
    e não um luxo: ela decide quais dessas questões são de fato sobre o
    tema pedido (ex: Citologia) e em qual subtema cada uma se encaixa.
  - Várias questões dependem de imagem (gráficos, tirinhas, mapas) — como
    nosso quiz é só texto, essas são descartadas (`_questao_e_valida`).
  - `correctAlternative` pode ser A-E (5 alternativas), não só A-D.

Uso:
    docker exec -it learning-service python scripts/ingest_enem.py
"""

import asyncio

import httpx
from loguru import logger

from app.database import async_session
from app.models.questao import Questao
from app.services.classificacao_ia import classificar_texto_por_subtema

API_BASE = "https://api.enem.dev/v1"
DISCIPLINA_CIENCIAS_NATUREZA = "ciencias-natureza"

LIMIAR_CONFIANCA = 0.35

NIVEL_DIFICULDADE_PADRAO = 2


async def _buscar_todas_questoes(ano: int, limit: int = 50) -> list[dict]:
    questoes: list[dict] = []
    offset = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            resp = await client.get(
                f"{API_BASE}/exams/{ano}/questions",
                params={"limit": limit, "offset": offset},
            )
            resp.raise_for_status()
            data = resp.json()

            questoes.extend(data["questions"])

            if not data["metadata"]["hasMore"]:
                break
            offset += limit

    return questoes


def _questao_e_valida(q: dict) -> bool:
    if q.get("files"):
        return False
    if any(alt.get("file") for alt in q.get("alternatives", [])):
        return False
    if not q.get("context"):
        return False
    return bool(q.get("correctAlternative"))


async def ingerir(ano: int, tema_id: int, quantidade_maxima: int = 40) -> None:
    logger.info("Buscando questões do ENEM {}...", ano)
    todas = await _buscar_todas_questoes(ano)
    logger.info("{} questões encontradas na prova (todas as disciplinas).", len(todas))

    candidatas = [
        q
        for q in todas
        if q.get("discipline") == DISCIPLINA_CIENCIAS_NATUREZA and _questao_e_valida(q)
    ]
    logger.info(
        "{} questões de Ciências da Natureza válidas (texto puro, sem depender de imagem).",
        len(candidatas),
    )

    ingeridas = 0
    nao_classificadas = 0

    async with async_session() as db:
        for q in candidatas:
            if ingeridas >= quantidade_maxima:
                break

            texto = q["context"]
            subtema_id, confianca = await classificar_texto_por_subtema(db, tema_id, texto)

            if subtema_id is None or confianca < LIMIAR_CONFIANCA:
                nao_classificadas += 1
                continue

            alternativas = {
                alt["letter"]: alt["text"] for alt in q.get("alternatives", []) if alt.get("text")
            }
            if len(alternativas) < 2:
                nao_classificadas += 1
                continue

            db.add(
                Questao(
                    subtema_id=subtema_id,
                    enunciado=texto,
                    alternativas=alternativas,
                    gabarito=q["correctAlternative"],
                    nivel_dificuldade=NIVEL_DIFICULDADE_PADRAO,
                    fonte="ENEM",
                    ano=ano,
                )
            )
            ingeridas += 1
            logger.info(
                "  + questão classificada no subtema {} (confianca {})", subtema_id, confianca
            )

        await db.commit()

    logger.info(
        "Resumo: {} questões ingeridas | {} descartadas (baixa confianca ou dados incompletos).",
        ingeridas,
        nao_classificadas,
    )


if __name__ == "__main__":
    asyncio.run(ingerir(ano=2022, tema_id=2, quantidade_maxima=40))
