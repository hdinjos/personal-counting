# AGENTS

## Ringkasan
Dokumen ini merangkum konteks proyek dari tahap perencanaan sampai status implementasi saat ini untuk MVP **Expense Agent** (Telegram bot pencatat pengeluaran dari foto struk dan pesan suara) dengan AI lokal `llama.cpp`.

## Tujuan MVP
- User kirim foto struk ke Telegram bot.
- User kirim voice note berisi detail transaksi ke Telegram bot.
- Bot unduh foto kualitas terbaik ke `uploads/`.
- Bot transkripsi voice note ke teks, lalu ekstraksi data transaksi via AI lokal.
- Foto atau teks transkripsi dikirim ke endpoint OpenAI-compatible `llama.cpp`.
- Hasil ekstraksi JSON divalidasi/normalisasi.
- Data transaksi disimpan ke SQLite.
- User dapat melihat laporan harian, bulanan, dan transaksi terakhir.
- User dapat mengunduh rekap harian dalam format PDF.

## Batasan Teknis yang Disepakati
- Tidak menggunakan OpenAI cloud API.
- Tidak menggunakan Ollama.
- Tidak menggunakan API eksternal lain.
- AI inference wajib melalui `llama.cpp` lokal (`/v1/chat/completions`).

## Arsitektur Final
- `app/main.py`: bootstrap aplikasi, register handler, register Telegram command menu (`setMyCommands`).
- `app/bot/handlers.py`: command handler + handler upload foto + handler voice note + command export PDF.
- `app/ai/receipt_extractor.py`:
  - `BaseReceiptExtractor`
  - `DummyReceiptExtractor`
  - `LlamaCppReceiptExtractor` (mendukung input gambar base64 data URL dan input teks transkripsi)
- `app/ai/voice_transcriber.py`:
  - `VoiceTranscriber` berbasis `openai-whisper` (model default `tiny`, bahasa `id`)
- `app/services/transaction_service.py`: validasi/normalisasi + aturan bisnis simpan transaksi.
- `app/services/report_service.py`: laporan harian/bulanan/transaksi terakhir + generator rekap PDF harian.
- `app/db/`: SQLAlchemy model + repository + session management.
- `app/utils/json_utils.py`: cleanup code fence + safe JSON parse + extract JSON object dari output model.

## Alur End-to-End
### A) Foto Struk
1. User upload foto struk.
2. Bot simpan file ke `uploads/{user_id}_{timestamp}.jpg`.
3. Bot panggil extractor `llama.cpp` dengan payload vision:
   - Endpoint: `{LLAMACPP_BASE_URL}/chat/completions`
   - Model: `LLAMACPP_MODEL`
   - Payload:
     - `{"type":"text","text":"...prompt..."}`
     - `{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,..."} }`
4. Response model dibersihkan dan diparse JSON.
5. Jika valid dan total ada, transaksi disimpan.
6. Bot kirim balasan status (`success` / `partial` / `failed`).

### B) Voice Note
1. User kirim voice note Telegram.
2. Bot simpan file `.ogg` ke `uploads/`.
3. `VoiceTranscriber` mentranskripsi audio ke teks (`openai-whisper`, language `id`).
4. Bot panggil extractor `llama.cpp` mode teks (tanpa `image_url`) menggunakan hasil transkripsi.
5. Hasil ekstraksi diproses oleh pipeline validasi/normalisasi yang sama, lalu disimpan ke DB.

### C) Rekap PDF
1. User jalankan command `/rekap`.
2. Bot ambil transaksi harian user dan membangun PDF via `fpdf2`.
3. Bot kirim file PDF ke user sebagai dokumen Telegram.

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

### 4) Ekstensi fitur voice note + export PDF
Sumber:
- Commit `5176dee` (`feat: add pdf export and voice note support`) pada **27 Mei 2026**.

Perubahan inti:
- `receipt_extractor` kini menerima `image_path` atau `text_input` agar satu pipeline ekstraksi bisa dipakai untuk foto dan voice.
- Penambahan `VoiceTranscriber` (`openai-whisper`) untuk mengubah voice note menjadi teks sebelum dikirim ke extractor.
- Penambahan command `/rekap` untuk generate dan kirim laporan PDF harian.
- Penambahan `generate_daily_pdf` di `report_service` menggunakan `fpdf2`.
- Registrasi handler baru di bootstrap:
  - `CommandHandler("rekap", ...)`
  - `MessageHandler(filters.VOICE, ...)`
- Dependensi baru:
  - `fpdf2>=2.8.0`
  - `openai-whisper>=20231117`

Analisa dampak:
- Positif: input transaksi tidak lagi terbatas pada foto struk; user bisa input cepat via suara.
- Positif: output laporan lebih portabel karena bisa dibagikan sebagai PDF.
- Teknis: throughput inference AI tetap mengikuti `llama.cpp` lokal; voice menambah tahapan transkripsi di sisi aplikasi.
- Operasional: install dependency bertambah berat (khususnya `openai-whisper`), sehingga provisioning environment perlu perhatian.

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
- Input transaksi via voice note Telegram.
- Ekstraksi AI lokal `llama.cpp`.
- Penyimpanan transaksi per user.
- Laporan per user.
- Export rekap harian ke PDF.
- Menu command Telegram terdaftar (`/start`, `/help`, `/laporan_hari_ini`, `/laporan_bulan_ini`, `/transaksi_terakhir`, `/rekap`).
