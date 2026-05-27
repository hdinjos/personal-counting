# Expense Agent (MVP)

Telegram Bot untuk mencatat pengeluaran dari foto struk dan voice note dengan extractor AI lokal `llama.cpp` (`llama-server` OpenAI-compatible) dan transkripsi suara via `whisper.cpp` `whisper-server`.

## Fitur MVP
- Command bot: `/start`, `/help`, `/laporan_hari_ini`, `/laporan_bulan_ini`, `/transaksi_terakhir`, `/rekap`
- Upload foto struk ke Telegram
- Kirim voice note transaksi ke Telegram
- Simpan file upload ke folder `uploads/`
- Ekstraksi data transaksi via endpoint lokal `http://localhost:8000/v1/chat/completions`
- Transkripsi voice note via endpoint lokal `http://127.0.0.1:8001/inference`
- Validasi + normalisasi JSON hasil ekstraksi
- Simpan transaksi ke SQLite
- Laporan pengeluaran harian dan bulanan
- Export rekap harian ke PDF

## Dokumentasi
- Panduan produk / operasional: [docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md)
- Panduan teknis llama.cpp: [docs/llama-cpp.md](docs/llama-cpp.md)
- Panduan teknis whisper.cpp: [docs/whisper-cpp.md](docs/whisper-cpp.md)
- Panduan kontribusi developer: [CONTRIBUTING.md](CONTRIBUTING.md)
- Konteks implementasi historis: [AGENTS.md](AGENTS.md)
- Dokumentasi resmi llama.cpp: [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)
- Dokumentasi resmi whisper.cpp: [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)

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
6. Pastikan `whisper-server` aktif, contoh:
   ```bash
   /home/hdinjos/Dev/whisper.cpp/build/bin/whisper-server \
     --host 127.0.0.1 \
     --port 8001 \
     --language id \
     --convert \
     --model /home/hdinjos/Dev/models/audio/ggml-small.bin
   ```

   Catatan: voice note Telegram berformat `.ogg`, jadi jalankan `whisper-server` dengan `--convert` dan pastikan `ffmpeg` terpasang.

Konfigurasi model Unsloth (`unsloth/Qwen3-VL-2B-Instruct-GGUF`) dan contoh command `llama-server` ada di [docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md).

## Menjalankan bot
```bash
python run.py
```

## Testing
```bash
pytest
```

## Catatan Integrasi AI Lokal
- Tidak menggunakan OpenAI cloud API
- Tidak menggunakan Ollama
- Request extractor diarahkan ke `LLAMACPP_BASE_URL`
- Field `model` extractor selalu dikirim menggunakan `LLAMACPP_MODEL` (default: `local-qwen3-vl`)
- Request transkripsi diarahkan ke `WHISPER_SERVER_BASE_URL + WHISPER_SERVER_INFERENCE_PATH`
