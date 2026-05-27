# Expense Agent (MVP)

Telegram Bot untuk mencatat pengeluaran dari foto struk dengan extractor AI lokal `llama.cpp` (`llama-server` OpenAI-compatible).

## Fitur MVP
- Command bot: `/start`, `/help`, `/laporan_hari_ini`, `/laporan_bulan_ini`, `/transaksi_terakhir`
- Upload foto struk ke Telegram
- Simpan foto ke folder `uploads/`
- Ekstraksi data struk via endpoint lokal `http://localhost:8000/v1/chat/completions`
- Validasi + normalisasi JSON hasil ekstraksi
- Simpan transaksi ke SQLite
- Laporan pengeluaran harian dan bulanan

## Dokumentasi
- Panduan produk / operasional: [docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md)
- Panduan teknis llama.cpp: [docs/llama-cpp.md](docs/llama-cpp.md)
- Panduan kontribusi developer: [CONTRIBUTING.md](CONTRIBUTING.md)
- Konteks implementasi historis: [AGENTS.md](AGENTS.md)
- Dokumentasi resmi llama.cpp: [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)

## Struktur
Struktur folder mengikuti spesifikasi Anda:

```text
expense-agent/
├── app/
├── docs/
├── uploads/
├── tests/
├── CONTRIBUTING.md
├── .env.example
├── requirements.txt
├── README.md
└── run.py
```

## Setup
1. Masuk ke direktori proyek:
   ```bash
   cd expense-agent
   ```
2. Buat virtual env dan install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Siapkan env:
   ```bash
   cp .env.example .env
   ```
4. Isi `TELEGRAM_BOT_TOKEN` pada `.env`.
5. Pastikan `llama-server` lokal Anda aktif pada `http://localhost:8000/v1`.

Konfigurasi model Unsloth (`unsloth/Qwen3-VL-2B-Instruct-GGUF`) dan contoh command `llama-server` ada di [docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md).

## Menjalankan bot
```bash
python run.py
```

## Testing
```bash
pytest
```

## Catatan Integrasi llama.cpp
- Tidak menggunakan OpenAI cloud API
- Tidak menggunakan Ollama
- Request AI diarahkan ke `LLAMACPP_BASE_URL`
- Field `model` selalu dikirim menggunakan `LLAMACPP_MODEL` (default: `local-qwen3-vl`)

