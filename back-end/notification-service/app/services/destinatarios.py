"""Quem é avisado de quê.

A regra mora AQUI, e não no commerce, porque o destinatário depende da
TRANSIÇÃO e não do evento — e porque quem sabe endereçar push é este serviço.
O commerce publica o fato; este módulo decide a audiência.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff import Staff

ALUNO = "aluno"

# Exaustivo sobre os dez estados internos do commerce. Um estado novo sem
# entrada aqui quebra `test_every_internal_status_has_a_recipient_rule` — que
# é o comportamento desejado: um push endereçado a ninguém é indistinguível,
# em produção, de um push que não foi publicado.
PAPEIS_POR_STATUS: dict[str, tuple[str, ...]] = {
    # Estado transitório que `confirmar_pagamento` atravessa na mesma chamada:
    # avisar aqui daria duas notificações por um clique. A supressão já
    # existia no handler e continua, agora escrita como dado.
    "CRIADO": (),
    "CONFIRMADO": (),
    "AGUARDANDO_SEPARACAO": (ALUNO, "separador"),
    "EM_SEPARACAO": (ALUNO,),
    "AGUARDANDO_SUBSTITUICAO": (ALUNO,),
    "SEPARADO": (ALUNO,),
    "AGUARDANDO_COLETA": (ALUNO, "entregador"),
    "EM_TRANSITO": (ALUNO,),
    "ENTREGUE": (ALUNO, "admin"),
    "CANCELADO": (ALUNO, "admin"),
}

PAPEIS_ORDER_CREATED: tuple[str, ...] = ("admin", "separador")
PAPEIS_STOCK_ISSUE: tuple[str, ...] = (ALUNO,)
PAPEIS_DELIVERY_DELAYED: tuple[str, ...] = (ALUNO,)
# O separador é quem está bloqueado esperando a decisão do aluno
# (`finalizar_separacao` recusa com ocorrência aberta).
PAPEIS_OCCURRENCE_RESOLVED: tuple[str, ...] = ("separador",)


async def resolver(db: AsyncSession, papeis: tuple[str, ...], aluno_id: str) -> list[str]:
    """Traduz papéis em ids de destinatário, sem repetir ninguém.

    Um registro de staff vazio devolve só o aluno — nunca uma lista vazia
    quando `aluno` está entre os papéis. Notificação de comprador não pode
    depender de um evento de staff ter chegado antes.
    """
    ids: list[str] = []
    if ALUNO in papeis:
        ids.append(aluno_id)

    papeis_staff = tuple(p for p in papeis if p != ALUNO)
    if papeis_staff:
        encontrados = (
            (await db.execute(select(Staff.user_id).where(Staff.papel.in_(papeis_staff))))
            .scalars()
            .all()
        )
        ids.extend(str(uid) for uid in encontrados)

    vistos: set[str] = set()
    return [i for i in ids if not (i in vistos or vistos.add(i))]
