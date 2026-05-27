# Menjalankan Qwen3-VL-2B-Instruct GGUF dengan llama.cpp di Local PC

## 1) Ringkasan
`llama.cpp` adalah runtime C/C++ ringan untuk menjalankan model LLM secara lokal, termasuk mode server OpenAI-compatible (`llama-server`).  
Proyek ini memakai `llama.cpp` agar proses OCR + ekstraksi struk berjalan lokal (tanpa API cloud), lebih privat, dan biaya operasional rendah.

Model yang dipakai adalah format **GGUF** karena:
- didukung langsung oleh `llama.cpp`,
- efisien untuk inferensi lokal,
- tersedia banyak varian kuantisasi.

Karena model ini **multimodal (vision-language)**, selain file model utama `.gguf`, dibutuhkan file tambahan **`mmproj`** (`.gguf`) untuk proyeksi fitur gambar.

Referensi:
- Repo resmi `llama.cpp`: https://github.com/ggml-org/llama.cpp
- Halaman release binary: https://github.com/ggml-org/llama.cpp/releases
- Model: https://huggingface.co/unsloth/Qwen3-VL-2B-Instruct-GGUF
- Server docs: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

## 2) Rekomendasi binary llama.cpp (berdasarkan OS + hardware)
> Penting: **jangan mengandalkan nama file asset statis** karena bisa berubah tiap release.  
> Selalu buka halaman release resmi, lalu pilih asset sesuai **OS + backend akselerasi**.

| Skenario | OS | Prioritas binary/backend | Catatan |
|---|---|---|---|
| NVIDIA GPU + CPU | Windows | CUDA build (jika tersedia) | Pilih asset Windows x64 dengan akselerasi NVIDIA/CUDA. |
| NVIDIA GPU + CPU | Linux | CUDA build (jika tersedia) | Pilih asset Linux/Ubuntu x64 dengan CUDA. |
| NVIDIA GPU + CPU | macOS | Umumnya Metal (tanpa CUDA) | CUDA tidak relevan di macOS. Gunakan backend macOS yang tersedia. |
| AMD GPU + CPU | Windows | Vulkan (umum) | ROCm biasanya fokus Linux; di Windows umumnya Vulkan lebih praktis. |
| AMD GPU + CPU | Linux (Ubuntu x64) | **1) ROCm 7.2, 2) Vulkan, 3) CPU** | Untuk proyek ini, prioritas utama ROCm 7.2. Jika gagal, fallback Vulkan lalu CPU. |
| AMD GPU + CPU | macOS | Metal (bukan ROCm) | ROCm tidak relevan di macOS. Gunakan backend native macOS jika tersedia. |
| CPU only | Windows | CPU build | Pilih asset CPU-only untuk Windows x64. |
| CPU only | Linux | CPU build | Pilih asset CPU-only untuk Linux/Ubuntu x64. |
| CPU only | macOS Intel | CPU/native macOS Intel | Pilih asset macOS Intel yang tersedia. |
| CPU only | macOS Apple Silicon | CPU/native macOS Apple Silicon | Pilih asset Apple Silicon (ARM64) jika tersedia. |

## 3) Setup yang digunakan author
- CPU: AMD Ryzen 7 5700X (8 core)
- GPU: AMD RX 6600 (GDDR6 8GB)
- RAM: 32GB DDR4 3200 MHz
- OS: Linux Ubuntu
- Mode: GPU AMD + CPU
- Binary pilihan: **Ubuntu x64 ROCm 7.2**
- Alasan: ingin akselerasi GPU AMD dengan performa lebih baik dibanding CPU-only.
- Fallback:
  1. Ubuntu x64 Vulkan (jika ROCm sulit/driver tidak cocok)
  2. Ubuntu x64 CPU (fallback terakhir)

