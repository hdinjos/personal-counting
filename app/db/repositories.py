from __future__ import annotations

import json
from contextlib import AbstractContextManager
from datetime import date
from typing import Any, Callable, Iterable

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.database import session_scope
from app.db.models import Transaction, TransactionItem
from app.utils.dates import month_date_bounds

SessionFactory = Callable[[], AbstractContextManager[Session]]


class TransactionRepository:
    def __init__(self, session_factory: SessionFactory = session_scope) -> None:
        self.session_factory = session_factory

    def create_transaction(
        self,
        telegram_user_id: int,
        telegram_username: str | None,
        store_name: str | None,
        transaction_date: date,
        transaction_time,
        total: int,
        status: str,
        image_path: str,
        raw_json: dict[str, Any] | None,
        items: Iterable[dict[str, Any]] | None = None,
    ) -> Transaction:
        with self.session_factory() as session:
            transaction = Transaction(
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
                store_name=store_name,
                transaction_date=transaction_date,
                transaction_time=transaction_time,
                total=total,
                status=status,
                image_path=image_path,
                raw_json=json.dumps(raw_json, ensure_ascii=False, default=str) if raw_json is not None else None,
            )
            for item in items or []:
                transaction.items.append(
                    TransactionItem(
                        name=item.get("name"),
                        category=item.get("category"),
                        quantity=item.get("quantity"),
                        unit=item.get("unit"),
                        unit_price=item.get("unit_price"),
                        subtotal=item.get("subtotal"),
                    )
                )

            session.add(transaction)
            session.flush()
            session.refresh(transaction)
            return transaction

    def get_transactions_for_day(self, telegram_user_id: int, target_date: date) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(
                and_(
                    Transaction.telegram_user_id == telegram_user_id,
                    Transaction.transaction_date == target_date,
                )
            )
            .order_by(Transaction.created_at.desc())
        )
        return self._fetch_transactions(stmt)

    def get_transactions_for_month(
        self, telegram_user_id: int, year: int, month: int
    ) -> list[Transaction]:
        month_start, month_end = month_date_bounds(year, month)
        stmt = (
            select(Transaction)
            .where(
                and_(
                    Transaction.telegram_user_id == telegram_user_id,
                    Transaction.transaction_date >= month_start,
                    Transaction.transaction_date < month_end,
                )
            )
            .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        )
        return self._fetch_transactions(stmt)

    def get_last_transactions(self, telegram_user_id: int, limit: int = 5) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(Transaction.telegram_user_id == telegram_user_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
        return self._fetch_transactions(stmt)

    def delete_transaction(self, telegram_user_id: int, transaction_id: int) -> bool:
        stmt = select(Transaction).where(
            and_(
                Transaction.id == transaction_id,
                Transaction.telegram_user_id == telegram_user_id
            )
        )
        with self.session_factory() as session:
            tx = session.scalar(stmt)
            if not tx:
                return False
            session.delete(tx)
            return True

    def get_daily_summary(self, telegram_user_id: int, target_date: date) -> tuple[int, int]:
        stmt = (
            select(func.count(Transaction.id), func.sum(Transaction.total))
            .where(
                and_(
                    Transaction.telegram_user_id == telegram_user_id,
                    Transaction.transaction_date == target_date,
                )
            )
        )
        with self.session_factory() as session:
            row = session.execute(stmt).first()
            if row:
                return row[0] or 0, row[1] or 0
            return 0, 0

    def get_monthly_summary(self, telegram_user_id: int, year: int, month: int) -> tuple[int, int]:
        month_start, month_end = month_date_bounds(year, month)
        stmt = (
            select(func.count(Transaction.id), func.sum(Transaction.total))
            .where(
                and_(
                    Transaction.telegram_user_id == telegram_user_id,
                    Transaction.transaction_date >= month_start,
                    Transaction.transaction_date < month_end,
                )
            )
        )
        with self.session_factory() as session:
            row = session.execute(stmt).first()
            if row:
                return row[0] or 0, row[1] or 0
            return 0, 0

    def _fetch_transactions(self, stmt: Select[tuple[Transaction]]) -> list[Transaction]:
        stmt = stmt.options(selectinload(Transaction.items))
        with self.session_factory() as session:
            return list(session.scalars(stmt).all())

