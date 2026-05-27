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
3. Bot mentranskripsi audio ke teks dengan `openai-whisper`.
4. Teks hasil transkripsi dikirim ke model AI lokal `llama.cpp` untuk diekstrak menjadi JSON transaksi.
5. Data masuk pipeline validasi/normalisasi yang sama, lalu disimpan ke SQLite.
6. Bot mengirim status proses transaksi ke user.

### C) Laporan
User bisa melihat:
- `/laporan_hari_ini`
- `/laporan_bulan_ini`
- `/transaksi_terakhir`
- `/rekap` (mengirim file PDF rekap harian)

## 3) Cara Kerja Teknis (System Flow)
- **Transport**: Telegram Bot API (`python-telegram-bot`)
- **AI Extractor**: `LlamaCppReceiptExtractor`
- **Voice Transcriber**: `VoiceTranscriber` (`openai-whisper`, default model `tiny`, language `id`)
- **Database**: SQLite via SQLAlchemy
- **Parser**: `json_utils` untuk menghapus code fence dan ekstrak JSON dari output campuran
- **PDF Report**: `report_service.generate_daily_pdf()` menggunakan `fpdf2`

### Integrasi AI Lokal
- Base URL default: `http://localhost:8000/v1`
- Endpoint: `POST /chat/completions`
- Payload bisa dua mode:
  - **Vision mode** (foto): text prompt + `image_url` data URL base64 (`data:image/jpeg;base64,...`)
  - **Text mode** (voice): text prompt + teks hasil transkripsi
- Model field wajib dikirim dari `LLAMACPP_MODEL` (default `local-qwen3-vl`)

### Referensi Model & Dokumentasi llama.cpp
- Model Hugging Face: https://huggingface.co/unsloth/Qwen3-VL-2B-Instruct-GGUF
- Repositori resmi llama.cpp: https://github.com/ggml-org/llama.cpp
- Dokumentasi server llama.cpp (OpenAI-compatible API): https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

### Sinkronisasi Nama Model (`model` field)
- Di aplikasi, request selalu mengirim `model` dari env `LLAMACPP_MODEL`.
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
4. Telegram bot token aktif
5. Port `llama-server` sesuai `LLAMACPP_BASE_URL` di `.env`
6. Dependency tambahan untuk fitur baru:
   - `openai-whisper>=20231117`
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

### 5.3 Jalankan Bot
```bash
source .venv/bin/activate
python run.py
```

### 5.4 Jalankan Test
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
  - cek dependency `openai-whisper` terpasang
  - cek file audio berhasil terunduh ke `uploads/`
- Menu command tidak muncul:
  - restart bot (karena command didaftarkan saat startup)
- Laporan PDF gagal dibuat:
  - cek dependency `fpdf2`
  - cek permission write ke folder `uploads/`
- Laporan kosong:
  - pastikan transaksi tersimpan untuk user Telegram yang sama
