"""rename expenses to operations

Revision ID: b7f3a1c9d204
Revises: 98ee7f5a555b
Create Date: 2026-07-28

"""

from typing import Sequence, Union

from alembic import op

revision: str = "b7f3a1c9d204"
down_revision: Union[str, Sequence[str], None] = "98ee7f5a555b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("expenses", "operations")


def downgrade() -> None:
    op.rename_table("operations", "expenses")
