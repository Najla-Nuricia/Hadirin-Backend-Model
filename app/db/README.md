# Hadirin — Database Setup (Supabase)

Folder ini berisi semua file SQL untuk inisialisasi database Hadirin di Supabase.

## 📁 Struktur File

```
app/db/
├── schema.sql    ← Buat semua tabel, enum, trigger, view
├── seed.sql      ← Data awal (program studi, dosen, kelas, mahasiswa demo)
├── rls.sql       ← Row Level Security per peran (admin / dosen / mahasiswa)
└── auth_hook.sql ← Custom JWT claims + fungsi link akun Auth ke tabel
```

---

## 🚀 Cara Menjalankan (urut!)

Jalankan di **Supabase Dashboard → SQL Editor**:

### Langkah 1 — Schema
```
Jalankan: schema.sql
```
Membuat semua tabel, enum, index, trigger, dan view.

### Langkah 2 — Seed Data
```
Jalankan: seed.sql
```

### Langkah 3 — RLS
```
Jalankan: rls.sql
```

### Langkah 4 — Auth Hook ⚠️ WAJIB
```
Jalankan: auth_hook.sql
```
Lalu aktifkan di Dashboard:
> **Authentication → Hooks → Add Hook → Custom Access Token**
> Schema: `public` | Function: `custom_access_token_hook`

---

## 🚀 Cara Menjalankan (detail)

### Langkah 1 — Schema
```
Jalankan: schema.sql
```
Membuat semua tabel, enum, index, trigger, dan view.

### Langkah 2 — Seed Data
```
Jalankan: seed.sql
```
Mengisi data awal:
- 2 Program Studi (D4-TI, D2-PPLS)
- 4 Tahun Ajaran (2023/2024 – 2026/2027)
- 12 Sesi Kuliah (07:00 – 18:00)
- 7 Ruangan (J301, J302, RT01, RT02, LPR1-3)
- 15 Mata Kuliah (TI101 – TI602)
- 5 Dosen
- 9 Kelas (TI-1A s/d TI-4A, PPLS-1A, PPLS-2A)
- 11 Mahasiswa (termasuk akun demo Flutter)
- 7 Jadwal Kuliah
- 2 Sesi Presensi + data kehadiran contoh

### Langkah 3 — RLS
```
Jalankan: rls.sql
```
Mengaktifkan Row Level Security untuk semua tabel.

---

## 🗄️ Diagram Tabel

```
program_studi ←──── kelas ──────────── mahasiswa
                      │                    │
tahun_ajaran ─────────┘              foto_wajah
                      │
sesi_kuliah ─── jadwal_kuliah ─── dosen
                      │
ruangan ──────────────┘
                      │
mata_kuliah ──────────┘
                      │
                sesi_presensi
                      │
                  kehadiran
                      │
         pengajuan_ketidakhadiran
```

---

## 🔐 Kebijakan Akses (RLS)

| Tabel                      | Admin | Dosen (kelas sendiri) | Mahasiswa (data sendiri) |
|----------------------------|:-----:|:---------------------:|:------------------------:|
| program_studi              | CRUD  | R                     | R                        |
| tahun_ajaran               | CRUD  | R                     | R                        |
| sesi_kuliah                | CRUD  | R                     | R                        |
| ruangan                    | CRUD  | R                     | R                        |
| mata_kuliah                | CRUD  | R                     | R                        |
| dosen                      | CRUD  | R + U self            | R                        |
| kelas                      | CRUD  | R                     | R                        |
| mahasiswa                  | CRUD  | R (kelasnya)          | R + U self               |
| foto_wajah                 | CRUD  | —                     | R + C self               |
| jadwal_kuliah              | CRUD  | R                     | R                        |
| sesi_presensi              | CRUD  | R + C + U (miliknya)  | R (kelasnya)             |
| kehadiran                  | CRUD  | R + U (sesinya)       | R + C self               |
| pengajuan_ketidakhadiran   | CRUD  | R + U (sesinya)       | R + C self               |
| admin                      | CRUD  | —                     | —                        |

> **C**reate · **R**ead · **U**pdate · **D**elete

---

## 🏷️ Peran JWT

Setiap user login via Supabase Auth harus memiliki custom claim di JWT:

```json
// Admin
{ "role": "admin" }

// Dosen
{ "role": "dosen", "nip": "198501012010121001" }

// Mahasiswa
{ "role": "mahasiswa", "nim": "2211001" }
```

Set custom claims melalui **Supabase Auth Hook** atau function PostgreSQL saat user login.

---

## 📦 Views Tersedia

| View                  | Kegunaan                                              |
|-----------------------|-------------------------------------------------------|
| `v_jadwal_lengkap`    | Jadwal kuliah lengkap dengan nama dosen, kelas, dll   |
| `v_rekap_kehadiran`   | Rekap kehadiran per mahasiswa per sesi presensi       |

---

## 🗂️ Supabase Storage Buckets (buat manual)

| Bucket              | Isi                                      | Akses        |
|---------------------|------------------------------------------|--------------|
| `foto-wajah`        | Foto registrasi wajah mahasiswa          | Private      |
| `foto-presensi`     | Foto saat mahasiswa absen (ML capture)   | Private      |
| `dokumen-pengajuan` | Surat izin / surat dokter                | Private      |
