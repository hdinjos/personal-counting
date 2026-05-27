# Menjalankan whisper.cpp (whisper-server) untuk Expense Agent

## 1) Ringkasan
Dokumen ini menjelaskan tata cara konfigurasi dan pemakaian `whisper.cpp` sebagai server transkripsi suara lokal untuk proyek Expense Agent.

Target penggunaan di proyek ini:
- endpoint transkripsi lokal: `http://127.0.0.1:8001/inference`
- model: `~/Dev/models/audio/ggml-small.bin`
- format input dari Telegram: `.ogg` (butuh `--convert` + `ffmpeg`)

## 2) Referensi Resmi
- Repo utama + bagian AMD ROCm: https://github.com/ggml-org/whisper.cpp#amd-rocm-gpu-support
- Release binary: https://github.com/ggml-org/whisper.cpp/releases
- Dokumentasi model (`ggml`): https://github.com/ggml-org/whisper.cpp/blob/master/models/README.md
- Kumpulan model pre-converted: https://huggingface.co/ggerganov/whisper.cpp/tree/main
- Dokumentasi `whisper-server`: https://github.com/ggml-org/whisper.cpp/blob/master/examples/server/README.md

## 3) Opsi Instalasi whisper.cpp

### Opsi A - Pakai binary dari release (paling cepat)
1. Buka halaman release resmi.
2. Pilih release terbaru.
3. Download aset sesuai OS/arsitektur/backend Anda.
4. Ekstrak file.
5. Verifikasi binary:

```bash
./whisper-server --help
./whisper-cli --help
```

Catatan: nama aset release bisa berubah antar versi, jadi pilih berdasarkan OS + arsitektur + backend, bukan menghafal nama file aset.

### Opsi B - Build dari source (AMD ROCm)
Prasyarat:
- ROCm sudah terpasang dan berfungsi.
- `rocminfo` tersedia.

Langkah:
```bash
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp

# cek arsitektur GPU AMD (contoh: gfx1030, gfx1100, gfx1201, dll)
rocminfo | grep "gfx"

# build HIP/ROCm
cmake -B build -DGGML_HIP=1 -DAMDGPU_TARGETS="gfx1030"
cmake --build build -j --config Release
```

Catatan:
- Dari dokumentasi resmi, contoh default memakai `gfx1201`; ganti sesuai output `rocminfo` Anda.
- Untuk beberapa GPU berbeda, bisa pakai daftar: `-DAMDGPU_TARGETS="gfx1100;gfx1201"`.

## 4) Menyiapkan Model
Ada 3 cara resmi:
1. Script download: `models/download-ggml-model.sh`
2. Download manual dari Hugging Face
3. Konversi sendiri dari model PyTorch

### Cara cepat (script resmi)
```bash
cd /path/to/whisper.cpp/models
./download-ggml-model.sh small
```

Hasil umumnya akan berupa file `ggml-small.bin`.

### Cara manual (sesuai kebutuhan proyek)
1. Buka: https://huggingface.co/ggerganov/whisper.cpp/tree/main
2. Ambil file `ggml-small.bin`
3. Simpan ke:

```bash
~/Dev/models/audio/ggml-small.bin
```

### Verifikasi hash model (opsional)
Dari tabel model resmi, `small` punya SHA `55356645c2b361a969dfd0ef2c5a50d530afd8d5`.

```bash
sha1sum ~/Dev/models/audio/ggml-small.bin
```

## 5) Menjalankan whisper-server (Setting Author)
Dari folder binary (`/home/hdinjos/Dev/whisper.cpp/build/bin/`):

```bash
./whisper-server \
   --host 127.0.0.1 \
   --port 8001 \
   --language id \
   --convert \
   --model ~/Dev/models/audio/ggml-small.bin
```

Penjelasan flag penting:
- `--port 8001`: menyesuaikan konfigurasi Expense Agent.
- `--language id`: default transkripsi bahasa Indonesia.
- `--convert`: penting untuk voice note Telegram (`.ogg/.opus`).
- `--model`: path model `ggml`.

## 6) Integrasi ke Expense Agent
Pastikan `.env` proyek berisi:

```dotenv
WHISPER_SERVER_BASE_URL=http://127.0.0.1:8001
WHISPER_SERVER_INFERENCE_PATH=/inference
WHISPER_SERVER_TIMEOUT_SECONDS=120
WHISPER_LANGUAGE=id
```

## 7) Verifikasi Setelah Konfigurasi

### Cek health endpoint
```bash
curl -s http://127.0.0.1:8001/health
```

Expected:
```json
{"status":"ok"}
```

### Cek endpoint transkripsi
```bash
curl -sS -X POST http://127.0.0.1:8001/inference \
  -F "file=@/path/to/audio.ogg" \
  -F "language=id" \
  -F "response_format=json"
```

Jika berhasil, response berisi field `text`.

## 8) Troubleshooting Singkat
- `HTTP 400 Invalid request` saat kirim `.ogg`:
  - pastikan server dijalankan dengan `--convert`
  - pastikan `ffmpeg` tersedia di PATH (`ffmpeg -version`)
- Server gagal start setelah menambah `--convert`:
  - biasanya karena `ffmpeg` belum terpasang
- Bot timeout ke whisper-server:
  - cek URL/port di `.env`
  - cek proses server masih hidup
- Transkripsi tidak akurat:
  - coba model lebih besar (`medium`/`large-v3`) jika resource cukup
  - pertahankan `--language id` untuk konteks Bahasa Indonesia
