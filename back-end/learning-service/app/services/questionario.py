import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.questao import Questao
from app.models.subtema import Subtema

QUANTIDADE_PADRAO = 15


async def montar_questionario(
    db: AsyncSession, tema_id: int, quantidade: int = QUANTIDADE_PADRAO
) -> list[Questao]:
    """
    Monta um questionário de `quantidade` questões distribuídas entre todos
    os subtemas de um tema (ex: as 4 partes de Citologia), em round-robin,
    para que o diagnóstico cubra o tema inteiro e não só um pedaço dele.

    Se o tema tiver menos questões cadastradas do que `quantidade`, retorna
    todas as disponíveis sem erro (útil enquanto o banco de questões ainda
    está sendo populado).
    """
    result = await db.execute(
        select(Subtema).where(Subtema.tema_id == tema_id).order_by(Subtema.ordem.asc())
    )
    subtemas = result.scalars().all()
    if not subtemas:
        return []

    pool_por_subtema: dict[int, list[Questao]] = {}
    for subtema in subtemas:
        result = await db.execute(select(Questao).where(Questao.subtema_id == subtema.id))
        questoes = list(result.scalars().all())
        random.shuffle(questoes)
        pool_por_subtema[subtema.id] = questoes

    questionario: list[Questao] = []
    indice_atual = {subtema.id: 0 for subtema in subtemas}

    while len(questionario) < quantidade:
        avancou_alguma = False
        for subtema in subtemas:
            sid = subtema.id
            i = indice_atual[sid]
            if i < len(pool_por_subtema[sid]):
                questionario.append(pool_por_subtema[sid][i])
                indice_atual[sid] += 1
                avancou_alguma = True
                if len(questionario) >= quantidade:
                    break
        if not avancou_alguma:
            break

    return questionario
