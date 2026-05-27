from __future__ import annotations

from datetime import date

from app.db.repositories import TransactionRepository


class ReportService:
    def __init__(self, repository: TransactionRepository) -> None:
        self.repository = repository

    def get_daily_report(self, telegram_user_id: int, target_date: date) -> dict:
        count, total = self.repository.get_daily_summary(telegram_user_id, target_date)
        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "count": count,
            "total": total,
        }

    def get_monthly_report(self, telegram_user_id: int, year: int, month: int) -> dict:
        count, total = self.repository.get_monthly_summary(telegram_user_id, year, month)
        return {
            "month": f"{year:04d}-{month:02d}",
            "count": count,
            "total": total,
        }

    def get_last_transactions(self, telegram_user_id: int, limit: int = 5) -> dict:
        transactions = self.repository.get_last_transactions(telegram_user_id, limit)
        formatted = [
            {
                "id": tx.id,
                "date": tx.transaction_date.strftime("%Y-%m-%d"),
                "store_name": tx.store_name or "-",
                "total": tx.total,
                "status": tx.status,
            }
            for tx in transactions
        ]
        return {"transactions": formatted}

