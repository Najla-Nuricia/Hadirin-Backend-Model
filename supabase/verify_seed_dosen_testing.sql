-- ============================================================
-- HADIRIN — Verifikasi seed "Dosen Testing" (READ-ONLY)
-- Jalankan di Supabase SQL Editor setelah scripts/seed_dosen_testing.py
-- ============================================================

-- 1. Profil dosen + tautan Supabase Auth
SELECT d.nip, d.nama, d.email, d.auth_user_id, u.email AS auth_email, u.email_confirmed_at
FROM dosen d
LEFT JOIN auth.users u ON u.id = d.auth_user_id
WHERE d.nip = '999999999001';

-- 2. Ringkasan jadwal per hari (harus Senin-Jumat, pagi-sore)
SELECT hari,
       COUNT(*)                        AS jumlah_jadwal,
       MIN(sesi_mulai)                 AS sesi_mulai,
       MAX(sesi_selesai)               AS sesi_selesai,
       COUNT(DISTINCT kelas_id)        AS jumlah_kelas,
       COUNT(DISTINCT ruangan_kode)    AS jumlah_ruangan
FROM jadwal_kuliah
WHERE dosen_nip = '999999999001'
GROUP BY hari
ORDER BY CASE hari
    WHEN 'senin' THEN 1 WHEN 'selasa' THEN 2 WHEN 'rabu' THEN 3
    WHEN 'kamis' THEN 4 WHEN 'jumat' THEN 5 ELSE 6 END;

-- 3. Cakupan seluruh kelas & ruangan yang tersedia
SELECT 'kelas' AS jenis, k.nama AS nama,
       COUNT(j.id) AS jumlah_jadwal
FROM kelas k
LEFT JOIN jadwal_kuliah j
       ON j.kelas_id = k.id AND j.dosen_nip = '999999999001'
GROUP BY k.nama
UNION ALL
SELECT 'ruangan', r.kode, COUNT(j.id)
FROM ruangan r
LEFT JOIN jadwal_kuliah j
       ON j.ruangan_kode = r.kode AND j.dosen_nip = '999999999001'
GROUP BY r.kode
ORDER BY 1, 2;

-- 4. Cek bentrok: jadwal dosen dummy vs jadwal lain (hasil harus 0 baris)
SELECT a.id AS jadwal_seed, b.id AS jadwal_lain, a.hari,
       a.kelas_id, a.ruangan_kode,
       a.sesi_mulai, a.sesi_selesai,
       b.sesi_mulai AS bentrok_mulai, b.sesi_selesai AS bentrok_selesai
FROM jadwal_kuliah a
JOIN jadwal_kuliah b
  ON b.id <> a.id
 AND b.hari = a.hari
 AND b.sesi_mulai <= a.sesi_selesai
 AND a.sesi_mulai <= b.sesi_selesai
 AND (b.kelas_id = a.kelas_id OR b.ruangan_kode = a.ruangan_kode)
WHERE a.dosen_nip = '999999999001';

-- 5. Relasi lengkap lewat view (semua field harus terisi)
SELECT hari, semester, tahun_ajaran, matkul_kode, matkul_nama,
       dosen_nip, dosen_nama, prodi_kode, kelas_nama, ruangan_kode,
       jam_mulai, jam_selesai
FROM v_jadwal_lengkap
WHERE dosen_nip = '999999999001'
ORDER BY CASE hari
    WHEN 'senin' THEN 1 WHEN 'selasa' THEN 2 WHEN 'rabu' THEN 3
    WHEN 'kamis' THEN 4 WHEN 'jumat' THEN 5 ELSE 6 END,
    sesi_mulai, kelas_nama;
