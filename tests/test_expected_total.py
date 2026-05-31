from app.services.transaction_service import TransactionService


def _service() -> TransactionService:
    class _Repo:
        def create_transaction(self, **kwargs):
            raise AssertionError("should not be called")

    return TransactionService(_Repo())


def test_double_counting_fix() -> None:
    service = _service()
    payload = {
        "status": "success",
        "store": {"name": "Toko"},
        "transaction": {},
        "items": [
            {"name": "A", "quantity": 2, "unit_price": 10000, "subtotal": 20000},
            {"name": "B", "quantity": 2, "unit_price": 5000, "subtotal": 10000},
        ],
        "summary": {"total": 15000},
    }
    normalized = service.prepare_extraction(payload)

    expected, corrected = service.expected_total(normalized)

    assert expected == 15000
    assert corrected["items"][0]["subtotal"] == 10000
    assert corrected["items"][1]["subtotal"] == 5000
    # Input untouched.
    assert normalized["items"][0]["subtotal"] == 20000


def test_inclusive_tax_fix() -> None:
    service = _service()
    payload = {
        "status": "success",
        "store": {"name": "Toko"},
        "transaction": {},
        "items": [{"name": "A", "quantity": 1, "unit_price": 50000, "subtotal": 50000}],
        "summary": {"total": 50000, "discount": 0, "tax": 5000, "service_charge": 0},
    }
    normalized = service.prepare_extraction(payload)

    expected, corrected = service.expected_total(normalized)

    assert expected == 50000
    assert corrected["summary"]["tax"] is None
    assert normalized["summary"]["tax"] == 5000


def test_tax_inference() -> None:
    service = _service()
    payload = {
        "status": "success",
        "store": {"name": "Toko"},
        "transaction": {},
        "items": [{"name": "A", "quantity": 1, "unit_price": 100000, "subtotal": 100000}],
        "summary": {"total": 110000, "discount": 0, "service_charge": 0},
    }
    normalized = service.prepare_extraction(payload)

    expected, corrected = service.expected_total(normalized)

    assert expected == 110000
    assert corrected["summary"]["tax"] == 10000
    assert normalized["summary"]["tax"] is None


def test_discount_correction() -> None:
    service = _service()
    payload = {
        "status": "success",
        "store": {"name": "Toko"},
        "transaction": {},
        "items": [{"name": "A", "quantity": 1, "unit_price": 100000, "subtotal": 100000}],
        "summary": {"total": 90000, "discount": 0, "tax": 0, "service_charge": 0},
    }
    normalized = service.prepare_extraction(payload)

    expected, corrected = service.expected_total(normalized)

    assert expected == 90000
    assert corrected["summary"]["discount"] == 10000
    assert normalized["summary"]["discount"] == 0
