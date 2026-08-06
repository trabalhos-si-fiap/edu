"""scrub pii from event_log

O consumer passou a filtrar `nome`/`email`/`telefone`/`documento` na
entrada (app/events/consumer.py), mas as linhas já gravadas continuam
carregando o PII. Esta revision as limpa in-place.

Irreversível de propósito: `downgrade` não tem como recuperar o dado
apagado, e não deveria — recuperá-lo seria reintroduzir o passivo.

Revision ID: a0cdb1104a9b
Revises: 6bebf7b7295f
Create Date: 2026-08-06 10:50:45.146447

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a0cdb1104a9b"
down_revision: str | Sequence[str] | None = "6bebf7b7295f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE event_log "
        "SET payload = payload - 'nome' - 'email' - 'telefone' - 'documento' "
        "WHERE payload ?| array['nome', 'email', 'telefone', 'documento']"
    )


def downgrade() -> None:
    # Sem volta: o dado apagado não existe mais em lugar nenhum, e restaurá-lo
    # seria desfazer o próprio objetivo da revision.
    raise NotImplementedError(
        "scrub de PII é irreversível por design — não há dado para restaurar."
    )
