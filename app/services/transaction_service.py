from __future__ import annotations

from datetime import date
from typing import Any

from app.db.repositories import TransactionRepository
from app.utils.dates import format_date_id, now_local_time, parse_receipt_date, parse_receipt_time, today_local_date
from app.utils.money import normalize_amount

ALLOWED_STATUSES = {"success", "partial", "failed"}
STATUS_NEEDS_TOTAL_CONFIRMATION = "needs_total_confirmation"
DEFAULT_STORE_NAME = "Toko belum diatur"
MANUAL_TOTAL_MESSAGE = "Total transaksi diinput manual oleh user."
INCOMPLETE_TRANSACTION_MESSAGE = "Data transaksi belum lengkap. Mohon upload ulang struk atau kirim voice note lagi."
ALLOWED_CATEGORIES = {
    "sembako",
    "makanan",
    "minuman",
    "jajanan & kopi",
    "kebersihan",
    "perlengkapan rumah",
    "elektronik",
    "pakaian",
    "perawatan diri",
    "kesehatan",
    "transportasi",
    "pendidikan",
    "hiburan",
    "tagihan & utilitas",
    "pulsa & internet",
    "anak & bayi",
    "hadiah & donasi",
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
        if normalized["status"] == "failed":
            return {"status": "failed", "message": normalized.get("message")}

        self._apply_defaults(normalized)
        if not self._has_minimum_transaction_data(normalized):
            return {"status": "failed", "message": INCOMPLETE_TRANSACTION_MESSAGE}

        self._fill_missing_totals(normalized)
        total = normalized["summary"]["total"]
        if total is None or total <= 0:
            return {"status": "failed", "message": INCOMPLETE_TRANSACTION_MESSAGE}

        upload_date = today_local_date(self.timezone)
        receipt_date = normalized["transaction"]["date"] or upload_date
        normalized["transaction"]["date"] = receipt_date
        receipt_time = normalized["transaction"]["time"]
        upload_time = now_local_time(self.timezone)

        expected_total = self._calculate_expected_total(normalized)
        if expected_total is not None and expected_total != total:
            return {
                "status": STATUS_NEEDS_TOTAL_CONFIRMATION,
                "store_name": normalized["store"]["name"],
                "date": format_date_id(upload_date, upload_time),
                "receipt_date": format_date_id(receipt_date, receipt_time),
                "total": total,
                "expected_total": expected_total,
                "message": "Total transaksi belum konsisten dengan rincian item.",
                "pending_payload": normalized,
            }

        normalized["status"] = "success"
        return self._store_transaction(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            image_path=image_path,
            normalized=normalized,
            upload_date=upload_date,
            manual_total_input=normalized.get("manual_total_input", False),
        )

    def store_confirmed_transaction(
        self,
        telegram_user_id: int,
        telegram_username: str | None,
        image_path: str,
        normalized_payload: dict[str, Any],
        confirmed_total: int,
        upload_date: date | None = None,
        manual_total_input: bool = True,
    ) -> dict[str, Any]:
        total = normalize_amount(confirmed_total)
        if total is None or total <= 0:
            return {"status": "failed", "message": "Nominal total tidak valid."}

        normalized = self.normalize_extraction(normalized_payload or {})
        self._apply_defaults(normalized)
        if not self._has_minimum_transaction_data(normalized):
            return {"status": "failed", "message": INCOMPLETE_TRANSACTION_MESSAGE}

        normalized["summary"]["total"] = total
        if normalized["summary"]["subtotal"] is None:
            self._fill_item_subtotals(normalized)
            item_subtotal = self._calculate_items_subtotal(normalized)
            normalized["summary"]["subtotal"] = item_subtotal if item_subtotal is not None else total
        normalized["status"] = "success"
        normalized["manual_total_input"] = manual_total_input
        if manual_total_input:
            normalized["message"] = MANUAL_TOTAL_MESSAGE

        target_upload_date = upload_date or today_local_date(self.timezone)
        if normalized["transaction"]["date"] is None:
            normalized["transaction"]["date"] = target_upload_date

        return self._store_transaction(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            image_path=image_path,
            normalized=normalized,
            upload_date=target_upload_date,
            manual_total_input=manual_total_input,
        )

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
            "manual_total_input": bool(payload.get("manual_total_input", False)),
        }

    def _store_transaction(
        self,
        telegram_user_id: int,
        telegram_username: str | None,
        image_path: str,
        normalized: dict[str, Any],
        upload_date: date,
        manual_total_input: bool,
    ) -> dict[str, Any]:
        receipt_date = normalized["transaction"]["date"] or upload_date
        normalized["transaction"]["date"] = receipt_date
        receipt_time = normalized["transaction"]["time"]
        upload_time = now_local_time(self.timezone)
        store_name = normalized["store"]["name"] or DEFAULT_STORE_NAME
        total = normalized["summary"]["total"]
        if total is None:
            return {"status": "failed", "message": INCOMPLETE_TRANSACTION_MESSAGE}

        transaction = self.repository.create_transaction(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            store_name=store_name,
            transaction_date=upload_date,
            transaction_time=receipt_time,
            total=total,
            status="success",
            image_path=image_path,
            raw_json=normalized,
            items=normalized["items"],
        )

        return {
            "status": "success",
            "transaction_id": transaction.id,
            "store_name": store_name,
            "date": format_date_id(upload_date, upload_time),
            "receipt_date": format_date_id(receipt_date, receipt_time),
            "total": total,
            "message": normalized.get("message"),
            "manual_total_input": manual_total_input,
        }

    def _apply_defaults(self, normalized: dict[str, Any]) -> None:
        if not normalized["store"]["name"]:
            normalized["store"]["name"] = DEFAULT_STORE_NAME

        for item in normalized["items"]:
            quantity = item.get("quantity")
            if quantity is None or quantity <= 0:
                item["quantity"] = 1.0

    def _has_minimum_transaction_data(self, normalized: dict[str, Any]) -> bool:
        named_items = [item for item in normalized["items"] if item.get("name")]
        if not named_items:
            return False

        has_item_price = any(
            item.get("subtotal") is not None or item.get("unit_price") is not None
            for item in named_items
        )
        if has_item_price:
            return True

        return normalized["summary"]["total"] is not None

    def _fill_missing_totals(self, normalized: dict[str, Any]) -> None:
        self._fill_item_subtotals(normalized)
        item_subtotal = self._calculate_items_subtotal(normalized)
        summary = normalized["summary"]

        if summary["subtotal"] is None and item_subtotal is not None:
            summary["subtotal"] = item_subtotal

        if summary["total"] is None:
            base_subtotal = summary["subtotal"] if summary["subtotal"] is not None else item_subtotal
            if base_subtotal is None:
                return

            summary["total"] = (
                base_subtotal
                - (summary["discount"] or 0)
                + (summary["tax"] or 0)
                + (summary["service_charge"] or 0)
            )

    @staticmethod
    def _fill_item_subtotals(normalized: dict[str, Any]) -> None:
        """Fill in missing item subtotals from unit_price * quantity (mutation)."""
        for item in normalized["items"]:
            if not item.get("name"):
                continue
            if item.get("subtotal") is None and item.get("unit_price") is not None:
                quantity = item.get("quantity") or 1.0
                item["subtotal"] = int(round(item["unit_price"] * quantity))

    def _calculate_items_subtotal(self, normalized: dict[str, Any]) -> int | None:
        """Pure calculation: sum existing item subtotals without mutation."""
        total = 0
        has_value = False
        for item in normalized["items"]:
            if not item.get("name"):
                continue

            line_subtotal = item.get("subtotal")
            if line_subtotal is None:
                continue

            total += line_subtotal
            has_value = True

        return total if has_value else None

    def _calculate_expected_total(self, normalized: dict[str, Any]) -> int | None:
        subtotal_from_items = self._calculate_items_subtotal(normalized)
        if subtotal_from_items is None:
            return None

        summary = normalized["summary"]
        return (
            subtotal_from_items
            - (summary["discount"] or 0)
            + (summary["tax"] or 0)
            + (summary["service_charge"] or 0)
        )

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
        if quantity is not None and quantity <= 0:
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
