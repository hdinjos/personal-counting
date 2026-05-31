# AGENTS

> Dokumen ini adalah referensi lengkap proyek **Expense Agent** agar agent berikutnya bisa langsung bekerja tanpa membaca seluruh codebase.
> Terakhir diperbarui: 31 Mei 2026.

---

## Ringkasan Proyek

Telegram bot pencatat pengeluaran dari **foto struk** dan **voice note** menggunakan AI lokal. User kirim foto/suara → bot ekstrak data transaksi → konfirmasi ke user → simpan ke SQLite → user bisa lihat laporan.

## Stack Teknologi

| Komponen | Library/Tool | Versi |
|----------|-------------|-------|
| Bot framework | python-telegram-bot | ~21.11.1 |
| ORM | SQLAlchemy | ~2.0.50 |
| Migration | Alembic | ~1.18.4 |
| HTTP client | httpx | ~0.28.1 |
| PDF export | fpdf2 | ~2.8.7 |
| Image processing | Pillow | ~10.4.0 |
| OCR struk | PaddleOCR (+paddlepaddle) | ~3.6.0 |
| Env | python-dotenv | ~1.2.2 |
| Test | pytest + pytest-asyncio | ~8.4.2 |
| AI Vision/Text | llama.cpp (llama-server) | external |
| AI Speech | whisper.cpp (whisper-server) | external |
| Python | 3.12 | |
| DB | SQLite | |

## Batasan Teknis

- **TIDAK** menggunakan OpenAI cloud API.
- **TIDAK** menggunakan Ollama.
- **TIDAK** menggunakan API eksternal lain.
- AI inference wajib melalui `llama.cpp` lokal (`/v1/chat/completions`).
- Transkripsi suara wajib melalui `whisper.cpp` lokal (`/inference`).

---

## Struktur Direktori

```
expense-agent/
├── app/
│   ├── __init__.py
│   ├── main.py              # Bootstrap, register handlers, post_init commands
│   ├── config.py            # Settings dataclass, env loading
│   ├── bot/
│   │   ├── handlers.py      # Semua Telegram handler (command + message)
│   │   └── messages.py      # Template pesan bot (format_*, constants)
│   ├── ai/
│   │   ├── receipt_extractor.py  # BaseReceiptExtractor, Dummy, LlamaCpp
│   │   ├── ocr.py                # PaddleOCREngine (baca teks dari gambar struk)
│   │   ├── voice_transcriber.py  # VoiceTranscriber (whisper.cpp client)
│   │   └── prompts.py            # RECEIPT_EXTRACTION_PROMPT
│   ├── services/
│   │   ├── transaction_service.py  # Validasi, normalisasi, simpan transaksi
│   │   └── report_service.py      # Laporan harian/bulanan, PDF generator
│   ├── db/
│   │   ├── database.py      # Engine init, session_scope, auto-migration
│   │   ├── models.py        # Transaction, TransactionItem (SQLAlchemy ORM)
│   │   └── repositories.py  # TransactionRepository (CRUD)
│   └── utils/
│       ├── json_utils.py    # remove_code_fence, safe_parse_json, extract_json_from_text, _eval_arithmetic_values
│       ├── money.py         # normalize_amount, format_rupiah
│       ├── dates.py         # parse_receipt_date/time, format_date_id, today_local_date
│       ├── health.py        # check_server_health, check_all_services
│       └── rate_limiter.py  # RateLimiter (sliding window per user)
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 76896b3a92b7_initial_schema.py
├── tests/
│   ├── conftest.py
│   ├── test_validation.py
│   ├── test_pending_total_handler.py
│   ├── test_voice_transcriber.py
│   ├── test_user_whitelist.py
│   ├── test_dummy_extractor.py
│   ├── test_reports.py
│   └── test_json_parser.py
├── docs/
│   ├── PRODUCT_GUIDE.md
│   ├── llama-cpp.md
│   └── whisper-cpp.md
├── uploads/                  # Runtime: foto, voice, PDF (gitignored)
├── run.py                    # Entry point: from app.main import run; run()
├── requirements.txt
├── alembic.ini
├── .env.example
├── CONTRIBUTING.md
└── README.md
```

