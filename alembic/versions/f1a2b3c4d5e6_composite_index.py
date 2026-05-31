"""composite index on transactions(telegram_user_id, transaction_date)

Revision ID: f1a2b3c4d5e6
Revises: 76896b3a92b7
Create Date: 2026-05-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "76896b3a92b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_transactions_user_date"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {ix["name"] for ix in inspector.get_indexes("transactions")}
    if INDEX_NAME not in existing:
        op.create_index(
            INDEX_NAME, "transactions", ["telegram_user_id", "transaction_date"]
        )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="transactions")
