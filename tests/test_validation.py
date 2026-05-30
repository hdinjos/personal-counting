from datetime import date, time

from app.services.transaction_service import (
    DEFAULT_STORE_NAME,
    INCOMPLETE_TRANSACTION_MESSAGE,
    MANUAL_TOTAL_MESSAGE,
    STATUS_NEEDS_TOTAL_CONFIRMATION,
    TransactionService,
)
from app.utils.dates import format_date_id, now_local_time, today_local_date


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


def test_process_and_store_success_with_default_store_and_quantity() -> None:
    repo = FakeRepository()
    service = TransactionService(repo)

    payload = {
        "status": "partial",
        "store": {"name": None},
        "transaction": {"date": "2026-05-27", "time": "10:15"},
        "items": [{"name": "Roti", "category": "makanan", "unit_price": "15000", "quantity": None}],
        "summary": {"total": "15000"},
    }

    upload_date = today_local_date("Asia/Jakarta")
    result = service.process_and_store(1, "user", "uploads/1.jpg", payload)

    assert result["status"] == "success"
    assert result["total"] == 15000
    assert repo.called is True
    assert repo.last_payload["total"] == 15000
    assert result["date"] == format_date_id(upload_date, now_local_time("Asia/Jakarta"))
    assert result["receipt_date"] == "27 Mei 2026 10:15 WIB"
    assert repo.last_payload["transaction_date"] == upload_date
    assert repo.last_payload["raw_json"]["transaction"]["date"] == date(2026, 5, 27)
    assert repo.last_payload["store_name"] == DEFAULT_STORE_NAME
    assert repo.last_payload["items"][0]["quantity"] == 1.0


def test_process_and_store_generates_receipt_date_when_missing() -> None:
    repo = FakeRepository()
    service = TransactionService(repo)

    payload = {
        "status": "partial",
        "store": {"name": "Warung"},
        "transaction": {"date": None, "time": "09:00"},
        "items": [{"name": "Kopi", "subtotal": "20000"}],
        "summary": {"total": "20000"},
    }

    upload_date = today_local_date("Asia/Jakarta")
    result = service.process_and_store(1, "user", "uploads/1.jpg", payload)

    assert result["status"] == "success"
    assert result["date"] == format_date_id(upload_date, now_local_time("Asia/Jakarta"))
    assert result["receipt_date"] == format_date_id(upload_date, time(9, 0))
    assert repo.last_payload["transaction_date"] == upload_date
    assert repo.last_payload["raw_json"]["transaction"]["date"] == upload_date


def test_process_and_store_failed_when_minimum_data_missing() -> None:
    repo = FakeRepository()
    service = TransactionService(repo)

    payload = {
        "status": "partial",
        "store": {"name": "Warung"},
        "transaction": {"date": "2026-05-27"},
        "items": [{"name": None, "subtotal": "20000"}],
        "summary": {"total": "20000"},
    }

    result = service.process_and_store(1, "user", "uploads/1.jpg", payload)

    assert result["status"] == "failed"
    assert result["message"] == INCOMPLETE_TRANSACTION_MESSAGE
    assert repo.called is False


def test_process_and_store_requests_total_confirmation_when_mismatch() -> None:
    repo = FakeRepository()
    service = TransactionService(repo)

    payload = {
        "status": "success",
        "store": {"name": "Warung"},
        "transaction": {"date": "2026-05-27"},
        "items": [{"name": "Beras", "subtotal": "10000", "quantity": 1}],
        "summary": {"total": "12000", "discount": 0, "tax": 0, "service_charge": 0},
    }

    result = service.process_and_store(1, "user", "uploads/1.jpg", payload)

    assert result["status"] == STATUS_NEEDS_TOTAL_CONFIRMATION
    assert result["total"] == 12000
    assert result["expected_total"] == 10000
    assert isinstance(result["pending_payload"], dict)
    assert repo.called is False


def test_store_confirmed_transaction_saves_success_with_manual_marker() -> None:
    repo = FakeRepository()
    service = TransactionService(repo)

    mismatch_payload = {
        "status": "success",
        "store": {"name": "Warung"},
        "transaction": {"date": "2026-05-27"},
        "items": [{"name": "Beras", "subtotal": "10000", "quantity": 1}],
        "summary": {"total": "12000", "discount": 0, "tax": 0, "service_charge": 0},
    }
    first_result = service.process_and_store(1, "user", "uploads/1.jpg", mismatch_payload)

    upload_date = today_local_date("Asia/Jakarta")
    result = service.store_confirmed_transaction(
        1,
        "user",
        "uploads/1.jpg",
        first_result["pending_payload"],
        12000,
        upload_date,
    )

    assert result["status"] == "success"
    assert result["total"] == 12000
    assert result["manual_total_input"] is True
    assert result["message"] == MANUAL_TOTAL_MESSAGE
    assert repo.called is True
    assert repo.last_payload["status"] == "success"
    assert repo.last_payload["raw_json"]["manual_total_input"] is True
    assert repo.last_payload["raw_json"]["message"] == MANUAL_TOTAL_MESSAGE