## 4) Cara download binary llama.cpp
1. Buka: https://github.com/ggml-org/llama.cpp/releases
2. Pilih release terbaru.
3. Download binary sesuai OS dan backend akselerasi Anda.
4. Ekstrak archive hasil download.
5. Masuk ke folder hasil ekstrak.
6. Pastikan executable `llama-server` dan `llama-cli` tersedia.

Contoh Linux:
```bash
chmod +x llama-server llama-cli
./llama-server --help
```

Catatan:
- Nama file release asset bisa berubah di tiap versi.
- Selalu cek halaman release resmi.

## 5) Cara mendapatkan model dari Hugging Face
Repository model:
- https://huggingface.co/unsloth/Qwen3-VL-2B-Instruct-GGUF

Contoh file:
- Model utama: `Qwen3-VL-2B-Instruct-BF16.gguf`
- Multimodal projection: `mmproj-BF16.gguf`

Buat folder model:
```bash
mkdir -p ~/Dev/models
cd ~/Dev/models
```

### Opsi A: Download manual lewat browser (paling sederhana)
1. Buka halaman model.
2. Download file model utama `.gguf`.
3. Download file `mmproj` `.gguf`.
4. Simpan keduanya di `~/Dev/models`.

### Opsi B: Download via `huggingface-cli`
```bash
pip install -U "huggingface_hub[cli]"
huggingface-cli download unsloth/Qwen3-VL-2B-Instruct-GGUF Qwen3-VL-2B-Instruct-BF16.gguf --local-dir ~/Dev/models
huggingface-cli download unsloth/Qwen3-VL-2B-Instruct-GGUF mmproj-BF16.gguf --local-dir ~/Dev/models
```

## 6) Menjalankan llama-server untuk proyek ini
### Opsi author (ROCm 7.2 + model lokal)
```bash
./llama-server \
  --model ~/Dev/models/Qwen3-VL-2B-Instruct-BF16.gguf \
  --mmproj ~/Dev/models/mmproj-BF16.gguf \
  --alias local-qwen3-vl \
  --jinja \
  --top-p 0.8 \
  --top-k 20 \
  --temp 0.7 \
  --min-p 0.0 \
  --flash-attn on \
  --presence-penalty 1.5 \
  --ctx-size 8192 \
  --n-gpu-layers 99 \
  --port 8000
```

### Fallback Vulkan
Gunakan binary Vulkan dari release, lalu jalankan command yang sama.

### Fallback CPU
Gunakan binary CPU-only, lalu jalankan command yang sama (opsional turunkan `--n-gpu-layers` menjadi `0` bila perlu).

## 7) Sinkronisasi dengan konfigurasi proyek
Set `.env` proyek:
```dotenv
LLAMACPP_BASE_URL=http://localhost:8000/v1
LLAMACPP_MODEL=local-qwen3-vl
USE_DUMMY_EXTRACTOR=false
```

Penjelasan:
- Bot memanggil endpoint `POST /v1/chat/completions`.
- Field `model` dikirim dari `LLAMACPP_MODEL`.
- Karena itu, `--alias` di `llama-server` disarankan sama dengan nilai `LLAMACPP_MODEL`.

## 8) Verifikasi cepat
### Cek model terdeteksi
```bash
curl -s http://localhost:8000/v1/models
```

### Cek chat completion sederhana
```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "local-qwen3-vl",
    "messages": [{"role":"user","content":"tes koneksi"}],
    "max_tokens": 16
  }'
```

Jika respons keluar, server siap dipakai oleh bot.

## 9) Troubleshooting
- **Port 8000 tidak bisa diakses**: cek proses `llama-server`, firewall, dan port conflict.
- **Model tidak ditemukan**: pastikan path file `.gguf` dan `mmproj` benar.
- **GPU AMD tidak jalan di ROCm**: coba binary Vulkan.
- **Vulkan juga gagal**: fallback CPU-only.
- **Bot tetap gagal ekstraksi**: pastikan `.env` mengarah ke `http://localhost:8000/v1` dan `LLAMACPP_MODEL` cocok dengan alias server.

