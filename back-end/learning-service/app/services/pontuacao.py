"""A regra de pontuação da spec D — aqui, e em nenhum outro lugar.

Quem lança pontos são a rota de resposta ao diagnóstico (questão correta,
revisão no prazo, bônus de sequência) e a conclusão de etapa do roadmap.
Todos passam por `registrar`, que é idempotente por
`(aluno_id, origem, referencia)`.

Nível NÃO é gravado: `nivel_do_total` o calcula na leitura. Mudar as faixas
depois é editar uma tupla, não migrar dado.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pontuacao import LancamentoPontos

PONTOS_QUESTAO_CORRETA = 10
PONTOS_REVISAO_NO_PRAZO = 15
PONTOS_ETAPA_CONCLUIDA = 50

PONTOS_POR_ACERTO_EM_SEQUENCIA = 5
TETO_BONUS_STREAK = 50

# Total mínimo de cada nível. O índice na tupla + 1 é o nível: 0 pontos é
# nível 1, 100 é nível 2, e assim por diante até o teto de 10.
FAIXAS_NIVEL = (0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500)


def bonus_streak(streak: int) -> int:
    """5 pontos por acerto em sequência, com teto de 50.

    Sem o teto, uma sequência longa vale mais que todo o resto do sistema
    junto — e a sequência é o número mais fácil de inflar respondendo
    questões fáceis.
    """
    if streak <= 0:
        return 0
    return min(PONTOS_POR_ACERTO_EM_SEQUENCIA * streak, TETO_BONUS_STREAK)


def nivel_do_total(total: int) -> int:
    """Nível derivado do total de pontos, pelas faixas fixas de `FAIXAS_NIVEL`."""
    nivel = 1
    for indice, minimo in enumerate(FAIXAS_NIVEL):
        if total >= minimo:
            nivel = indice + 1
    return nivel


async def registrar(
    db: AsyncSession,
    *,
    aluno_id: uuid.UUID | str,
    origem: str,
    referencia: str,
    pontos: int,
) -> bool:
    """Grava um lançamento, ou não faz nada se a trinca já existir.

    `ON CONFLICT DO NOTHING` e não "SELECT, decidir, INSERT": duas respostas
    simultâneas do mesmo aluno para a mesma questão leriam as duas "não
    existe" e gravariam as duas (regra 3 do CLAUDE.md). Aqui quem decide é o
    índice único, dentro do banco.

    NÃO faz commit — quem abre a transação decide quando fechá-la. Na rota de
    resposta, pontos e progresso fecham juntos.
    """
    stmt = (
        pg_insert(LancamentoPontos)
        .values(aluno_id=aluno_id, origem=origem, referencia=referencia, pontos=pontos)
        .on_conflict_do_nothing(constraint="uq_lancamento_idempotente")
        .returning(LancamentoPontos.id)
    )
    resultado = await db.execute(stmt)
    return resultado.scalar_one_or_none() is not None


async def total_de_pontos(db: AsyncSession, aluno_id: uuid.UUID | str) -> int:
    """Soma do extrato. Zero para quem nunca pontuou — `coalesce` porque
    `SUM` de conjunto vazio é NULL, e a tela mostra número, não nada."""
    total = await db.execute(
        select(func.coalesce(func.sum(LancamentoPontos.pontos), 0)).where(
            LancamentoPontos.aluno_id == aluno_id
        )
    )
    return int(total.scalar_one())
