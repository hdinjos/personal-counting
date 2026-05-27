# Contributing Guide

Terima kasih sudah ingin berkontribusi ke proyek ini.

## 1) Prinsip Kontribusi
- Jaga scope tetap kecil dan fokus.
- Pertahankan integrasi AI tetap lokal (`llama.cpp`), tanpa API cloud.
- Prioritaskan stabilitas alur utama: upload struk -> ekstraksi -> simpan -> laporan.

## 2) Setup Development
```bash
cd expense-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Isi `.env` minimal:
- `TELEGRAM_BOT_TOKEN`
- `LLAMACPP_BASE_URL`
- `LLAMACPP_MODEL`
- `USE_DUMMY_EXTRACTOR`

## 3) Jalankan Aplikasi Lokal
1. Jalankan `llama-server` lokal.
2. Jalankan bot:
   ```bash
   source .venv/bin/activate
   python run.py
   ```

## 4) Testing Sebelum PR
```bash
source .venv/bin/activate
pytest -q
```

PR yang mengubah logic bisnis harus menyertakan atau memperbarui test yang relevan.

## 5) Standar Kode
- Gunakan Python 3.11+.
- Ikuti pola struktur modul yang sudah ada (`app/bot`, `app/ai`, `app/services`, `app/db`, `app/utils`).
- Jangan menambah dependency besar tanpa alasan kuat.
- Hindari refactor besar yang tidak relevan dengan issue.

## 6) Checklist Pull Request
- [ ] Perubahan fokus pada masalah yang jelas
- [ ] Tidak ada pemanggilan OpenAI cloud API / Ollama
- [ ] Integrasi llama.cpp tetap ke endpoint OpenAI-compatible lokal
- [ ] `pytest -q` lulus
- [ ] README / docs diperbarui jika behavior berubah
- [ ] Jika mengubah setup model/port `llama.cpp`, update `docs/PRODUCT_GUIDE.md` dan pastikan referensi ke `https://github.com/ggml-org/llama.cpp` tetap valid

## 7) Area Kontribusi yang Dibutuhkan
- Ketahanan parser output model (format output liar)
- Validasi data transaksi dan edge cases
- Peningkatan kualitas laporan dan ringkasan
- Pengujian integrasi end-to-end

