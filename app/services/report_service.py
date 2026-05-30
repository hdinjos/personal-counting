from __future__ import annotations

from datetime import date

from app.db.repositories import TransactionRepository
from app.utils.dates import format_date_id, format_month_id


class ReportService:
    def __init__(self, repository: TransactionRepository) -> None:
        self.repository = repository

    def get_daily_report(self, telegram_user_id: int, target_date: date) -> dict:
        transactions = self.repository.get_transactions_for_day(telegram_user_id, target_date)
        return {
            "date": format_date_id(target_date),
            "count": len(transactions),
            "total": sum(tx.total for tx in transactions),
        }

    def get_monthly_report(self, telegram_user_id: int, year: int, month: int) -> dict:
        transactions = self.repository.get_transactions_for_month(telegram_user_id, year, month)
        return {
            "month": format_month_id(year, month),
            "count": len(transactions),
            "total": sum(tx.total for tx in transactions),
        }

    def get_last_transactions(self, telegram_user_id: int, limit: int = 5) -> dict:
        transactions = self.repository.get_last_transactions(telegram_user_id, limit)
        formatted = [
            {
                "id": tx.id,
                "date": format_date_id(tx.transaction_date, tx.transaction_time),
                "store_name": tx.store_name or "-",
                "total": tx.total,
                "status": tx.status,
            }
            for tx in transactions
        ]
        return {"transactions": formatted}
    def generate_daily_pdf(self, telegram_user_id: int, target_date: date, output_path: str) -> None:
        from fpdf import FPDF
        
        transactions = self.repository.get_transactions_for_day(telegram_user_id, target_date)
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", size=16, style="B")
        pdf.cell(200, 10, txt=f"Laporan Transaksi Harian", ln=True, align="C")
        pdf.set_font("helvetica", size=12)
        pdf.cell(200, 10, txt=f"Tanggal: {format_date_id(target_date)}", ln=True, align="C")
        pdf.ln(10)

        pdf.set_font("helvetica", size=10, style="B")
        pdf.cell(10, 10, "No", border=1, align="C")
        pdf.cell(70, 10, "Toko/Keterangan", border=1)
        pdf.cell(30, 10, "Status", border=1, align="C")
        pdf.cell(40, 10, "Total", border=1, align="R")
        pdf.ln(10)

        pdf.set_font("helvetica", size=10)
        total_pengeluaran = 0
        for i, tx in enumerate(transactions, start=1):
            store_name = tx.store_name if tx.store_name else "-"
            # Basic sanitization to avoid fpdf latin-1 errors
            store_name = store_name.encode('latin-1', 'replace').decode('latin-1')
            
            pdf.cell(10, 10, str(i), border=1, align="C")
            pdf.cell(70, 10, store_name[:35], border=1)
            pdf.cell(30, 10, tx.status, border=1, align="C")
            pdf.cell(40, 10, f"Rp {tx.total:,}", border=1, align="R")
            pdf.ln(10)
            if tx.status == "success":
                total_pengeluaran += tx.total

        pdf.ln(5)
        pdf.set_font("helvetica", size=12, style="B")
        pdf.cell(110, 10, "Total Pengeluaran (Sukses):", border=0, align="R")
        pdf.cell(40, 10, f"Rp {total_pengeluaran:,}", border=0, align="R")
        
        pdf.output(output_path)
