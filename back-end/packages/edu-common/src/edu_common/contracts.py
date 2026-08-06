"""Formato dos payloads publicados na exchange — a definição que produtor e
consumidores compartilham.

`events.py` cuida do *transporte* (exchange topic durável, mensagem
persistente, corpo JSON). Este módulo cuida do *conteúdo*: quais chaves cada
evento carrega e com que nome elas vão para o barramento.

Por que isto existe. Antes, o produtor montava um dict literal no router e
cada consumidor recriava um literal igual na própria suíte, com uma docstring
prometendo que os dois espelhavam o mesmo formato — mas sem importar nada um
do outro. O resultado foi medido: renomear `dominio_tema` para `dominio` no
`learning-service/app/routers/diagnostico.py` deixava learning, notification e
analytics **inteiramente verdes**, 102 testes cegos exatamente para o defeito
que já tinha consumido uma rodada inteira de correção. Uma promessa em prosa
não é um acoplamento.

Como usar. O produtor publica sempre por aqui:

    await publish_event(
        DiagnosticCompleted.ROUTING_KEY,
        DiagnosticCompleted(...).to_payload(),
    )

e as suítes dos consumidores constroem seus fixtures a partir da MESMA classe,
em vez de um literal local. Com isso, renomear um campo aqui muda de fato o
payload que os testes dos consumidores recebem: quem lê a chave antiga passa a
ler `None` e falha. O nome do campo do dataclass É a chave do barramento
(`to_payload` usa `asdict`), então os dois não têm como divergir em silêncio.

Os testes que fixam o formato (`tests/test_contracts.py` aqui, e o teste de
produtor de cada serviço) escrevem os nomes das chaves como **literais** — usar
as constantes deste módulo faria o teste seguir uma renomeação em vez de
detectá-la.
"""

from dataclasses import asdict, dataclass
from typing import ClassVar


@dataclass(frozen=True)
class DiagnosticCompleted:
    """Publicado pelo learning-service ao fechar um diagnóstico de tema.

    Consumido por notification-service (`handle_diagnostic_completed`, que lê
    `aluno_id`, `acao` e `dominio_tema`) e por analytics-service (que grava o
    payload cru em `event_log` e depois lê `tema_id`/`dominio_tema`/`acao` em
    `GET /analytics/students/{id}`).
    """

    ROUTING_KEY: ClassVar[str] = "diagnostic.completed"

    aluno_id: str
    tema_id: int
    dominio_tema: float
    acao: str

    def to_payload(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class StudentCreated:
    """Publicado pelo auth-users-service em `POST /auth/register`.

    Consumido por learning-service (`handle_student_created`, que cria uma
    linha de `AlunoTemaProgresso` zerada em todo subtema) e por
    analytics-service (grava em `event_log`, mas com `nome`/`email` removidos
    na entrada por `_sem_pii` — não é mais o payload cru).
    """

    ROUTING_KEY: ClassVar[str] = "student.created"

    aluno_id: str
    nome: str
    email: str

    def to_payload(self) -> dict:
        return asdict(self)
