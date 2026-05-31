from app.services.transaction_service import (
    DEFAULT_STORE_NAME,
    INCOMPLETE_TRANSACTION_MESSAGE,
    MANUAL_TOTAL_MESSAGE,
    TransactionService,
)
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


def test_prepare_extraction_applies_default_store_and_quantity() -> None:
    service = TransactionService(FakeRepository())

    payload = {
        "status": "partial",
        "store": {"name": None},
        "transaction": {"date": "2026-05-27", "time": "10:15"},
        "items": [{"name": "Roti", "category": "makanan", "unit_price": "15000", "quantity": None}],
        "summary": {"total": "15000"},
    }

    normalized = service.prepare_extraction(payload)

    assert normalized["store"]["name"] == DEFAULT_STORE_NAME
    assert normalized["items"][0]["quantity"] == 1.0
    assert normalized["summary"]["total"] == 15000


def test_expected_total_detects_mismatch_without_mutating_input() -> None:
    service = TransactionService(FakeRepository())

    payload = {
        "status": "success",
        "store": {"name": "Warung"},
        "transaction": {"date": "2026-05-27"},
        "items": [{"name": "Beras", "subtotal": "10000", "quantity": 1}],
        "summary": {"total": "12000", "discount": 0, "tax": 0, "service_charge": 0},
    }
    normalized = service.prepare_extraction(payload)

    expected, corrected = service.expected_total(normalized)

    assert expected == 10000
    # Input must remain untouched.
    assert normalized["summary"]["total"] == 12000
    assert corrected is not normalized


def test_store_confirmed_transaction_failed_when_minimum_data_missing() -> None:
    repo = FakeRepository()
    service = TransactionService(repo)

    payload = {
        "status": "partial",
        "store": {"name": "Warung"},
        "transaction": {"date": "2026-05-27"},
        "items": [{"name": None, "subtotal": "20000"}],
        "summary": {"total": "20000"},
    }
    normalized = service.prepare_extraction(payload)
    upload_date = today_local_date("Asia/Jakarta")

    result = service.store_confirmed_transaction(
        1, "user", "uploads/1.jpg", normalized, 20000, upload_date
    )

    assert result["status"] == "failed"
    assert result["message"] == INCOMPLETE_TRANSACTION_MESSAGE
    assert repo.called is False


def test_store_confirmed_transaction_success_with_default_store() -> None:
    repo = FakeRepository()
    service = TransactionService(repo)

    payload = {
        "status": "partial",
        "store": {"name": None},
        "transaction": {"date": "2026-05-27", "time": "10:15"},
        "items": [{"name": "Roti", "category": "makanan", "unit_price": "15000", "quantity": None}],
        "summary": {"total": "15000"},
    }
    normalized = service.prepare_extraction(payload)
    upload_date = today_local_date("Asia/Jakarta")

    result = service.store_confirmed_transaction(
        1, "user", "uploads/1.jpg", normalized, 15000, upload_date, manual_total_input=False
    )

    assert result["status"] == "success"
    assert result["total"] == 15000
    assert repo.called is True
    assert repo.last_payload["total"] == 15000
    assert repo.last_payload["transaction_date"] == upload_date
    assert repo.last_payload["store_name"] == DEFAULT_STORE_NAME
    assert result["receipt_date"] == "27 Mei 2026 10:15 WIB"


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
    normalized = service.prepare_extraction(mismatch_payload)
    upload_date = today_local_date("Asia/Jakarta")

    result = service.store_confirmed_transaction(
        1, "user", "uploads/1.jpg", normalized, 12000, upload_date
    )

    assert result["status"] == "success"
    assert result["total"] == 12000
    assert result["manual_total_input"] is True
    assert result["message"] == MANUAL_TOTAL_MESSAGE
    assert repo.called is True
    assert repo.last_payload["status"] == "success"
    assert repo.last_payload["raw_json"]["manual_total_input"] is True
    assert repo.last_payload["raw_json"]["message"] == MANUAL_TOTAL_MESSAGE