---

## Konfigurasi (.env)

```env
TELEGRAM_BOT_TOKEN=           # Wajib
LLAMACPP_BASE_URL=http://localhost:8000/v1
LLAMACPP_MODEL=local-qwen3-vl
WHISPER_SERVER_BASE_URL=http://127.0.0.1:8001
WHISPER_SERVER_INFERENCE_PATH=/inference
WHISPER_SERVER_TIMEOUT_SECONDS=120
WHISPER_LANGUAGE=id
OCR_LANGUAGE=id               # bahasa model PaddleOCR (id→latin model)
OCR_BACKEND=paddleocr         # "paddleocr" | "glm_ocr_llamacpp" | "vlm_llamacpp"
GLM_OCR_BASE_URL=http://127.0.0.1:8002/v1
GLM_OCR_MODEL=glm-ocr
GLM_OCR_PROMPT=OCR markdown. Preserve receipt line order from top to bottom. Do not add explanations.
GLM_OCR_TIMEOUT_SECONDS=120
GLM_OCR_MAX_TOKENS=4096
USE_DUMMY_EXTRACTOR=false
DATABASE_URL=sqlite:///expense-agent.db
UPLOAD_DIR=uploads
EXTRACTOR_BACKEND=llamacpp    # atau "dummy"
REQUEST_TIMEOUT_SECONDS=120
ENABLE_USER_WHITELIST=false
ALLOWED_USER_IDS=             # comma-separated int
ENABLE_STARTUP_HEALTH_CHECK=false
TZ=Asia/Jakarta
```

---

## Database Schema

### Table: `transactions`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | auto |
| telegram_user_id | Integer | indexed |
| telegram_username | String(128) | nullable |
| store_name | String(255) | nullable |
| transaction_date | Date | indexed, tanggal upload |
| transaction_time | Time | nullable, waktu dari struk |
| total | Integer | dalam Rupiah, tanpa desimal |
| status | String(16) | "success" |
| image_path | String(512) | telegram file_id |
| raw_json | Text | JSON lengkap hasil normalisasi |
| created_at | DateTime | UTC |

### Table: `transaction_items`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | auto |
| transaction_id | Integer FK | → transactions.id |
| name | String(255) | nullable |
| category | String(64) | nullable, dari set terbatas |
| quantity | Float | nullable |
| unit | String(32) | nullable |
| unit_price | Integer | nullable |
| subtotal | Integer | nullable |

### Kategori yang diizinkan:
`sembako`, `makanan`, `minuman`, `jajanan & kopi`, `kebersihan`, `perlengkapan rumah`, `elektronik`, `pakaian`, `perawatan diri`, `kesehatan`, `transportasi`, `pendidikan`, `hiburan`, `tagihan & utilitas`, `pulsa & internet`, `anak & bayi`, `hadiah & donasi`, `lainnya`

---

## Alur End-to-End

### A) Foto Struk
1. User upload foto → `handle_photo`
2. File disimpan sementara ke `uploads/{user_id}_{uuid}.jpg`
3. Routing berdasarkan `OCR_BACKEND`:
   - **`paddleocr`** (default): `PaddleOCREngine.extract_text(image_path)` → preprocessing (grayscale, autocontrast, denoise, sharpen) → OCR → layout reconstruction → teks
   - **`glm_ocr_llamacpp`**: kirim gambar ke GLM-OCR llama-server → return teks/markdown
   - **`vlm_llamacpp`**: skip OCR, langsung ke step 4 dengan `image_path`
4. `LlamaCppReceiptExtractor.extract(...)`:
   - Jika `ocr_text` → `_build_ocr_payload` (text mode)
   - Jika `image_path` (VLM) → `_build_vision_payload` (preprocessing VLM + base64 + vision prompt)
   - POST ke `{LLAMACPP_BASE_URL}/chat/completions`
   - Parse JSON dari response (handle code fence, ekspresi aritmatika)
