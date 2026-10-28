-- ============================================================
-- HADIRIN — Supabase Database Schema
-- Jalankan file ini di Supabase SQL Editor
-- Urutan: schema → seed → rls
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- EXTENSIONS
-- ─────────────────────────────────────────────────────────────
-- uuid-ossp tidak diperlukan, Supabase sudah punya gen_random_uuid() bawaan
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────────────────────────────
-- ENUM TYPES
-- ─────────────────────────────────────────────────────────────
CREATE TYPE status_tahun_ajaran  AS ENUM ('aktif', 'non_aktif');
CREATE TYPE status_kelas         AS ENUM ('aktif', 'non_aktif');
CREATE TYPE hari_kuliah          AS ENUM ('senin', 'selasa', 'rabu', 'kamis', 'jumat', 'sabtu');
CREATE TYPE semester_periode     AS ENUM ('ganjil', 'genap');
CREATE TYPE status_kehadiran     AS ENUM ('hadir', 'izin', 'sakit', 'alfa');
CREATE TYPE peran_pengguna       AS ENUM ('admin', 'dosen', 'mahasiswa');
CREATE TYPE status_pengajuan     AS ENUM ('pending', 'diterima', 'ditolak');

-- ─────────────────────────────────────────────────────────────
-- 1. PROGRAM STUDI
-- ─────────────────────────────────────────────────────────────
CREATE TABLE program_studi (
    kode        VARCHAR(20)  PRIMARY KEY,
    nama        VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- 2. TAHUN AJARAN
-- ─────────────────────────────────────────────────────────────
CREATE TABLE tahun_ajaran (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tahun            VARCHAR(10)  NOT NULL UNIQUE,   -- contoh: "2026/2027"
    status           status_tahun_ajaran NOT NULL DEFAULT 'non_aktif',
    semester_ganjil  BOOLEAN      NOT NULL DEFAULT TRUE,
    semester_genap   BOOLEAN      NOT NULL DEFAULT TRUE,
    tanggal_mulai    DATE,
    tanggal_selesai  DATE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Hanya satu tahun ajaran yang boleh aktif
CREATE UNIQUE INDEX idx_tahun_ajaran_aktif
    ON tahun_ajaran (status)
    WHERE status = 'aktif';

-- ─────────────────────────────────────────────────────────────
-- 3. SESI KULIAH (jam per slot)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE sesi_kuliah (
    nomor        SMALLINT    PRIMARY KEY,   -- 1 – 12
    jam_mulai    TIME        NOT NULL,
    jam_selesai  TIME        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- 4. RUANGAN
-- ─────────────────────────────────────────────────────────────
CREATE TABLE ruangan (
    kode        VARCHAR(20)  PRIMARY KEY,
    nama        VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- 5. MATA KULIAH
-- ─────────────────────────────────────────────────────────────
CREATE TABLE mata_kuliah (
    kode        VARCHAR(20)  PRIMARY KEY,
    nama        VARCHAR(100) NOT NULL,
    semester    SMALLINT     NOT NULL CHECK (semester BETWEEN 1 AND 8),
    sks         SMALLINT     NOT NULL CHECK (sks > 0),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- 6. DOSEN
-- ─────────────────────────────────────────────────────────────
CREATE TABLE dosen (
    nip          VARCHAR(30)  PRIMARY KEY,
    nama         VARCHAR(100) NOT NULL,
    email        VARCHAR(150) UNIQUE,
    no_hp        VARCHAR(20),
    auth_user_id UUID         UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- 7. KELAS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE kelas (
    id                 UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    nama               VARCHAR(20)  NOT NULL,
    tingkat            SMALLINT     NOT NULL CHECK (tingkat BETWEEN 1 AND 8),
    program_studi_kode VARCHAR(20)  NOT NULL REFERENCES program_studi(kode) ON DELETE RESTRICT,
    tahun_ajaran_id    UUID         NOT NULL REFERENCES tahun_ajaran(id)    ON DELETE RESTRICT,
    kapasitas          SMALLINT     NOT NULL DEFAULT 30 CHECK (kapasitas > 0),
    status             status_kelas NOT NULL DEFAULT 'aktif',
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (nama, tahun_ajaran_id)
);

-- ─────────────────────────────────────────────────────────────
-- 8. MAHASISWA
-- ─────────────────────────────────────────────────────────────
CREATE TABLE mahasiswa (
    nim           VARCHAR(20)  PRIMARY KEY,
    nama_lengkap  VARCHAR(100) NOT NULL,
    email         VARCHAR(150) UNIQUE,
    no_hp         VARCHAR(20),
    kelas_id      UUID         REFERENCES kelas(id) ON DELETE SET NULL,
    auth_user_id  UUID         UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- 9. FOTO WAJAH MAHASISWA (untuk face recognition)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE foto_wajah (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    nim           VARCHAR(20)  NOT NULL REFERENCES mahasiswa(nim) ON DELETE CASCADE,
    storage_path  TEXT         NOT NULL,
    embedding     JSONB,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_foto_wajah_nim ON foto_wajah (nim);

-- ─────────────────────────────────────────────────────────────
-- 10. JADWAL KULIAH
-- ─────────────────────────────────────────────────────────────
CREATE TABLE jadwal_kuliah (
    id                  UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    tahun_ajaran_id     UUID             NOT NULL REFERENCES tahun_ajaran(id)    ON DELETE RESTRICT,
    mata_kuliah_kode    VARCHAR(20)      NOT NULL REFERENCES mata_kuliah(kode)   ON DELETE RESTRICT,
    dosen_nip           VARCHAR(30)      NOT NULL REFERENCES dosen(nip)          ON DELETE RESTRICT,
    program_studi_kode  VARCHAR(20)      NOT NULL REFERENCES program_studi(kode) ON DELETE RESTRICT,
    kelas_id            UUID             NOT NULL REFERENCES kelas(id)           ON DELETE RESTRICT,
    ruangan_kode        VARCHAR(20)      NOT NULL REFERENCES ruangan(kode)       ON DELETE RESTRICT,
    hari                hari_kuliah      NOT NULL,
    sesi_mulai          SMALLINT         NOT NULL REFERENCES sesi_kuliah(nomor),
    sesi_selesai        SMALLINT         NOT NULL REFERENCES sesi_kuliah(nomor),
    semester            semester_periode NOT NULL,
    created_at          TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    CHECK (sesi_mulai <= sesi_selesai)
);

CREATE INDEX idx_jadwal_tahun_kelas  ON jadwal_kuliah (tahun_ajaran_id, kelas_id);
CREATE INDEX idx_jadwal_dosen_hari   ON jadwal_kuliah (dosen_nip, hari);
CREATE INDEX idx_jadwal_ruangan_hari ON jadwal_kuliah (ruangan_kode, hari);

-- ─────────────────────────────────────────────────────────────
-- 11. SESI PRESENSI (dibuka dosen per pertemuan)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE sesi_presensi (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    jadwal_id      UUID        NOT NULL REFERENCES jadwal_kuliah(id) ON DELETE CASCADE,
    tanggal        DATE        NOT NULL,
    qr_token       TEXT        UNIQUE,
    qr_expires_at  TIMESTAMPTZ,
    is_open        BOOLEAN     NOT NULL DEFAULT FALSE,
    dibuka_oleh    VARCHAR(30) REFERENCES dosen(nip),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (jadwal_id, tanggal)
);

CREATE INDEX idx_sesi_presensi_jadwal  ON sesi_presensi (jadwal_id);
CREATE INDEX idx_sesi_presensi_tanggal ON sesi_presensi (tanggal);

-- ─────────────────────────────────────────────────────────────
-- 12. KEHADIRAN
-- ─────────────────────────────────────────────────────────────
CREATE TABLE kehadiran (
    id               UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    sesi_presensi_id UUID             NOT NULL REFERENCES sesi_presensi(id) ON DELETE CASCADE,
    nim              VARCHAR(20)      NOT NULL REFERENCES mahasiswa(nim)    ON DELETE CASCADE,
    status           status_kehadiran NOT NULL DEFAULT 'alfa',
    jam_masuk        TIME,
    catatan          TEXT,
    face_photo_path  TEXT,
    created_at       TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    UNIQUE (sesi_presensi_id, nim)
);

CREATE INDEX idx_kehadiran_nim    ON kehadiran (nim);
CREATE INDEX idx_kehadiran_sesi   ON kehadiran (sesi_presensi_id);
CREATE INDEX idx_kehadiran_status ON kehadiran (status);

-- ─────────────────────────────────────────────────────────────
-- 13. PENGAJUAN IZIN / SAKIT
-- ─────────────────────────────────────────────────────────────
CREATE TABLE pengajuan_ketidakhadiran (
    id               UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    kehadiran_id     UUID             NOT NULL UNIQUE REFERENCES kehadiran(id) ON DELETE CASCADE,
    jenis            status_kehadiran NOT NULL CHECK (jenis IN ('izin', 'sakit')),
    alasan           TEXT             NOT NULL,
    dokumen_path     TEXT,
    status_pengajuan status_pengajuan NOT NULL DEFAULT 'pending',
    diputus_oleh     VARCHAR(30)      REFERENCES dosen(nip),
    catatan_dosen    TEXT,
    created_at       TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pengajuan_kehadiran ON pengajuan_ketidakhadiran (kehadiran_id);
CREATE INDEX idx_pengajuan_status    ON pengajuan_ketidakhadiran (status_pengajuan);

-- ─────────────────────────────────────────────────────────────
-- 14. ADMIN
-- ─────────────────────────────────────────────────────────────
CREATE TABLE admin (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    nama          VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    auth_user_id  UUID         UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- TRIGGER: auto-update updated_at
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'program_studi', 'tahun_ajaran', 'ruangan', 'mata_kuliah',
        'dosen', 'kelas', 'mahasiswa', 'jadwal_kuliah',
        'sesi_presensi', 'kehadiran', 'pengajuan_ketidakhadiran', 'admin'
    ]
    LOOP
        EXECUTE format(
            'CREATE TRIGGER set_updated_at
             BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();',
            tbl
        );
    END LOOP;
END;
$$;

-- ─────────────────────────────────────────────────────────────
-- TRIGGER: saat tahun ajaran di-set aktif, nonaktifkan yang lain
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION trigger_single_active_tahun_ajaran()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'aktif' THEN
        UPDATE tahun_ajaran
        SET status = 'non_aktif'
        WHERE id <> NEW.id AND status = 'aktif';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER single_active_tahun_ajaran
BEFORE INSERT OR UPDATE OF status ON tahun_ajaran
FOR EACH ROW
WHEN (NEW.status = 'aktif')
EXECUTE FUNCTION trigger_single_active_tahun_ajaran();

-- ─────────────────────────────────────────────────────────────
-- VIEWS
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_jadwal_lengkap WITH (security_invoker = true) AS
SELECT
    j.id,
    j.hari,
    j.semester,
    ta.tahun                AS tahun_ajaran,
    mk.kode                 AS matkul_kode,
    mk.nama                 AS matkul_nama,
    mk.sks,
    d.nip                   AS dosen_nip,
    d.nama                  AS dosen_nama,
    ps.kode                 AS prodi_kode,
    ps.nama                 AS prodi_nama,
    k.nama                  AS kelas_nama,
    k.tingkat               AS kelas_tingkat,
    r.kode                  AS ruangan_kode,
    r.nama                  AS ruangan_nama,
    sm.jam_mulai,
    ss.jam_selesai,
    j.sesi_mulai,
    j.sesi_selesai,
    j.created_at
FROM jadwal_kuliah j
JOIN tahun_ajaran  ta ON ta.id    = j.tahun_ajaran_id
JOIN mata_kuliah   mk ON mk.kode  = j.mata_kuliah_kode
JOIN dosen          d ON d.nip    = j.dosen_nip
JOIN program_studi ps ON ps.kode  = j.program_studi_kode
JOIN kelas          k ON k.id     = j.kelas_id
JOIN ruangan        r ON r.kode   = j.ruangan_kode
JOIN sesi_kuliah   sm ON sm.nomor = j.sesi_mulai
JOIN sesi_kuliah   ss ON ss.nomor = j.sesi_selesai;

CREATE OR REPLACE VIEW v_rekap_kehadiran WITH (security_invoker = true) AS
SELECT
    k.id                        AS kehadiran_id,
    sp.tanggal,
    sp.id                       AS sesi_presensi_id,
    j.id                        AS jadwal_id,
    mk.nama                     AS matkul_nama,
    kl.nama                     AS kelas_nama,
    d.nama                      AS dosen_nama,
    m.nim,
    m.nama_lengkap              AS nama_mahasiswa,
    k.status,
    k.jam_masuk,
    k.catatan,
    pk.status_pengajuan,
    pk.jenis                    AS jenis_pengajuan
FROM kehadiran k
JOIN sesi_presensi           sp ON sp.id       = k.sesi_presensi_id
JOIN jadwal_kuliah            j ON j.id        = sp.jadwal_id
JOIN mata_kuliah             mk ON mk.kode     = j.mata_kuliah_kode
JOIN kelas                   kl ON kl.id       = j.kelas_id
JOIN dosen                    d ON d.nip       = j.dosen_nip
JOIN mahasiswa                m ON m.nim       = k.nim
LEFT JOIN pengajuan_ketidakhadiran pk ON pk.kehadiran_id = k.id;
