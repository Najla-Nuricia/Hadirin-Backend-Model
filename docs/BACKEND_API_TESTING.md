# Automated API Testing — Hadirin Backend

## 1. Audit test existing

Sumber: `qa/unit` (21 test), `qa/integration` (63 test), `pytest.ini`.

Sudah teruji: login/register mahasiswa, admin & dosen; JWT/tampered token; role rejection;
CRUD tahun ajaran & mata kuliah (happy path + token wajib); CRUD jadwal admin (list filter,
create, update, overlap kelas, relasi invalid); dashboard/kehadiran/QR dosen; presensi GPS & QR;
pengajuan; wajah; profile & riwayat mahasiswa; health.

Celah yang ditemukan (tidak diduplikasi):

- `POST/GET/PUT/DELETE /admin/whitelist-nim` hanya punya unit test service/schema, **belum ada API test**.
- Endpoint opsi form jadwal (`/admin/dosen`, `/admin/program-studi`, `/admin/ruangan`,
  `/admin/sesi-kuliah`) dan perluasan `GET /kelas` **belum punya test sama sekali**.
- Master data hanya diuji happy path + auth; belum ada duplikat, payload invalid, delete terikat relasi.
- Jadwal admin belum diuji: ketidaksesuaian semester matkul, konflik ruangan, sesi tidak ada, 422, role dosen.
- `GET /auth/check-nim/{nim}` belum punya API test.

## 2. Fitur & endpoint yang diuji (test baru)

| Grup | Endpoint |
|---|---|
| Whitelist NIM | `POST/GET/DELETE /admin/whitelist-nim` |
| Opsi form jadwal | `GET /admin/dosen`, `/admin/program-studi`, `/admin/ruangan`, `/admin/sesi-kuliah`, `GET /kelas` |
| Master data (negatif) | `POST/DELETE /admin/tahun-ajaran`, `POST/DELETE /admin/mata-kuliah` |
| Jadwal admin (business) | `POST /admin/jadwal` |
| Status NIM | `GET /auth/check-nim/{nim}` |

## 3. Skenario test baru (21 test)

### `qa/api/test_admin_whitelist_api.py` (5)
1. Positive: tambah NIM → 201, `status = "Belum Registrasi"`, NIM ter-trim.
2. Business: NIM duplikat → 409.
3. Positive: list + search menampilkan status `"Sudah Registrasi"`, nama & kelas dari relasi mahasiswa.
4. Business: hapus NIM yang sudah punya mahasiswa → 409; NIM belum registrasi → 200.
5. Auth: tanpa token → 401; token mahasiswa/dosen → 403.

### `qa/api/test_admin_options_api.py` (4)
1. Positive: `/admin/dosen` memuat `Dosen Testing` (NIP `999999999001`) + filter `?search=`.
2. Positive: `/admin/program-studi`, `/admin/ruangan`, `/admin/sesi-kuliah`; jam dinormalisasi `HH:mm`.
3. Positive: `GET /kelas` mengembalikan `tingkat`, `program_studi_kode`, `tahun_ajaran_id` dan filter tahun ajaran/prodi; tahun ajaran unknown → kosong.
4. Auth: 401 tanpa token, 403 untuk mahasiswa & dosen di keempat endpoint admin.

### `qa/api/test_admin_master_data_validation_api.py` (5)
1. Business: tahun ajaran duplikat → 409.
2. Negative: format tahun `2026-2027` → 422.
3. Business: hapus tahun ajaran yang masih direferensikan → 409.
4. Business: kode mata kuliah duplikat → 409; `semester = 0` → 422.
5. Business: hapus mata kuliah yang dipakai jadwal → 409.

### `qa/api/test_admin_jadwal_business_api.py` (4)
1. Business: semester matkul genap dengan periode `ganjil` → 400.
2. Business: bentrok ruangan → 409.
3. Business: nomor sesi tidak tersedia → 400.
4. Negative: `hari = minggu` → 422; token dosen → 403.

### `qa/api/test_check_nim_api.py` (3)
1. Positive: NIM ter-whitelist belum registrasi → `can_register = true`, `siap_registrasi`.
2. Business: NIM ter-whitelist sudah ada mahasiswa → `sudah_terdaftar`.
3. Negative: NIM tidak ter-whitelist → `belum_whitelist`.

## 4. Database testing terpisah

`qa/api/conftest.py` menyuntikkan **in-memory fake repository** lewat FastAPI `dependency_overrides`.
Tidak ada koneksi ke Supabase dev/prod; tidak ada data yang ditulis ke DB sungguhan. Request tetap
melewati routing, Pydantic, JWT, dan pengecekan role secara penuh via `TestClient`.
Fixture `_isolate_dependency_overrides` (autouse) membersihkan override antar test.

## 5. File yang dibuat / diubah

- Baru: `qa/api/conftest.py`, `qa/api/test_admin_whitelist_api.py`,
  `qa/api/test_admin_options_api.py`, `qa/api/test_admin_master_data_validation_api.py`,
  `qa/api/test_admin_jadwal_business_api.py`, `qa/api/test_check_nim_api.py`,
  `qa/__init__.py`, `qa/api/__init__.py`.
- Diubah: `pytest.ini` (`testpaths` ditambah `qa/api`).
- Tidak ada business logic backend yang diubah.

## 6. Hasil validasi

Dijalankan dengan `.venv/bin/python -m pytest`:

| Perintah | Hasil |
|---|---|
| `pytest qa/api -q` | **21 passed** |
| `pytest qa/unit -q` | **21 passed** |

## 7. Bug / kendala API yang ditemukan (belum diperbaiki)

1. **Status whitelist tidak membedakan profil vs akun.** `WhitelistNimService._item()` dan
   `GET /auth/check-nim/{nim}` menyatakan "Sudah Registrasi" hanya karena ada baris `mahasiswa`,
   tanpa memeriksa `auth_user_id`. Mahasiswa hasil seed/test tanpa akun Auth ikut terlapor sudah registrasi.
2. **Migrasi auto-whitelist.** `supabase/migrations/20261122000001_whitelist_nim.sql` mengisi
   `whitelist_nim` dari seluruh `mahasiswa`, sehingga NIM lama otomatis terdaftar.
3. **Pencarian whitelist by nama tidak bekerja.** Repository memfilter `nim` dulu, lalu service
   memfilter ulang nama/kelas → `?search=<nama>` selalu menghasilkan 0 baris.
4. **Fallback frontend `checkNim` terbalik.** Saat backend gagal, `dummy_student_auth_repository.dart`
   memakai `whitelisted: !_accounts.containsKey(nim)` dan `registered` dari daftar demo lokal.
5. **Test infra (bukan API):** generator NIM pada `qa/integration/conftest.py` memakai hex,
   melanggar validator numerik `RegisterRequest`/`WhitelistNimWriteRequest`; dan test membuat
   mahasiswa tanpa mengisi whitelist baru. Perlu diperbaiki di fixture test, bukan di business logic.

Semua temuan di atas sengaja **tidak diperbaiki** pada task ini sesuai instruksi.
