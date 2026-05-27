from __future__ import annotations

from datetime import date
from typing import Any

from app.db.repositories import TransactionRepository
from app.utils.dates import parse_receipt_date, parse_receipt_time, today_local_date
from app.utils.money import normalize_amount

ALLOWED_STATUSES = {"success", "partial", "failed"}
ALLOWED_CATEGORIES = {
    "sembako",
    "makanan",
    "minuman",
    "kebersihan",
    "perlengkapan rumah",
    "transportasi",
    "kesehatan",
    "pendidikan",
    "tagihan",
    "lainnya",
}


class TransactionService:
    def __init__(self, repository: TransactionRepository, timezone: str = "Asia/Jakarta") -> None:
        self.repository = repository
        self.timezone = timezone

    def process_and_store(
        self,
        telegram_user_id: int,
        telegram_username: str | None,
        image_path: str,
        extracted_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        normalized = self.normalize_extraction(extracted_payload or {})
        return self.store_normalized(telegram_user_id, telegram_username, image_path, normalized)

    def store_normalized(
        self,
        telegram_user_id: int,
        telegram_username: str | None,
        image_path: str,
        normalized: dict[str, Any],
    ) -> dict[str, Any]:
        status = normalized["status"]
        if status == "failed":
            return {"status": "failed", "message": normalized.get("message")}

        total = normalized["summary"]["total"]
        if total is None:
            return {"status": "failed", "message": "Total belanja tidak ditemukan"}

        upload_date = today_local_date(self.timezone)
        receipt_date = normalized["transaction"]["date"] or upload_date
        normalized["transaction"]["date"] = receipt_date
        receipt_time = normalized["transaction"]["time"]
        store_name = normalized["store"]["name"]

        transaction = self.repository.create_transaction(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            store_name=store_name,
            transaction_date=upload_date,
            transaction_time=receipt_time,
            total=total,
            status=status,
            image_path=image_path,
            raw_json=normalized,
            items=normalized["items"],
        )

        return {
            "status": status,
            "transaction_id": transaction.id,
            "store_name": store_name,
            "date": upload_date.strftime("%Y-%m-%d"),
            "receipt_date": receipt_date.strftime("%Y-%m-%d"),
            "total": total,
            "message": normalized.get("message"),
        }

    def normalize_extraction(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = str(payload.get("status", "failed")).lower().strip()
        if status not in ALLOWED_STATUSES:
            status = "failed"

        message = payload.get("message")
        store = payload.get("store") or {}
        transaction = payload.get("transaction") or {}
        summary = payload.get("summary") or {}
        items = payload.get("items") or []

        parsed_date = parse_receipt_date(transaction.get("date"), current_year=date.today().year)
        parsed_time = parse_receipt_time(transaction.get("time"))

        normalized_items = [self._normalize_item(item) for item in items if isinstance(item, dict)]

        total = normalize_amount(summary.get("total"))
        if total is None:
            item_subtotals = [item["subtotal"] for item in normalized_items if item["subtotal"] is not None]
            if item_subtotals:
                total = sum(item_subtotals)

        return {
            "status": status,
            "message": message,
            "store": {
                "name": self._normalize_text(store.get("name")),
                "address": self._normalize_text(store.get("address")),
                "phone": self._normalize_text(store.get("phone")),
            },
            "transaction": {
                "date": parsed_date,
                "time": parsed_time,
                "invoice_number": self._normalize_text(transaction.get("invoice_number")),
                "payment_method": self._normalize_text(transaction.get("payment_method")),
            },
            "items": normalized_items,
            "summary": {
                "subtotal": normalize_amount(summary.get("subtotal")),
                "discount": normalize_amount(summary.get("discount")),
                "tax": normalize_amount(summary.get("tax")),
                "service_charge": normalize_amount(summary.get("service_charge")),
                "total": total,
                "paid": normalize_amount(summary.get("paid")),
                "change": normalize_amount(summary.get("change")),
            },
            "raw_text": payload.get("raw_text"),
        }

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
        category = (item.get("category") or "lainnya")
        category = str(category).strip().lower()
        if category not in ALLOWED_CATEGORIES:
            category = "lainnya"

        quantity = item.get("quantity")
        if quantity is not None:
            try:
                quantity = float(quantity)
            except (TypeError, ValueError):
                quantity = None

        return {
            "name": TransactionService._normalize_text(item.get("name")),
            "category": category,
            "quantity": quantity,
            "unit": TransactionService._normalize_text(item.get("unit")),
            "unit_price": normalize_amount(item.get("unit_price")),
            "subtotal": normalize_amount(item.get("subtotal")),
        }

    @staticmethod
    def _normalize_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

