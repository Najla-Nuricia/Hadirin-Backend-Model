# Hadirin Backend API

Backend REST API & Face Recognition Service untuk sistem presensi **Hadirin** (FastAPI + Supabase + MTCNN/MobileFaceNet).

- Docs interaktif: `http://127.0.0.1:8000/docs`
- Health check: `GET /health`

---

## 0. Quick Start (cara tercepat)

Kalau setup sudah pernah dilakukan (`.venv` ada, `.env` terisi, database sudah di-seed):

```bash
./run.sh
```

Lalu buka <http://127.0.0.1:8000/docs>.

Tanpa script, cukup 2 baris:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Stop server: `Ctrl+C`. Cek hidup atau tidak: `curl http://127.0.0.1:8000/health`.

Mau jalan di background (tetap hidup walau terminal ditutup)?

```bash
setsid nohup ./run.sh > /tmp/hadirin.log 2>&1 < /dev/null &
# lihat log: tail -f /tmp/hadirin.log
# matikan:  pkill -f "uvicorn app.main:app"
```

---

## 1. Prasyarat

- **Python 3.10+** (repo ini dites dengan 3.14)
- Project **Supabase** (URL + service role key)
- Git

---

## 2. Setup

```bash
# 1. Clone & masuk ke folder
git clone <repo-url> Hadirin-Backend-Model
cd Hadirin-Backend-Model

# 2. Buat virtualenv
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependency
pip install -r requirements.txt
```

> `torch` + `torchvision` cukup besar (± 1–2 GB). Jika punya GPU, install build CUDA
> sesuai versi driver. Tanpa GPU, versi CPU sudah cukup.

---

## 3. Konfigurasi `.env`

```bash
cp .env.example .env
```

Lalu isi nilai wajib berikut:

