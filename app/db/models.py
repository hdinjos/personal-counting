from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    store_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    transaction_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    items: Mapped[list["TransactionItem"]] = relationship(
        "TransactionItem",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )


class TransactionItem(Base):
    __tablename__ = "transaction_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unit_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subtotal: Mapped[int | None] = mapped_column(Integer, nullable=True)

    transaction: Mapped[Transaction] = relationship("Transaction", back_populates="items")

