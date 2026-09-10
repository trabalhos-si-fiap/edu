"""Geração do percurso de estudo — a regra explícita da spec D.

Quatro passos, na ordem em que a spec os escreve:

1. Matérias na ordem do seed (`Materia.id`).
2. Temas e subtemas dentro de cada uma, por `.ordem` (com `.id` como
   desempate: `.ordem` tem default 0 e não é única — a mesma correção que
   `routers/materias.py` já carrega).
3. Prazos distribuídos entre hoje e a data-alvo.
4. Etapa de subtema já dominado nasce concluída.

Trocar isto por distribuição adaptativa depois é substituir estas funções,
não desmontar tela nenhuma: quem chama sabe só `gerar_roadmap`.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.progresso import AlunoTemaProgresso
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema
from app.services.decisao import LIMIAR_DOMINIO_SUBTEMA

# Teto de segurança: o seed completo do ENEM tem ordem de 130 subtemas.
TETO_ETAPAS = 2000


def distribuir_prazos(quantidade: int, inicio: date, data_alvo: date) -> list[date]:
    """Espalha `quantidade` etapas entre `inicio` e `data_alvo`, inclusive.

    A primeira vence hoje e a última na data-alvo. Quando há mais etapas que
    dias, vários prazos caem no mesmo dia — é o "agrupa em vez de falhar" da
    spec: recusar seria impedir um aluno de estudar para a prova da semana
    que vem.
    """
    if quantidade <= 0:
        return []
    dias = max((data_alvo - inicio).days, 0)
    if quantidade == 1:
        return [inicio + timedelta(days=dias)]
    return [inicio + timedelta(days=(i * dias) // (quantidade - 1)) for i in range(quantidade)]


def prazo_apertado(quantidade: int, inicio: date, data_alvo: date) -> bool:
    """Verdadeiro quando não há um dia inteiro por etapa."""
    dias_disponiveis = max((data_alvo - inicio).days, 0) + 1
    return quantidade > dias_disponiveis


async def _subtemas_em_ordem(db: AsyncSession) -> list[int]:
    resultado = await db.execute(
        select(Subtema.id)
        .join(Tema, Tema.id == Subtema.tema_id)
        .join(Materia, Materia.id == Tema.materia_id)
        .order_by(
            Materia.id.asc(),
            Tema.ordem.asc(),
            Tema.id.asc(),
            Subtema.ordem.asc(),
            Subtema.id.asc(),
        )
        .limit(TETO_ETAPAS)
    )
    return list(resultado.scalars().all())


async def gerar_roadmap(
    db: AsyncSession,
    *,
    aluno_id: uuid.UUID | str,
    data_alvo: date,
    hoje: date,
) -> int:
    """(Re)gera o percurso do aluno. Devolve quantas etapas ficaram.

    Regenerar é APAGAR e REINSERIR, com as conclusões relidas antes do
    delete: um `UPDATE` etapa a etapa teria que lidar com subtema que sumiu
    do seed e com subtema novo, dois caminhos a mais para manter certos.

    Não faz commit — a rota que chama decide a transação.
    """
    subtema_ids = await _subtemas_em_ordem(db)

    concluidas: dict[int, datetime] = {
        etapa.subtema_id: etapa.concluida_em
        for etapa in (
            await db.execute(select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == aluno_id))
        )
        .scalars()
        .all()
        if etapa.concluida_em is not None
    }

    dominados = set(
        (
            await db.execute(
                select(AlunoTemaProgresso.subtema_id).where(
                    AlunoTemaProgresso.aluno_id == aluno_id,
                    AlunoTemaProgresso.nivel_dominio >= LIMIAR_DOMINIO_SUBTEMA,
                )
            )
        )
        .scalars()
        .all()
    )

    await db.execute(delete(EtapaRoadmap).where(EtapaRoadmap.aluno_id == aluno_id))

    if not subtema_ids:
        return 0

    prazos = distribuir_prazos(len(subtema_ids), hoje, data_alvo)
    agora = datetime.now(UTC)
    for ordem, subtema_id in enumerate(subtema_ids):
        concluida_em = concluidas.get(subtema_id)
        if concluida_em is None and subtema_id in dominados:
            concluida_em = agora
        db.add(
            EtapaRoadmap(
                aluno_id=aluno_id,
                subtema_id=subtema_id,
                ordem=ordem,
                prazo=prazos[ordem],
                concluida_em=concluida_em,
            )
        )
    return len(subtema_ids)


async def concluir_etapa(
    db: AsyncSession,
    *,
    aluno_id: uuid.UUID | str,
    subtema_id: int,
    quando: datetime,
) -> bool:
    """Marca a etapa como concluída. Devolve `True` só na transição.

    O `WHERE concluida_em IS NULL` é o que torna a chamada idempotente sem
    uma leitura antes: a segunda passagem não encontra linha para atualizar
    e devolve `False` — e é esse `False` que impede a rota de pontuar duas
    vezes a mesma conclusão.
    """
    resultado = await db.execute(
        update(EtapaRoadmap)
        .where(
            EtapaRoadmap.aluno_id == aluno_id,
            EtapaRoadmap.subtema_id == subtema_id,
            EtapaRoadmap.concluida_em.is_(None),
        )
        .values(concluida_em=quando)
    )
    return bool(resultado.rowcount)
