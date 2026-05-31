from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.bot import messages
from app.services.report_service import ReportService
from app.services.transaction_service import TransactionService
from app.utils.dates import format_date_id, month_from_date, now_local_time, parse_receipt_date, today_local_date
from app.utils.money import normalize_amount
from app.utils.rate_limiter import RateLimiter
from app.utils.health import check_all_services

logger = logging.getLogger(__name__)

PENDING_TOTAL_KEY = "pending_total_confirmation"
PENDING_CONFIRMATION_KEY = "pending_confirmation"
PENDING_TOTAL_TIMEOUT_SECONDS = 600
CANCEL_KEYWORDS = {"batal", "/batal", "tidak", "no", "cancel"}
CONFIRM_KEYWORDS = {"ya", "y", "simpan", "ok", "oke", "yes"}
TELEGRAM_MAX_MESSAGE_LENGTH = 4096


class BotHandlers:
    def __init__(
        self,
        transaction_service: TransactionService,
        report_service: ReportService,
        extractor,
        voice_transcriber,
        upload_dir: Path,
        ocr_engine=None,
        timezone: str = "Asia/Jakarta",
        allowed_user_ids: list[int] | None = None,
        enable_user_whitelist: bool = False,
    ) -> None:
        self.transaction_service = transaction_service
        self.report_service = report_service
        self.extractor = extractor
        self.voice_transcriber = voice_transcriber
        self.upload_dir = upload_dir
        self.ocr_engine = ocr_engine
        self.timezone = timezone
        self.allowed_user_ids = allowed_user_ids or []
        self.enable_user_whitelist = enable_user_whitelist
        self.rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

        if self.enable_user_whitelist and not self.allowed_user_ids:
            logger.warning("User whitelist is enabled but ALLOWED_USER_IDS is empty. All users will be blocked.")

    def _is_allowed(self, user_id: int) -> bool:
        if not self.enable_user_whitelist:
            return True

        if not self.allowed_user_ids:
            return False

        return user_id in self.allowed_user_ids

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return
        await update.message.reply_text(messages.START_MESSAGE)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return
        await update.message.reply_text(messages.HELP_MESSAGE)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        from app.config import get_settings
        settings = get_settings()
        results = await check_all_services(settings.llamacpp_base_url, settings.whisper_server_base_url)

        lines = ["Status server AI:"]
        for name, healthy in results.items():
            icon = "✅" if healthy else "❌"
            lines.append(f"  {icon} {name}")
        await update.message.reply_text("\n".join(lines))

    async def laporan_hari_ini(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        today = today_local_date(self.timezone)
        report = await asyncio.to_thread(
            self.report_service.get_daily_report,
            update.effective_user.id,
            today,
        )
        await self._safe_reply_text(update.message, messages.format_daily_report(report))

    async def laporan_bulan_ini(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        today = today_local_date(self.timezone)
        year, month = month_from_date(today)
        report = await asyncio.to_thread(
            self.report_service.get_monthly_report,
            update.effective_user.id,
            year,
            month,
        )
        await self._safe_reply_text(update.message, messages.format_monthly_report(report))

    async def transaksi_terakhir(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        report = await asyncio.to_thread(
            self.report_service.get_last_transactions,
            update.effective_user.id,
            5,
        )
        await self._safe_reply_text(update.message, messages.format_last_transactions(report))

    async def rekap_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        await update.message.reply_text("Membuat rekap PDF...")
        today = today_local_date(self.timezone)
        user_id = update.effective_user.id

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        filename = f"rekap_{user_id}_{today.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}.pdf"
        output_path = self.upload_dir / filename

        try:
            await asyncio.to_thread(
                self.report_service.generate_daily_pdf,
                user_id,
                today,
                str(output_path),
            )

            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, filename=f"Rekap_Pengeluaran_{today.strftime('%Y%m%d')}.pdf")
        except Exception:
            logger.exception("Failed to generate PDF")
            await update.message.reply_text("Terjadi kesalahan saat membuat laporan PDF.")
        finally:
            if output_path.exists():
                output_path.unlink(missing_ok=True)

    async def batal_pending_total(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        pending = self._get_pending_confirmation(context)
        if not pending:
            await update.message.reply_text("Tidak ada transaksi yang menunggu konfirmasi.")
            return

        self._clear_pending_confirmation(context)
        await update.message.reply_text("Transaksi dibatalkan. Data tidak disimpan.")

    async def handle_pending_total_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        pending = self._get_pending_confirmation(context)
        if not pending:
            return

        raw_text = (update.message.text or "").strip()
        lowered = raw_text.lower()

        # Check expiry
        if self._is_pending_expired(pending):
            self._clear_pending_confirmation(context)
            await update.message.reply_text(
                "Konfirmasi sudah kedaluwarsa. Silakan kirim ulang struk atau voice note."
            )
            return

        # Cancel
        if lowered in CANCEL_KEYWORDS:
            self._clear_pending_confirmation(context)
            await update.message.reply_text("Transaksi dibatalkan. Data tidak disimpan.")
            return

        pending_type = pending.get("type")

        # New confirmation flow: user confirms extracted data
        if pending_type == "save_transaction":
            if lowered in CONFIRM_KEYWORDS:
                await self._save_pending_transaction(update, context, pending)
            else:
                await update.message.reply_text(
                    "Balas *ya* / *simpan* untuk menyimpan, atau *batal* untuk membatalkan.",
                    parse_mode="Markdown",
                )
            return

        # Manual total input (total inconsistent with items)
        if pending_type == "manual_total":
            total = normalize_amount(raw_text)
            if total is None or total <= 0:
                await update.message.reply_text(
                    "Nominal tidak valid. Kirim angka total yang benar, atau *batal* untuk membatalkan.",
                    parse_mode="Markdown",
                )
                return

            upload_date = parse_receipt_date(pending.get("upload_date"))
            try:
                result = await asyncio.to_thread(
                    self.transaction_service.store_confirmed_transaction,
                    update.effective_user.id,
                    update.effective_user.username,
                    pending["image_path"],
                    pending["normalized_payload"],
                    total,
                    upload_date,
                )
            except Exception:
                logger.exception("Failed to save with manual total")
                await update.message.reply_text("Terjadi kesalahan saat menyimpan transaksi.")
                return

            self._clear_pending_confirmation(context)
            await update.message.reply_text(messages.format_transaction_result(result))
            return

        # Legacy: manual total input (needs_total_confirmation)
        total = normalize_amount(raw_text)
        if total is None or total <= 0:
            await update.message.reply_text(
                "Nominal tidak valid. Kirim angka total akhir transaksi, atau `batal` / `/batal` untuk membatalkan."
            )
            return

        upload_date = parse_receipt_date(pending.get("upload_date"))
        try:
            result = await asyncio.to_thread(
                self.transaction_service.store_confirmed_transaction,
                update.effective_user.id,
                update.effective_user.username,
                pending["image_path"],
                pending["normalized_payload"],
                total,
                upload_date,
            )
        except Exception:
            logger.exception("Failed to confirm manual total")
            await update.message.reply_text("Terjadi kesalahan saat menyimpan transaksi. Silakan coba lagi.")
            return

        self._clear_pending_confirmation(context)
        await update.message.reply_text(messages.format_transaction_result(result))

    async def _save_pending_transaction(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, pending: dict[str, Any]
    ) -> None:
        """Save the pending transaction after user confirms. Check total consistency first."""
        upload_date = parse_receipt_date(pending.get("upload_date"))
        normalized = pending["normalized_payload"]
        normalized["status"] = "success"
        total = normalized["summary"]["total"]

        # Check if total is consistent with items
        expected_total = self.transaction_service._calculate_expected_total(normalized)
        if expected_total is not None and expected_total != total:
            # Switch to manual total input mode
            pending["type"] = "manual_total"
            self._set_pending_confirmation(context, pending)
            await update.message.reply_text(
                f"⚠️ Total transaksi ({messages.format_rupiah(total)}) tidak konsisten "
                f"dengan total item ({messages.format_rupiah(expected_total)}).\n\n"
                "Balas dengan nominal total yang benar (angka saja), atau *batal* untuk membatalkan.",
                parse_mode="Markdown",
            )
            return

        try:
            result = await asyncio.to_thread(
                self.transaction_service.store_confirmed_transaction,
                update.effective_user.id,
                update.effective_user.username,
                pending["image_path"],
                normalized,
                total,
                upload_date,
                False,
            )
        except Exception:
            logger.exception("Failed to save confirmed transaction")
            await update.message.reply_text("Terjadi kesalahan saat menyimpan transaksi. Silakan coba lagi.")
            return

        self._clear_pending_confirmation(context)
        await update.message.reply_text(messages.format_transaction_result(result))

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        if not self.rate_limiter.is_allowed(update.effective_user.id):
            await update.message.reply_text("Terlalu banyak request. Coba lagi dalam 1 menit.")
            return

        is_photo = bool(update.message.photo)
        is_document = bool(update.message.document)

        if not is_photo and not is_document:
            return

        if is_document and not (update.message.document.mime_type and update.message.document.mime_type.startswith("image/")):
            return

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        user_id = update.effective_user.id

        if is_photo:
            telegram_file_id = update.message.photo[-1].file_id
        else:
            telegram_file_id = update.message.document.file_id

        ext = ".jpg"
        if is_document and update.message.document.file_name:
            ext = Path(update.message.document.file_name).suffix or ".jpg"

        temp_filename = f"{user_id}_{uuid.uuid4().hex}{ext}"
        temp_path = self.upload_dir / temp_filename

        try:
            await update.message.reply_text("Sedang memproses struk...")

            telegram_file = await context.bot.get_file(telegram_file_id)
            await telegram_file.download_to_drive(custom_path=str(temp_path))

            if self.ocr_engine:
                # PaddleOCR / GLM-OCR path
                ocr_text = await asyncio.to_thread(self.ocr_engine.extract_text, str(temp_path))
                if not ocr_text:
                    await update.message.reply_text(messages.FAILED_RECEIPT_MESSAGE)
                    return
                extracted = await self.extractor.extract(ocr_text=ocr_text)
            else:
                # VLM path: extractor reads image directly
                extracted = await self.extractor.extract(image_path=str(temp_path))
            normalized = self.transaction_service.normalize_extraction(extracted or {})

            if normalized["status"] == "failed":
                await update.message.reply_text(messages.FAILED_RECEIPT_MESSAGE)
                return

            self.transaction_service._apply_defaults(normalized)
            self.transaction_service._fill_missing_totals(normalized)
            total = normalized["summary"]["total"]

            if total is None or total <= 0:
                await update.message.reply_text(messages.FAILED_RECEIPT_MESSAGE)
                return

            upload_date = today_local_date(self.timezone)
            receipt_date = normalized["transaction"]["date"] or upload_date
            normalized["transaction"]["date"] = receipt_date
            upload_time = now_local_time(self.timezone)

            confirmation_data = {
                "store_name": normalized["store"]["name"],
                "date": format_date_id(upload_date, upload_time),
                "receipt_date": format_date_id(receipt_date, normalized["transaction"]["time"]),
                "total": total,
                "items": normalized["items"],
            }

            pending = {
                "type": "save_transaction",
                "image_path": telegram_file_id,
                "normalized_payload": normalized,
                "upload_date": upload_date.strftime("%Y-%m-%d"),
                "created_at_ts": datetime.now().timestamp(),
            }
            self._set_pending_confirmation(context, pending)
            await update.message.reply_text(messages.format_confirmation_request(confirmation_data), parse_mode="Markdown")
        except Exception:
            logger.exception("Failed to process receipt photo")
            await update.message.reply_text(messages.FAILED_RECEIPT_MESSAGE)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        if not self.rate_limiter.is_allowed(update.effective_user.id):
            await update.message.reply_text("Terlalu banyak request. Coba lagi dalam 1 menit.")
            return

        if not update.message.voice:
            return

        if not self.voice_transcriber:
            await update.message.reply_text("Fitur suara belum dikonfigurasi.")
            return

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        user_id = update.effective_user.id
        telegram_file_id = update.message.voice.file_id

        temp_filename = f"{user_id}_{uuid.uuid4().hex}.ogg"
        temp_path = self.upload_dir / temp_filename

        try:
            msg = await update.message.reply_text("Mendengarkan suara...")

            telegram_file = await context.bot.get_file(telegram_file_id)
            await telegram_file.download_to_drive(custom_path=str(temp_path))

            await msg.edit_text("Mengubah suara ke teks...")
            transcribed_text = await self.voice_transcriber.transcribe(str(temp_path))

            if not transcribed_text:
                await msg.edit_text("Maaf, tidak dapat mendengar atau mengenali pesan suara tersebut.")
                return

            await msg.edit_text(f"Pesan dikenali: \"{transcribed_text}\"\nSedang memproses transaksi...")

            extracted = await self.extractor.extract(text_input=transcribed_text)
            normalized = self.transaction_service.normalize_extraction(extracted or {})

            try:
                await msg.delete()
            except Exception:
                pass

            if normalized["status"] == "failed":
                await update.message.reply_text(messages.FAILED_RECEIPT_MESSAGE)
                return

            self.transaction_service._apply_defaults(normalized)
            self.transaction_service._fill_missing_totals(normalized)
            total = normalized["summary"]["total"]

            if total is None or total <= 0:
                await update.message.reply_text(messages.FAILED_RECEIPT_MESSAGE)
                return

            upload_date = today_local_date(self.timezone)
            upload_time = now_local_time(self.timezone)
            user_said_date = normalized["transaction"]["date"] is not None
            receipt_date = normalized["transaction"]["date"] or upload_date
            normalized["transaction"]["date"] = receipt_date

            date_display = format_date_id(upload_date, upload_time)
            receipt_date_display = (
                format_date_id(receipt_date, normalized["transaction"]["time"])
                if user_said_date
                else date_display
            )

            confirmation_data = {
                "store_name": normalized["store"]["name"],
                "date": date_display,
                "receipt_date": receipt_date_display,
                "total": total,
                "items": normalized["items"],
            }

            pending = {
                "type": "save_transaction",
                "image_path": telegram_file_id,
                "normalized_payload": normalized,
                "upload_date": upload_date.strftime("%Y-%m-%d"),
                "created_at_ts": datetime.now().timestamp(),
            }
            self._set_pending_confirmation(context, pending)
            await update.message.reply_text(messages.format_confirmation_request(confirmation_data), parse_mode="Markdown")
        except Exception:
            logger.exception("Failed to process voice note")
            await update.message.reply_text("Maaf, terjadi kesalahan saat memproses pesan suara.")
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    @staticmethod
    def _set_pending_confirmation(context: ContextTypes.DEFAULT_TYPE, pending: dict[str, Any]) -> None:
        context.user_data[PENDING_TOTAL_KEY] = pending

    @staticmethod
    def _clear_pending_confirmation(context: ContextTypes.DEFAULT_TYPE) -> None:
        context.user_data.pop(PENDING_TOTAL_KEY, None)

    @staticmethod
    def _get_pending_confirmation(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
        pending = context.user_data.get(PENDING_TOTAL_KEY)
        if isinstance(pending, dict):
            return pending
        return None

    @staticmethod
    def _is_pending_expired(pending: dict[str, Any]) -> bool:
        created_at_ts = pending.get("created_at_ts")
        if not isinstance(created_at_ts, (int, float)):
            return True
        return (datetime.now().timestamp() - float(created_at_ts)) > PENDING_TOTAL_TIMEOUT_SECONDS

    @staticmethod
    async def _safe_reply_text(message, text: str) -> None:
        """Reply with truncation to respect Telegram's 4096-character limit."""
        if len(text) <= TELEGRAM_MAX_MESSAGE_LENGTH:
            await message.reply_text(text)
        else:
            truncated = text[: TELEGRAM_MAX_MESSAGE_LENGTH - 30] + "\n\n... (pesan terpotong)"
            await message.reply_text(truncated)