5. `TransactionService.normalize_extraction()` → validasi + normalisasi + auto-koreksi
6. Bot kirim **konfirmasi** ke user (tampilkan data terbaca)
7. User balas "ya"/"simpan" → `_save_pending_transaction` → simpan ke DB
8. User balas "batal" → data dibuang
9. File sementara dihapus setelah proses

### B) Voice Note
1. User kirim voice → `handle_voice`
2. File `.ogg` disimpan sementara
3. `VoiceTranscriber.transcribe()`:
   - POST multipart ke `{WHISPER_SERVER_BASE_URL}/inference`
   - Return teks transkripsi
4. `LlamaCppReceiptExtractor.extract(text_input=...)`:
   - POST ke llama-server (text-only payload, tanpa image)
5. Normalisasi → konfirmasi → simpan (sama seperti foto)
6. File sementara dihapus

### C) Confirmation Flow (PENTING)
Setiap transaksi (foto/voice) **tidak langsung disimpan**. Bot menampilkan data terbaca dan minta konfirmasi:
- User balas `ya`/`y`/`simpan`/`ok`/`oke`/`yes` → simpan
- User balas `batal`/`tidak`/`no`/`cancel` atau `/batal` → batal
- Jika total tidak konsisten dengan item → minta input total manual
- Pending expired setelah 600 detik

### D) Laporan & Rekap
- `/laporan_hari_ini` → total transaksi hari ini
- `/laporan_bulan_ini` → total transaksi bulan ini
- `/transaksi_terakhir` → 5 transaksi terbaru
- `/rekap` → generate PDF harian via fpdf2, kirim sebagai dokumen

---

## Command Telegram Terdaftar

| Command | Fungsi |
|---------|--------|
| `/start` | Pesan selamat datang |
| `/help` | Panduan penggunaan |
| `/laporan_hari_ini` | Laporan pengeluaran hari ini |
| `/laporan_bulan_ini` | Laporan pengeluaran bulan ini |
| `/transaksi_terakhir` | 5 transaksi terbaru |
| `/rekap` | Export PDF harian |
| `/batal` | Batalkan pending konfirmasi |
| `/status` | Cek koneksi ke llama-server & whisper-server |

---

## Arsitektur Kelas Utama

### `BotHandlers` (app/bot/handlers.py)
- Menerima semua dependency via constructor (DI)
- Rate limiter: max 10 request/menit per user
- User whitelist opsional
- Pending confirmation disimpan di `context.user_data`
- Safe reply: truncate pesan > 4096 char

### `TransactionService` (app/services/transaction_service.py)
- `normalize_extraction(payload)` → normalisasi output AI ke format standar
- `_apply_defaults(normalized)` → isi default (store name, quantity)
- `_fill_missing_totals(normalized)` → hitung total dari item jika tidak ada
- `_calculate_expected_total(normalized)` → validasi konsistensi total vs item, dengan auto-koreksi:
  - **Double-counting fix**: jika sum(subtotals) > total×1.5 dan sum(unit_prices) ≈ total → model salah kalikan qty×harga, koreksi subtotal = unit_price
  - **Inclusive tax fix**: jika items - discount == total dan tax non-zero → tax sudah inklusif, nullify
  - **Tax inference**: jika tax=None dan total > items - discount, dan gap ≤ 20% → infer tax (restoran/cafe)
  - **Discount correction**: jika expected ≠ total dan selisih wajar (≤ 50%) → koreksi discount
- `store_confirmed_transaction(...)` → simpan setelah user konfirmasi
- `_has_minimum_transaction_data(normalized)` → cek minimal ada item bernama + harga

### `LlamaCppReceiptExtractor` (app/ai/receipt_extractor.py)
- Retry logic: max 2 retry dengan exponential backoff
- `extract(ocr_text|text_input|image_path)` — tiga mode payload:
  - `ocr_text` → struk hasil OCR (`_build_ocr_payload`, prompt struk + instruksi OCR error)
  - `text_input` → voice/teks (`_build_text_payload`, jangan karang tanggal/waktu)
  - `image_path` → VLM vision (`_build_vision_payload`, preprocessing VLM + base64 + vision prompt)
