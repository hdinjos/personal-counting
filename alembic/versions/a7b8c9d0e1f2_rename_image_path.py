"""rename transactions.image_path to telegram_file_id

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-05-31 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns("transactions")}


def upgrade() -> None:
    cols = _columns(op.get_bind())
    if "image_path" in cols and "telegram_file_id" not in cols:
        with op.batch_alter_table("transactions") as batch_op:
            batch_op.alter_column("image_path", new_column_name="telegram_file_id")


def downgrade() -> None:
    cols = _columns(op.get_bind())
    if "telegram_file_id" in cols and "image_path" not in cols:
        with op.batch_alter_table("transactions") as batch_op:
            batch_op.alter_column("telegram_file_id", new_column_name="image_path")
