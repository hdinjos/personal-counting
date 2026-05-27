# Product Guide - Expense Agent MVP

## 1) Tujuan Produk
Expense Agent adalah Telegram Bot untuk mencatat pengeluaran pribadi dari foto struk atau voice note transaksi, lalu menyajikannya sebagai laporan harian, bulanan, dan rekap PDF harian.

## 2) Flow Alur Produk (User Flow)
### A) Foto Struk
1. User mengirim foto struk ke bot Telegram.
2. Bot menyimpan foto ke folder `uploads/` dengan nama unik: `user_id_timestamp.jpg`.
3. Bot mengirim gambar ke model AI lokal `llama.cpp` (OpenAI-compatible API).
4. Model mengembalikan hasil ekstraksi JSON.
5. Sistem membersihkan output model dan parse JSON dengan aman.
6. Data divalidasi dan dinormalisasi.
7. Data transaksi disimpan ke SQLite.
8. Bot membalas hasil proses (`success`, `partial`, atau `failed`).

### B) Voice Note
1. User mengirim voice note ke bot Telegram.
2. Bot menyimpan audio `.ogg` ke `uploads/`.
3. Bot mengirim file audio ke endpoint lokal `whisper.cpp` `whisper-server`.
4. `whisper-server` mengembalikan teks transkripsi.
5. Teks hasil transkripsi dikirim ke model AI lokal `llama.cpp` untuk diekstrak menjadi JSON transaksi.
6. Data masuk pipeline validasi/normalisasi yang sama, lalu disimpan ke SQLite.
7. Bot mengirim status proses transaksi ke user.

### C) Laporan
User bisa melihat:
- `/laporan_hari_ini`
- `/laporan_bulan_ini`
- `/transaksi_terakhir`
- `/rekap` (mengirim file PDF rekap harian)

## 3) Cara Kerja Teknis (System Flow)
- **Transport**: Telegram Bot API (`python-telegram-bot`)
- **AI Extractor**: `LlamaCppReceiptExtractor`
- **Voice Transcriber**: `VoiceTranscriber` (HTTP client ke `whisper-server`, language default `id`)
- **Database**: SQLite via SQLAlchemy
- **Parser**: `json_utils` untuk menghapus code fence dan ekstrak JSON dari output campuran
- **PDF Report**: `report_service.generate_daily_pdf()` menggunakan `fpdf2`

### Integrasi AI Lokal
- Base URL extractor default: `http://localhost:8000/v1`
- Endpoint extractor: `POST /chat/completions`
- Base URL transcriber default: `http://127.0.0.1:8001`
- Endpoint transcriber default: `POST /inference` (`multipart/form-data`)
- Payload transkripsi mengirim field:
  - `file` (audio)
  - `language` (`id`)
  - `response_format` (`json`)
- Payload extractor bisa dua mode:
  - **Vision mode** (foto): text prompt + `image_url` data URL base64 (`data:image/jpeg;base64,...`)
  - **Text mode** (voice): text prompt + teks hasil transkripsi
- Model field extractor wajib dikirim dari `LLAMACPP_MODEL` (default `local-qwen3-vl`)

### Referensi Model & Dokumentasi
- Model Hugging Face (vision extractor): https://huggingface.co/unsloth/Qwen3-VL-2B-Instruct-GGUF
- Repositori resmi llama.cpp: https://github.com/ggml-org/llama.cpp
- Dokumentasi server llama.cpp (OpenAI-compatible API): https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Repositori resmi whisper.cpp: https://github.com/ggml-org/whisper.cpp
- Dokumentasi whisper-server: https://github.com/ggml-org/whisper.cpp/tree/master/examples/server

### Sinkronisasi Nama Model (`model` field)
- Di aplikasi, request extractor selalu mengirim `model` dari env `LLAMACPP_MODEL`.
- Agar konsisten, jalankan `llama-server` dengan `--alias local-qwen3-vl` (sesuai default `.env.example`).
- Jika Anda tidak memakai alias, ubah `LLAMACPP_MODEL` ke nama model yang benar-benar tersedia di endpoint `/v1/models`.

### Aturan Tanggal Transaksi
- `transaction_date` (kolom utama laporan) = **tanggal upload struk/voice**.
- Tanggal struk asli tetap disimpan di `raw_json.transaction.date`.
- Jika tanggal struk tidak terbaca, `raw_json.transaction.date` diisi tanggal upload.

