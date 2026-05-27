from __future__ import annotations

from app.utils.money import format_rupiah

START_MESSAGE = (
    "Halo, saya bot pencatat pengeluaran.\n"
    "Kirim foto struk belanja, lalu saya bantu simpan transaksinya."
)

HELP_MESSAGE = (
    "Perintah yang tersedia:\n"
    "/start\n"
    "/help\n"
    "/laporan_hari_ini\n"
    "/laporan_bulan_ini\n"
    "/transaksi_terakhir\n\n"
    "Kirim foto struk kapan saja untuk dicatat."
)

FAILED_RECEIPT_MESSAGE = (
    "Maaf, struk belum bisa dibaca.\n"
    "Silakan coba foto ulang dengan pencahayaan lebih jelas."
)


def format_transaction_result(result: dict) -> str:
    status = result.get("status", "failed")
    if status == "success":
        return (
            "Struk berhasil disimpan.\n\n"
            f"Toko: {result.get('store_name') or '-'}\n"
            f"Tanggal: {result.get('date') or '-'}\n"
            f"Total: {format_rupiah(result.get('total'))}\n"
            "Status: success"
        )

    if status == "partial":
        return (
            "Struk berhasil dibaca sebagian.\n\n"
            f"Toko: {result.get('store_name') or '-'}\n"
            f"Tanggal: {result.get('date') or '-'}\n"
            f"Total: {format_rupiah(result.get('total'))}\n"
            "Status: partial\n\n"
            "Beberapa informasi mungkin tidak terbaca."
        )

    return FAILED_RECEIPT_MESSAGE


def format_daily_report(report: dict) -> str:
    if report["count"] == 0:
        return "Belum ada pengeluaran hari ini."

    return (
        f"Laporan harian {report['date']}:\n"
        f"Total transaksi: {report['count']}\n"
        f"Total pengeluaran: {format_rupiah(report['total'])}"
    )


def format_monthly_report(report: dict) -> str:
    if report["count"] == 0:
        return "Belum ada pengeluaran bulan ini."

    return (
        f"Laporan bulanan {report['month']}:\n"
        f"Total transaksi: {report['count']}\n"
        f"Total pengeluaran: {format_rupiah(report['total'])}"
    )


def format_last_transactions(report: dict) -> str:
    transactions = report.get("transactions", [])
    if not transactions:
        return "Belum ada transaksi."

    lines = ["5 transaksi terakhir:"]
    for tx in transactions:
        lines.append(
            f"#{tx['id']} | {tx['date']} | {tx['store_name']} | {format_rupiah(tx['total'])} ({tx['status']})"
        )
    lines.append("\nKlik tombol di bawah ini untuk menghapus transaksi tertentu:")
    return "\n".join(lines)

def format_save_confirmation(result: dict) -> str:
    status = result.get("status", "failed")
    if status == "failed":
        return FAILED_RECEIPT_MESSAGE

    text = (
        "🔍 **Hasil Ekstraksi Struk**\n\n"
        f"Toko: {result.get('store_name') or '-'}\n"
        f"Tanggal: {result.get('date') or '-'}\n"
        f"Total: {format_rupiah(result.get('total'))}\n"
        f"Status: {status}\n\n"
        "Apakah Anda ingin menyimpan transaksi ini?"
    )
    return text

