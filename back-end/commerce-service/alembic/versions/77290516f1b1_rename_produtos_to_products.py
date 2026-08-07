"""rename produtos to products

Revision ID: 77290516f1b1
Revises: 62926745dd94
Create Date: 2026-08-07 09:55:19.795270

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "77290516f1b1"
down_revision: str | Sequence[str] | None = "62926745dd94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename explícito, não drop+create: o autogenerate não detecta rename
    # e gera create_table("products") + drop_table("produtos"), que apaga
    # dado. As FKs de estoque, pedido_itens e ocorrencias acompanham o
    # rename da tabela sozinhas — a constraint referencia o OID, não o
    # nome (confirmado no banco descartável, ver task-B3-report.md).
    op.rename_table("produtos", "products")
    op.alter_column("products", "nome", new_column_name="name")
    op.alter_column("products", "descricao", new_column_name="description")
    op.alter_column("products", "preco", new_column_name="price")
    op.alter_column("products", "categoria", new_column_name="type")
    op.alter_column("products", "imagem_url", new_column_name="image_url")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("products", "image_url", new_column_name="imagem_url")
    op.alter_column("products", "type", new_column_name="categoria")
    op.alter_column("products", "price", new_column_name="preco")
    op.alter_column("products", "description", new_column_name="descricao")
    op.alter_column("products", "name", new_column_name="nome")
    op.rename_table("products", "produtos")