- Response parsing: `extract_json_from_text()` (handle code fence, partial JSON, ekspresi aritmatika)

### `PaddleOCREngine` (app/ai/ocr.py)
- Wrapper PaddleOCR **3.x** untuk baca teks dari gambar struk
- Model di-lazy load saat `extract_text()` pertama dipanggil (hemat startup)
- Konstruktor: `use_textline_orientation=True`, `use_doc_orientation_classify=False`, `use_doc_unwarping=False`, `enable_mkldnn=False`, `text_rec_score_thresh=0.5`
  - `enable_mkldnn=False` WAJIB: paddlepaddle 3.x CPU crash oneDNN (`ConvertPirAttribute2RuntimeAttribute`) saat `.predict()` bila MKLDNN aktif
  - `text_rec_score_thresh=0.5` membuang hasil low-confidence (noise) agar tidak mengganggu interpretasi llama
- **Preprocessing** (`preprocess_for_ocr`): grayscale → autocontrast (cutoff=1) → MedianFilter (denoise) → sharpen. Menghilangkan efek shadow/bayangan pada foto.
- **Noise filter** (`_filter_noise`): buang deteksi ≤3 karakter yang x-position-nya di luar IQR area struk (menghilangkan noise dari latar belakang, mis. keyboard keys).
- Inferensi pakai `.predict(image_path)`; teks diambil dari `res["rec_texts"]`
- **Rekonstruksi layout**: `_layout_text()` mengelompokkan deteksi per baris via koordinat box (`rec_boxes`/`rec_polys`) — deteksi pada baris vertikal yang sama digabung & diurutkan kiri→kanan (join dua spasi, antar baris newline), supaya nama item tetap sebaris dengan harga (mengurangi kerugian layout vs vision)
- **Orphan merge**: jika baris hanya berisi angka dan baris sebelumnya berakhir `:`, gabungkan (fix "NON TUNAI :" terpisah dari nilainya)
- `lang` dari `OCR_LANGUAGE` (default `id`; fallback otomatis ke `latin` bila lang tak didukung)

### Standalone preprocessing functions (app/ai/ocr.py)
- `preprocess_for_ocr(image_path)` → grayscale + autocontrast + denoise + sharpen (optimal PaddleOCR)
- `preprocess_for_vlm(image_path, max_side=1536)` → autocontrast RGB + resize (optimal model vision)

### `VoiceTranscriber` (app/ai/voice_transcriber.py)
- Client untuk whisper.cpp `whisper-server`
- Multipart upload file audio
- Retry logic: max 2 retry
- Error handling: hint tentang `--convert` jika HTTP 400

### `ReportService` (app/services/report_service.py)
- Query via repository → format laporan
- PDF generation via fpdf2 (tabel sederhana)

### `TransactionRepository` (app/db/repositories.py)
- `create_transaction(...)` → insert + items dalam satu session
- `get_transactions_for_day/month(...)` → query by date range
- `get_last_transactions(...)` → query last N
- `raw_json` diserialisasi dengan `json.dumps(..., default=str)`

---

## Format Output AI (Expected JSON)

```json
{
  "status": "success | partial | failed",
  "message": null,
  "store": { "name": null, "address": null, "phone": null },
  "transaction": {
    "date": "YYYY-MM-DD | null",
    "time": "HH:mm | null",
    "invoice_number": null,
    "payment_method": null
  },
  "items": [
    {
      "name": "string",
      "category": "kategori",
      "quantity": 1,
      "unit": "pcs",
      "unit_price": 10000,
      "subtotal": 10000
    }
  ],
  "summary": {
    "subtotal": null,
    "discount": null,
    "tax": null,
    "service_charge": null,
    "total": 10000,
    "paid": null,
    "change": null
  },
  "raw_text": null
}
```

---

## Aturan Bisnis Penting

