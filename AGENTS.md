# AGENTS

## Ringkasan
Dokumen ini merangkum konteks proyek dari tahap perencanaan sampai status implementasi saat ini untuk MVP **Expense Agent** (Telegram bot pencatat pengeluaran dari foto struk) dengan AI lokal `llama.cpp`.

## Tujuan MVP
- User kirim foto struk ke Telegram bot.
- Bot unduh foto kualitas terbaik ke `uploads/`.
- Foto dikirim ke endpoint OpenAI-compatible `llama.cpp`.
- Hasil ekstraksi JSON divalidasi/normalisasi.
- Data transaksi disimpan ke SQLite.
- User dapat melihat laporan harian, bulanan, dan transaksi terakhir.

## Batasan Teknis yang Disepakati
- Tidak menggunakan OpenAI cloud API.
- Tidak menggunakan Ollama.
- Tidak menggunakan API eksternal lain.
- AI inference wajib melalui `llama.cpp` lokal (`/v1/chat/completions`).

## Arsitektur Final
- `app/main.py`: bootstrap aplikasi, register handler, register Telegram command menu (`setMyCommands`).
- `app/bot/handlers.py`: command handler + handler upload foto.
- `app/ai/receipt_extractor.py`:
  - `BaseReceiptExtractor`
  - `DummyReceiptExtractor`
  - `LlamaCppReceiptExtractor` (base64 image data URL + payload vision OpenAI-compatible)
- `app/services/transaction_service.py`: validasi/normalisasi + aturan bisnis simpan transaksi.
- `app/services/report_service.py`: laporan harian/bulanan/transaksi terakhir.
- `app/db/`: SQLAlchemy model + repository + session management.
- `app/utils/json_utils.py`: cleanup code fence + safe JSON parse + extract JSON object dari output model.

## Alur End-to-End
1. User upload foto struk.
2. Bot simpan file ke `uploads/{user_id}_{timestamp}.jpg`.
3. Bot panggil extractor `llama.cpp`:
   - Endpoint: `{LLAMACPP_BASE_URL}/chat/completions`
   - Model: `LLAMACPP_MODEL`
   - Vision payload:
     - `{"type":"text","text":"...prompt..."}`
     - `{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,..."} }`
4. Response model dibersihkan dan diparse JSON.
5. Jika valid dan total ada, transaksi disimpan.
6. Bot kirim balasan status (`success` / `partial` / `failed`).

## Keputusan/Patch Penting Selama Implementasi

### 1) Kegagalan baca struk meski model bisa ekstrak
Akar masalah yang ditemukan:
- Endpoint bot mengarah ke `:8000`, tapi server aktif pada `:8080` di environment saat debugging.
- Serialisasi `raw_json` gagal saat berisi object `date`/`time` Python.

Perbaikan:
- Menjalankan bot dengan `LLAMACPP_BASE_URL` yang sesuai environment runtime.
- Menambahkan `json.dumps(..., default=str)` saat simpan `raw_json`.

### 2) Menu command Telegram tidak muncul
Perbaikan:
- Menambahkan `set_my_commands` via `post_init` di `app/main.py`.
- Menu sinkron dengan handler:
  - `/start`
  - `/help`
  - `/laporan_hari_ini`
  - `/laporan_bulan_ini`
  - `/transaksi_terakhir`

### 3) Aturan tanggal transaksi diubah
Kebutuhan baru:
- `transaction_date` harus tanggal saat upload.
- Tanggal struk tetap disimpan.
- Jika tanggal struk tidak ada, gunakan tanggal upload.

Implementasi:
- `transaction_date` di DB sekarang diset dari tanggal upload.
- `raw_json.transaction.date` menyimpan tanggal struk; fallback ke tanggal upload jika kosong.
- Response service menampilkan:
  - `date` = tanggal upload
  - `receipt_date` = tanggal struk/fallback

## Konfigurasi Env Saat Ini
`.env.example`:
- `LLAMACPP_BASE_URL=http://localhost:8000/v1`
- `LLAMACPP_MODEL=local-qwen3-vl`
- `USE_DUMMY_EXTRACTOR=false`
- `DATABASE_URL=sqlite:///expense-agent.db`
- `UPLOAD_DIR=uploads`
- `REQUEST_TIMEOUT_SECONDS=120`

## Validasi & Testing
- Test suite aktif via `pytest`.
- Status terakhir: semua test lulus (`9 passed`).

## Catatan Operasional
- Jika bot selalu balas gagal, cek:
  1. `llama-server` benar-benar hidup.
  2. Port di `LLAMACPP_BASE_URL` sesuai port server aktif.
  3. Log bot untuk error koneksi / parsing / DB.

## Status Saat Ini
MVP berjalan end-to-end dengan:
- Upload struk via Telegram.
- Ekstraksi AI lokal `llama.cpp`.
- Penyimpanan transaksi per user.
- Laporan per user.
- Menu command Telegram terdaftar.
