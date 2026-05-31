from __future__ import annotations

from app.utils.money import format_rupiah

START_MESSAGE = (
    "Halo, saya bot pencatat pengeluaran.\n"
    "Kirim foto struk atau voice note transaksi, lalu saya bantu simpan transaksinya."
)

HELP_MESSAGE = (
    "Perintah yang tersedia:\n"
    "/start\n"
    "/help\n"
    "/laporan_hari_ini\n"
    "/laporan_bulan_ini\n"
    "/transaksi_terakhir\n"
    "/rekap\n"
    "/batal (batalkan input total manual)\n\n"
    "Kirim foto struk atau voice note kapan saja untuk dicatat."
)

FAILED_TRANSACTION_MESSAGE = (
    "Maaf, transaksi belum bisa diproses.\n"
    "Silakan upload ulang struk atau kirim voice note kembali."
)

# Backward compatible alias.
FAILED_RECEIPT_MESSAGE = FAILED_TRANSACTION_MESSAGE


def format_confirmation_request(data: dict) -> str:
    """Format extracted data for user confirmation before saving."""
    lines = ["📋 Data transaksi yang terbaca:\n"]
    lines.append(f"🏪 Toko: {data.get('store_name') or '-'}")
    lines.append(f"📅 Tanggal: {data.get('date') or '-'}")
    if data.get("receipt_date") and data.get("receipt_date") != data.get("date"):
        lines.append(f"🧾 Tanggal struk: {data['receipt_date']}")
    lines.append(f"💰 Total: {format_rupiah(data.get('total'))}")

    items = data.get("items", [])
    if items:
        lines.append(f"\n📝 Item ({len(items)}):")
        for item in items[:10]:
            name = item.get("name") or "-"
            subtotal = format_rupiah(item.get("subtotal")) if item.get("subtotal") else ""
            qty = item.get("quantity") or 1
            lines.append(f"  • {name} x{qty} {subtotal}")
        if len(items) > 10:
            lines.append(f"  ... dan {len(items) - 10} item lainnya")

    lines.append("\n✅ Balas *ya* / *simpan* untuk menyimpan")
    lines.append("❌ Balas *batal* untuk membatalkan")
    return "\n".join(lines)


def format_total_confirmation_request(result: dict) -> str:
    return (
        "Data transaksi terbaca, tetapi total belum konsisten.\n\n"
        f"Toko: {result.get('store_name') or '-'}\n"
        f"Tanggal: {result.get('date') or '-'}\n"
        f"Total terdeteksi: {format_rupiah(result.get('total'))}\n"
        f"Total hitung item: {format_rupiah(result.get('expected_total'))}\n\n"
        "Balas dengan nominal total akhir (angka saja), atau kirim `batal` / `/batal` untuk membatalkan transaksi ini."
    )


def format_transaction_result(result: dict) -> str:
    status = result.get("status", "failed")

    if status == "success":
        details = [
            "Transaksi berhasil disimpan.\n",
            f"Toko: {result.get('store_name') or '-'}",
            f"Tanggal: {result.get('date') or '-'}",
            f"Total: {format_rupiah(result.get('total'))}",
            "Status: success",
        ]
        if result.get("manual_total_input"):
            details.append("Keterangan: total transaksi diinput manual oleh user.")
        return "\n".join(details)

    if status == "partial":
        return (
            "Transaksi berhasil dibaca sebagian.\n\n"
            f"Toko: {result.get('store_name') or '-'}\n"
            f"Tanggal: {result.get('date') or '-'}\n"
            f"Total: {format_rupiah(result.get('total'))}\n"
            "Status: partial\n\n"
            "Beberapa informasi mungkin tidak terbaca."
        )

    if status == "needs_total_confirmation":
        return format_total_confirmation_request(result)

    message = result.get("message")
    if message:
        return f"Transaksi gagal diproses.\n{message}"

    return FAILED_TRANSACTION_MESSAGE


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
            f"- {tx['date']} | {tx['store_name']} | {format_rupiah(tx['total'])} ({tx['status']})"
        )
    return "\n".join(lines)