## 4) Syarat yang Harus Dipenuhi
1. Python `3.11+`
2. Sistem bisa menjalankan `llama-server` lokal
3. Model multimodal `.gguf` + `mmproj` tersedia di lokal
4. Sistem bisa menjalankan `whisper-server` lokal
5. Model whisper (`ggml-small.bin` atau varian lain) tersedia di lokal
6. Telegram bot token aktif
7. Port `llama-server` sesuai `LLAMACPP_BASE_URL` di `.env`
8. Port/path `whisper-server` sesuai `WHISPER_SERVER_BASE_URL` + `WHISPER_SERVER_INFERENCE_PATH`
9. Dependency tambahan untuk fitur baru:
   - `fpdf2>=2.8.0`

## 5) Cara Menjalankan

### 5.1 Setup Project
```bash
cd expense-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Isi minimal `.env`:
- `TELEGRAM_BOT_TOKEN=...`
- `LLAMACPP_BASE_URL=http://localhost:8000/v1`
- `LLAMACPP_MODEL=local-qwen3-vl`
- `WHISPER_SERVER_BASE_URL=http://127.0.0.1:8001`
- `WHISPER_SERVER_INFERENCE_PATH=/inference`
- `WHISPER_LANGUAGE=id`
- `USE_DUMMY_EXTRACTOR=false`

### 5.2 Jalankan llama-server (model Unsloth)
**Opsi A - langsung dari Hugging Face (recommended)**
```bash
./llama-server \
  -hf unsloth/Qwen3-VL-2B-Instruct-GGUF:UD-Q4_K_XL \
  --alias local-qwen3-vl \
  --jinja \
  --ctx-size 8192 \
  --n-gpu-layers 99 \
  --flash-attn on \
  --top-p 0.8 \
  --top-k 20 \
  --temp 0.7 \
  --min-p 0.0 \
  --presence-penalty 1.5 \
  --port 8000
```

Catatan: pada dokumentasi server `llama.cpp`, parameter `-hf/--hf-repo` otomatis mengunduh `mmproj` jika tersedia (dapat dinonaktifkan dengan `--no-mmproj`).

**Opsi B - file lokal (.gguf + mmproj)**
```bash
./llama-server \
  --model ~/Dev/models/Qwen3-VL-2B-Instruct-BF16.gguf \
  --mmproj ~/Dev/models/mmproj-BF16.gguf \
  --alias local-qwen3-vl \
  --jinja \
  --ctx-size 8192 \
  --n-gpu-layers 99 \
  --flash-attn on \
  --top-p 0.8 \
  --top-k 20 \
  --temp 0.7 \
  --min-p 0.0 \
  --presence-penalty 1.5 \
  --port 8000
```

### 5.3 Jalankan whisper-server
```bash
/home/hdinjos/Dev/whisper.cpp/build/bin/whisper-server \
  --host 127.0.0.1 \
  --port 8001 \
  --language id \
  --convert \
  --model /home/hdinjos/Dev/models/audio/ggml-small.bin
```

Catatan: karena voice note Telegram berformat `.ogg`, opsi `--convert` membutuhkan `ffmpeg` terpasang di sistem.

### 5.4 Jalankan Bot
```bash
source .venv/bin/activate
python run.py
```

### 5.5 Jalankan Test
```bash
source .venv/bin/activate
pytest -q
```

## 6) Troubleshooting Singkat
- Bot selalu gagal baca struk/voice:
  - cek `llama-server` hidup
  - cek `LLAMACPP_BASE_URL` dan port
  - cek format output model (JSON valid atau tidak)
- Voice note gagal diproses:
  - cek `whisper-server` hidup
  - cek `WHISPER_SERVER_BASE_URL` + `WHISPER_SERVER_INFERENCE_PATH`
  - karena input Telegram `.ogg`, pastikan `whisper-server` dijalankan dengan `--convert`
  - pastikan `ffmpeg` tersedia di PATH
  - cek file audio berhasil terunduh ke `uploads/`
- Menu command tidak muncul:
  - restart bot (karena command didaftarkan saat startup)
- Laporan PDF gagal dibuat:
  - cek dependency `fpdf2`
  - cek permission write ke folder `uploads/`
- Laporan kosong:
  - pastikan transaksi tersimpan untuk user Telegram yang sama
