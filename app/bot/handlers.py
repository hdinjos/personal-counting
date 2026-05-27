from __future__ import annotations

import asyncio
import logging
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
        upload_dir: Path,
        timezone: str = "Asia/Jakarta",
    ) -> None:
        self.transaction_service = transaction_service
        self.report_service = report_service
        self.extractor = extractor
        self.upload_dir = upload_dir
        self.timezone = timezone

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message:
            await update.message.reply_text(messages.START_MESSAGE)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message:
            await update.message.reply_text(messages.HELP_MESSAGE)

    async def laporan_hari_ini(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        today = today_local_date(self.timezone)
        report = await asyncio.to_thread(
            self.report_service.get_daily_report,
            update.effective_user.id,
            today,
        )
        await update.message.reply_text(messages.format_daily_report(report))

    async def laporan_bulan_ini(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
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
        if not update.message or not update.effective_user:
            return

        report = await asyncio.to_thread(
            self.report_service.get_last_transactions,
            update.effective_user.id,
            5,
        )
        await update.message.reply_text(messages.format_last_transactions(report))

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not update.message.photo:
            return

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        user_id = update.effective_user.id
        username = update.effective_user.username
        timestamp = int(datetime.now().timestamp() * 1000)
        filename = f"{user_id}_{timestamp}.jpg"
        destination = self.upload_dir / filename

        try:
            await update.message.reply_text("Sedang memproses struk...")

            largest_photo = update.message.photo[-1]
            telegram_file = await context.bot.get_file(largest_photo.file_id)
            await telegram_file.download_to_drive(custom_path=str(destination))

            extracted = await asyncio.to_thread(self.extractor.extract, str(destination))
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

