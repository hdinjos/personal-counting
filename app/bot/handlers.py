from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from app.bot import messages
from app.services.report_service import ReportService
from app.services.transaction_service import TransactionService
from app.utils.dates import month_from_date, today_local_date

logger = logging.getLogger(__name__)


class BotHandlers:
    def __init__(
        self,
        transaction_service: TransactionService,
        report_service: ReportService,
        extractor,
        voice_transcriber,
        upload_dir: Path,
        timezone: str = "Asia/Jakarta",
        allowed_user_ids: list[int] | None = None,
        enable_user_whitelist: bool = False,
    ) -> None:
        self.transaction_service = transaction_service
        self.report_service = report_service
        self.extractor = extractor
        self.voice_transcriber = voice_transcriber
        self.upload_dir = upload_dir
        self.timezone = timezone
        self.allowed_user_ids = allowed_user_ids or []
        self.enable_user_whitelist = enable_user_whitelist

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

    async def laporan_hari_ini(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        today = today_local_date(self.timezone)
        report = await asyncio.to_thread(
            self.report_service.get_daily_report,
            update.effective_user.id,
            today,
        )
        await update.message.reply_text(messages.format_daily_report(report))

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
        await update.message.reply_text(messages.format_monthly_report(report))

    async def transaksi_terakhir(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        report = await asyncio.to_thread(
            self.report_service.get_last_transactions,
            update.effective_user.id,
            5,
        )
        await update.message.reply_text(messages.format_last_transactions(report))

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

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        is_photo = bool(update.message.photo)
        is_document = bool(update.message.document)

        if not is_photo and not is_document:
            return

        if is_document and not (update.message.document.mime_type and update.message.document.mime_type.startswith("image/")):
            return

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        user_id = update.effective_user.id
        username = update.effective_user.username

        ext = ".jpg"
        if is_document and update.message.document.file_name:
            ext = Path(update.message.document.file_name).suffix or ".jpg"

        filename = f"{user_id}_{uuid.uuid4().hex}{ext}"
        destination = self.upload_dir / filename

        try:
            await update.message.reply_text("Sedang memproses struk...")

            if is_photo:
                file_id = update.message.photo[-1].file_id
            else:
                file_id = update.message.document.file_id

            telegram_file = await context.bot.get_file(file_id)
            await telegram_file.download_to_drive(custom_path=str(destination))

            extracted = await self.extractor.extract(image_path=str(destination))
            result = await asyncio.to_thread(
                self.transaction_service.process_and_store,
                user_id,
                username,
                str(destination),
                extracted,
            )
            await update.message.reply_text(messages.format_transaction_result(result))
        except Exception:
            logger.exception("Failed to process receipt photo")
            await update.message.reply_text(messages.FAILED_RECEIPT_MESSAGE)

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not self._is_allowed(update.effective_user.id):
            return

        if not update.message.voice:
            return

        if not self.voice_transcriber:
            await update.message.reply_text("Fitur suara belum dikonfigurasi.")
            return

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        user_id = update.effective_user.id
        username = update.effective_user.username

        filename = f"{user_id}_{uuid.uuid4().hex}.ogg"
        destination = self.upload_dir / filename

        try:
            msg = await update.message.reply_text("Mendengarkan suara...")

            telegram_file = await context.bot.get_file(update.message.voice.file_id)
            await telegram_file.download_to_drive(custom_path=str(destination))

            await msg.edit_text("Mengubah suara ke teks...")
            transcribed_text = await self.voice_transcriber.transcribe(str(destination))

            if not transcribed_text:
                await msg.edit_text("Maaf, tidak dapat mendengar atau mengenali pesan suara tersebut.")
                return

            await msg.edit_text(f"Pesan dikenali: \"{transcribed_text}\"\nSedang memproses transaksi...")

            extracted = await self.extractor.extract(text_input=transcribed_text)
            result = await asyncio.to_thread(
                self.transaction_service.process_and_store,
                user_id,
                username,
                str(destination),
                extracted,
            )
            await msg.delete()
            await update.message.reply_text(messages.format_transaction_result(result))
        except Exception:
            logger.exception("Failed to process voice note")
            await update.message.reply_text("Maaf, terjadi kesalahan saat memproses pesan suara.")