1. **transaction_date** = tanggal upload (bukan tanggal struk). Tanggal struk disimpan di `raw_json`.
2. **Semua nominal** disimpan sebagai integer (Rupiah tanpa desimal).
3. **Konfirmasi wajib** sebelum simpan — tidak ada auto-save.
4. **Total inconsistency** → bot minta user input total manual.
5. **Pending timeout** = 600 detik. Setelah itu, user harus kirim ulang.
6. **File upload dihapus** setelah proses (tidak disimpan permanen di disk).
7. **image_path** di DB menyimpan Telegram file_id (bukan path lokal).

---

## Menjalankan Proyek

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-paddle.txt  # opsional, hanya untuk OCR_BACKEND=paddleocr
cp .env.example .env  # isi TELEGRAM_BOT_TOKEN

# Jalankan AI servers
llama-server --model <path-to-gguf> --port 8000
whisper-server --host 127.0.0.1 --port 8001 --language id --convert --model <path-to-whisper-ggml>

# Jalankan bot
python run.py

# Test
pytest -q
```

---

## Keputusan/Patch Historis

### 1) Endpoint port mismatch
- Bot mengarah ke `:8000` tapi server aktif di `:8080` → pastikan `LLAMACPP_BASE_URL` sesuai.

### 2) Serialisasi raw_json gagal
- Object `date`/`time` Python tidak bisa di-`json.dumps` → fix: `default=str`.

### 3) Tanggal transaksi = tanggal upload
- Awalnya pakai tanggal struk. Diubah: `transaction_date` = tanggal upload, tanggal struk tetap di raw_json.

### 4) Migrasi dari openai-whisper ke whisper.cpp
- Awalnya pakai library `openai-whisper` (Python). Diganti ke `whisper-server` (whisper.cpp) via HTTP.
- Alasan: lebih ringan, tidak perlu install torch/model besar di environment bot.

### 5) Confirmation flow ditambahkan
- Awalnya auto-save. Sekarang wajib konfirmasi user sebelum simpan.
- Mencegah data salah masuk DB tanpa review user.

### 6) Foto struk: vision → OCR (PaddleOCR) + llama text → multi-backend
- Awalnya foto struk dikirim langsung ke llama vision (multimodal).
- Diubah: PaddleOCR (bahasa `id`) baca teks dari gambar, lalu teks OCR diinterpretasi llama (text mode, `_build_ocr_payload`).
- Kemudian ditambahkan kembali opsi VLM (`OCR_BACKEND=vlm_llamacpp`) — gambar di-preprocess lalu dikirim langsung ke model multimodal (Qwen3-VL) via `_build_vision_payload`.
- Sekarang ada 3 backend: `paddleocr` (default), `glm_ocr_llamacpp`, `vlm_llamacpp`.
- Voice tetap pakai whisper → llama text (tidak berubah).

---

## Testing

```bash
pytest -q
```

Test files:
- `test_validation.py` — normalisasi dan validasi transaksi
- `test_pending_total_handler.py` — flow konfirmasi dan manual total
- `test_voice_transcriber.py` — mock whisper-server responses
- `test_user_whitelist.py` — whitelist logic
- `test_dummy_extractor.py` — dummy extractor output
- `test_reports.py` — laporan harian/bulanan
- `test_json_parser.py` — JSON extraction dari output model

---

## Catatan Operasional

- Log file: `bot.log` (rotating, max 5MB × 3 backup)
- Health check saat startup (opsional via `ENABLE_STARTUP_HEALTH_CHECK`)
- Rate limiter: 10 request/menit per user (foto + voice)
- Jika bot selalu gagal:
  1. Cek `llama-server` hidup di port yang benar
  2. Cek `whisper-server` hidup (untuk voice)
  3. Cek `bot.log` untuk error detail
  4. Jalankan `/status` dari Telegram untuk quick check

---

## Referensi Dokumentasi Lain

- [docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md) — panduan produk, setup model
- [docs/llama-cpp.md](docs/llama-cpp.md) — panduan teknis llama.cpp
- [docs/whisper-cpp.md](docs/whisper-cpp.md) — panduan teknis whisper.cpp
- [CONTRIBUTING.md](CONTRIBUTING.md) — panduan kontribusi & migration workflow
