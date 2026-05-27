from datetime import date

from app.services.transaction_service import TransactionService
from app.utils.dates import today_local_date


class FakeRepository:
    def __init__(self) -> None:
        self.called = False
        self.last_payload = None

    def create_transaction(self, **kwargs):
        self.called = True
        self.last_payload = kwargs

        class Result:
            id = 123

        return Result()


def test_process_and_store_success() -> None:
    repo = FakeRepository()
    service = TransactionService(repo)

    payload = {
        "status": "success",
        "store": {"name": "Indomaret"},
        "transaction": {"date": "2026-05-27", "time": "10:15"},
        "items": [{"name": "Roti", "category": "makanan", "subtotal": "15000"}],
        "summary": {"total": "15000"},
    }

    upload_date = today_local_date("Asia/Jakarta")
    result = service.process_and_store(1, "user", "uploads/1.jpg", payload)

    assert result["status"] == "success"
    assert result["total"] == 15000
    assert repo.called is True
    assert repo.last_payload["total"] == 15000
    assert result["date"] == upload_date.strftime("%Y-%m-%d")
    assert result["receipt_date"] == "2026-05-27"
    assert repo.last_payload["transaction_date"] == upload_date
    assert repo.last_payload["raw_json"]["transaction"]["date"] == date(2026, 5, 27)


def test_process_and_store_generates_receipt_date_when_missing() -> None:
    repo = FakeRepository()
    service = TransactionService(repo)

    payload = {
        "status": "partial",
        "store": {"name": "Warung"},
        "transaction": {"date": None, "time": "09:00"},
        "items": [],
        "summary": {"total": "20000"},
    }

    upload_date = today_local_date("Asia/Jakarta")
    result = service.process_and_store(1, "user", "uploads/1.jpg", payload)

    assert result["status"] == "partial"
    assert result["date"] == upload_date.strftime("%Y-%m-%d")
    assert result["receipt_date"] == upload_date.strftime("%Y-%m-%d")
    assert repo.last_payload["transaction_date"] == upload_date
    assert repo.last_payload["raw_json"]["transaction"]["date"] == upload_date


def test_process_and_store_failed_when_total_missing() -> None:
    repo = FakeRepository()
    service = TransactionService(repo)

    payload = {
        "status": "partial",
        "store": {"name": "Warung"},
        "transaction": {"date": "2026-05-27"},
        "items": [],
        "summary": {"total": None},
    }

    result = service.process_and_store(1, "user", "uploads/1.jpg", payload)

    assert result["status"] == "failed"
    assert repo.called is False

