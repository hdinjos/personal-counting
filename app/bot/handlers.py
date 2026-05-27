from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
        
        text = messages.format_last_transactions(report)
        transactions = report.get("transactions", [])
        
        reply_markup = None
        if transactions:
            keyboard = []
            row = []
            for tx in transactions:
                row.append(InlineKeyboardButton(f"🗑 Hapus #{tx['id']}", callback_data=f"del_prompt_{tx['id']}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup)

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
            normalized = await asyncio.to_thread(self.transaction_service.normalize_extraction, extracted)
            
            if normalized["status"] == "failed":
                await update.message.reply_text(messages.FAILED_RECEIPT_MESSAGE)
                return

            upload_date = today_local_date(self.timezone)
            receipt_date = normalized["transaction"]["date"] or upload_date
            
            result_preview = {
                "status": normalized["status"],
                "store_name": normalized["store"]["name"],
                "date": upload_date.strftime("%Y-%m-%d"),
                "total": normalized["summary"]["total"],
            }
            
            context.user_data["pending_receipt"] = {
                "telegram_user_id": user_id,
                "telegram_username": username,
                "image_path": str(destination),
                "normalized": normalized
            }

            keyboard = [
                [
                    InlineKeyboardButton("✅ Simpan", callback_data="save_yes"),
                    InlineKeyboardButton("❌ Batal", callback_data="save_no")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                messages.format_save_confirmation(result_preview),
                reply_markup=reply_markup
            )

        except Exception:
            logger.exception("Failed to process receipt photo")
            await update.message.reply_text(messages.FAILED_RECEIPT_MESSAGE)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "save_yes":
            pending = context.user_data.get("pending_receipt")
            if not pending:
                await query.edit_message_text("Sesi penyimpanan telah kedaluwarsa atau sudah disimpan.")
                return
            
            result = await asyncio.to_thread(
                self.transaction_service.store_normalized,
                pending["telegram_user_id"],
                pending["telegram_username"],
                pending["image_path"],
                pending["normalized"]
            )
            context.user_data.pop("pending_receipt", None)
            await query.edit_message_text(messages.format_transaction_result(result))

        elif data == "save_no":
            context.user_data.pop("pending_receipt", None)
            await query.edit_message_text("Penyimpanan transaksi dibatalkan.")
            
        elif data.startswith("del_prompt_"):
            tx_id = data.split("_")[2]
            keyboard = [
                [
                    InlineKeyboardButton("✅ Ya, Hapus", callback_data=f"del_confirm_{tx_id}"),
                    InlineKeyboardButton("❌ Batal", callback_data=f"del_cancel_{tx_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"Anda yakin ingin menghapus transaksi #{tx_id}?",
                reply_markup=reply_markup
            )

        elif data.startswith("del_confirm_"):
            tx_id = int(data.split("_")[2])
            success = await asyncio.to_thread(
                self.report_service.repository.delete_transaction,
                update.effective_user.id,
                tx_id
            )
            if success:
                await query.edit_message_text(f"Transaksi #{tx_id} berhasil dihapus.")
            else:
                await query.edit_message_text(f"Transaksi #{tx_id} gagal dihapus (tidak ditemukan).")

        elif data.startswith("del_cancel_"):
            await query.edit_message_text("Penghapusan transaksi dibatalkan.")