| Variabel | Keterangan |
|---|---|
| `SUPABASE_URL` | URL project Supabase, mis. `https://xxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | **Service role key** (bukan anon key) |
| `JWT_SECRET_KEY` | String acak panjang untuk menandatangani token |
| `DOSEN_DEFAULT_PASSWORD` | Password login dosen (opsional, kosong = login dosen 503) |

Variabel lain (GPS geofence, TTL QR, threshold wajah, nama bucket storage, CORS) sudah punya
default yang wajar — lihat `.env.example` untuk daftar lengkap.

> ⚠️ `.env` berisi rahasia dan **sudah di-ignore git**. Jangan commit.

---

## 4. Siapkan Database Supabase

Jalankan SQL berikut **berurutan** di **Supabase Dashboard → SQL Editor**:

1. `app/db/schema.sql` — tabel, enum, index, trigger, view
2. `app/db/seed.sql` — data awal (prodi, dosen, kelas, mahasiswa demo)
3. `app/db/rls.sql` — Row Level Security
4. `app/db/auth_hook.sql` — custom JWT claims

Setelah langkah 4, aktifkan hook di dashboard:

> **Authentication → Hooks → Add Hook → Custom Access Token**
> Schema: `public` | Function: `custom_access_token_hook`

Detail tabel, RLS, dan bucket storage: [`app/db/README.md`](app/db/README.md).

### Bucket Storage (buat manual, semua Private)

| Bucket | Isi |
|---|---|
| `foto-wajah` | Foto registrasi wajah mahasiswa |
| `foto-presensi` | Foto capture saat absensi |
| `dokumen-pengajuan` | Surat izin / surat dokter |

### Seed akun Auth (opsional)

Membuat akun Supabase Auth untuk mahasiswa seed + 2 akun demo QA:

```bash
python -m scripts.seed_auth_and_demo
# reset password akun yang sudah ter-link:
python -m scripts.seed_auth_and_demo --reset-passwords
```

### Seed akun Dosen Testing + jadwal (idempotent)

Membuat satu dosen dummy (`Dosen Testing`, `dosentesting@hadirin.test` / `dosen123`)
di Supabase Auth **dan** tabel `dosen`, lalu menambahkan jadwal Senin-Jumat untuk
**seluruh kelas & ruangan** yang sudah ada. Aman dijalankan berulang kali.

```bash
python -m scripts.seed_dosen_testing --dry-run  # lihat rencana, tanpa menulis
python -m scripts.seed_dosen_testing            # terapkan seed
```

Kredensial dosen dummy:

| Field | Nilai |
|---|---|
| NIP | `999999999001` |
| Nama | `Dosen Testing` |
| Email | `dosentesting@hadirin.test` |
| Password | `dosen123` |

Seed hanya menambahkan baris baru (UUID deterministik). Baris lama tidak diubah atau
dihapus. Untuk memeriksa hasilnya lewat SQL Editor, jalankan
`supabase/verify_seed_dosen_testing.sql` (read-only).

---

## 5. Model Face Recognition

Bobot model harus ada di `ml/models/weights/`:

```
ml/models/weights/
├── MobileFace_Net
├── pnet_Weights
├── rnet_Weights
└── onet_Weights
```

Jika folder ini kosong, endpoint presensi wajah tidak akan berfungsi.
Cek kesiapan via `GET /health` → `"ml_weights_ready": true`.

---

## 6. Jalankan Server

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Buka:

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- Health: <http://127.0.0.1:8000/health>

Verifikasi cepat:

```bash
curl http://127.0.0.1:8000/health
# {"status":"healthy","database":"connected","ml_weights_ready":true}
```

---

## 7. Ringkasan Endpoint

| Grup | Base path | Contoh |
|---|---|---|
| Auth | `/auth` | `POST /auth/login`, `GET /auth/check-nim/{nim}` |
| Dosen | `/auth/dosen/login`, `/dosen` | `GET /dosen/dashboard`, `GET /dosen/matkul?kelas_id=...&tanggal=YYYY-MM-DD`, `POST /dosen/sesi-presensi/{id}/qr` |
| Mahasiswa | `/mahasiswa` | `GET /mahasiswa/me`, `GET /mahasiswa/jadwal` |
| Wajah | `/mahasiswa/wajah` | `POST /mahasiswa/wajah`, `POST /mahasiswa/wajah/verify` |
| Pengajuan | `/mahasiswa/pengajuan` | `POST /mahasiswa/pengajuan` |
| Presensi | `/attendance` | `POST /attendance/qr`, `/gps`, `/face` |
| Health | `/health` | probe DB + bobot ML |

Autentikasi memakai header `Authorization: Bearer <token>`.

### Mata kuliah di sisi dosen (bergantung kelas + tanggal)

`GET /dosen/matkul?kelas_id=<uuid>&tanggal=YYYY-MM-DD` hanya mengembalikan mata kuliah
dari **jadwal dosen yang sedang login**, untuk kelas yang dipilih, pada hari hasil
konversi `tanggal` (Senin–Jumat). Tidak mengambil seluruh `mata_kuliah` di database.
Contoh:

```bash
curl -H "Authorization: Bearer <token-dosen>" \
  "http://127.0.0.1:8000/dosen/matkul?kelas_id=22222222-0000-0000-0000-000000000005&tanggal=2026-11-23"
```

---

## 8. Menjalankan Test

Test integrasi memukul **Supabase live** (bukan mock), jadi `.env` harus valid dan
database sudah di-seed.

```bash
source .venv/bin/activate
pytest                      # semua test
pytest qa/integration/test_auth.py -v
pytest -k presensi -v
```

---

## 9. Troubleshooting

| Masalah | Penyebab / Solusi |
|---|---|
| `ValidationError` saat start | Ada variabel wajib kosong di `.env` (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `JWT_SECRET_KEY`) |
| `/health` → `database: error` | URL/key salah, atau schema belum dijalankan |
| `/health` → `ml_weights_ready: false` | File bobot tidak ada di `ml/models/weights/` |
| Login dosen 503 | `DOSEN_DEFAULT_PASSWORD` kosong dan dosen belum terhubung Supabase Auth |
| Absensi GPS ditolak | Koordinat di luar geofence / akurasi > `GEOFENCE_MAX_ACCURACY_METERS` |
| QR kedaluwarsa | Token berlaku `QR_TOKEN_TTL_SECONDS` (default 30 detik) |
| Import `torch` lambat | Normal pada first load; model dimuat lazy |

---

## Struktur Singkat

```
app/
├── main.py          # entrypoint FastAPI
├── api/routes/      # endpoint per domain
├── core/            # config, security, exceptions
├── db/              # client Supabase + repository + SQL setup
├── schemas/         # Pydantic request/response
└── services/        # business logic (presensi, wajah, dsb.)
ml/                  # MTCNN alignment + MobileFaceNet embedding
qa/integration/      # test integrasi live
scripts/             # seed tooling
supabase/            # konfigurasi & migration Supabase CLI
```
