from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.db.repositories import TransactionRepository
from app.services.report_service import ReportService


def build_test_repository() -> TransactionRepository:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    @contextmanager
    def local_session_scope():
        session: Session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return TransactionRepository(session_factory=local_session_scope)


def test_daily_and_monthly_report() -> None:
    repo = build_test_repository()
    report_service = ReportService(repo)

    repo.create_transaction(
        telegram_user_id=1,
        telegram_username="user",
        store_name="Indomaret",
        transaction_date=date(2026, 5, 27),
        transaction_time=None,
        total=35000,
        status="success",
        image_path="uploads/a.jpg",
        raw_json={},
        items=[],
    )
    repo.create_transaction(
        telegram_user_id=1,
        telegram_username="user",
        store_name="Warung",
        transaction_date=date(2026, 5, 27),
        transaction_time=None,
        total=20000,
        status="partial",
        image_path="uploads/b.jpg",
        raw_json={},
        items=[],
    )

    daily = report_service.get_daily_report(1, date(2026, 5, 27))
    monthly = report_service.get_monthly_report(1, 2026, 5)

    assert daily["count"] == 2
    assert daily["total"] == 55000
    assert monthly["count"] == 2
    assert monthly["total"] == 55000


def test_last_transactions() -> None:
    repo = build_test_repository()
    report_service = ReportService(repo)

    for idx in range(3):
        repo.create_transaction(
            telegram_user_id=1,
            telegram_username="user",
            store_name=f"Toko {idx}",
            transaction_date=date(2026, 5, 27),
            transaction_time=None,
            total=10000 + idx,
            status="success",
            image_path=f"uploads/{idx}.jpg",
            raw_json={},
            items=[],
        )

    latest = report_service.get_last_transactions(1, limit=2)
    assert len(latest["transactions"]) == 2

