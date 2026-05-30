"""initial schema

Revision ID: 76896b3a92b7
Revises:
Create Date: 2026-05-30 08:22:49.278279

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '76896b3a92b7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "transactions" not in existing_tables:
        op.create_table(
            "transactions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("telegram_user_id", sa.Integer(), nullable=False, index=True),
            sa.Column("telegram_username", sa.String(128), nullable=True),
            sa.Column("store_name", sa.String(255), nullable=True),
            sa.Column("transaction_date", sa.Date(), nullable=False, index=True),
            sa.Column("transaction_time", sa.Time(), nullable=True),
            sa.Column("total", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("image_path", sa.String(512), nullable=False),
            sa.Column("raw_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    if "transaction_items" not in existing_tables:
        op.create_table(
            "transaction_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False, index=True),
            sa.Column("name", sa.String(255), nullable=True),
            sa.Column("category", sa.String(64), nullable=True),
            sa.Column("quantity", sa.Float(), nullable=True),
            sa.Column("unit", sa.String(32), nullable=True),
            sa.Column("unit_price", sa.Integer(), nullable=True),
            sa.Column("subtotal", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("transaction_items")
    op.drop_table("transactions")
