-- ============================================================
-- HADIRIN — Row Level Security (RLS) Policies
-- Jalankan SETELAH schema.sql dan seed.sql
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- HELPER FUNCTION: ambil peran user dari metadata
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION auth_role()
RETURNS TEXT AS $$
    SELECT COALESCE(
        current_setting('request.jwt.claims', TRUE)::jsonb ->> 'role',
        ''
    );
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION auth_nim()
RETURNS TEXT AS $$
    SELECT COALESCE(
        current_setting('request.jwt.claims', TRUE)::jsonb ->> 'nim',
        ''
    );
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION auth_nip()
RETURNS TEXT AS $$
    SELECT COALESCE(
        current_setting('request.jwt.claims', TRUE)::jsonb ->> 'nip',
        ''
    );
$$ LANGUAGE sql STABLE;

-- ─────────────────────────────────────────────────────────────
-- AKTIFKAN RLS DI SEMUA TABEL
-- ─────────────────────────────────────────────────────────────
ALTER TABLE program_studi              ENABLE ROW LEVEL SECURITY;
ALTER TABLE tahun_ajaran               ENABLE ROW LEVEL SECURITY;
ALTER TABLE sesi_kuliah                ENABLE ROW LEVEL SECURITY;
ALTER TABLE ruangan                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE mata_kuliah                ENABLE ROW LEVEL SECURITY;
ALTER TABLE dosen                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE kelas                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE mahasiswa                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE foto_wajah                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE jadwal_kuliah              ENABLE ROW LEVEL SECURITY;
ALTER TABLE sesi_presensi              ENABLE ROW LEVEL SECURITY;
ALTER TABLE kehadiran                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE pengajuan_ketidakhadiran   ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin                      ENABLE ROW LEVEL SECURITY;

-- ─────────────────────────────────────────────────────────────
-- 1. PROGRAM STUDI — semua bisa baca, hanya admin bisa ubah
-- ─────────────────────────────────────────────────────────────
CREATE POLICY ps_select_all ON program_studi
    FOR SELECT USING (TRUE);

CREATE POLICY ps_modify_admin ON program_studi
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 2. TAHUN AJARAN — semua bisa baca, hanya admin bisa ubah
-- ─────────────────────────────────────────────────────────────
CREATE POLICY ta_select_all ON tahun_ajaran
    FOR SELECT USING (TRUE);

CREATE POLICY ta_modify_admin ON tahun_ajaran
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 3. SESI KULIAH — semua bisa baca, hanya admin bisa ubah
-- ─────────────────────────────────────────────────────────────
CREATE POLICY sk_select_all ON sesi_kuliah
    FOR SELECT USING (TRUE);

CREATE POLICY sk_modify_admin ON sesi_kuliah
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 4. RUANGAN — semua bisa baca, hanya admin bisa ubah
-- ─────────────────────────────────────────────────────────────
CREATE POLICY ruangan_select_all ON ruangan
    FOR SELECT USING (TRUE);

CREATE POLICY ruangan_modify_admin ON ruangan
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 5. MATA KULIAH — semua bisa baca, hanya admin bisa ubah
-- ─────────────────────────────────────────────────────────────
CREATE POLICY mk_select_all ON mata_kuliah
    FOR SELECT USING (TRUE);

CREATE POLICY mk_modify_admin ON mata_kuliah
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 6. DOSEN
--    - Admin: full access
--    - Dosen: bisa baca semua, update profil sendiri
--    - Mahasiswa: bisa baca (nama, nip saja — lewat view)
-- ─────────────────────────────────────────────────────────────
CREATE POLICY dosen_select_all ON dosen
    FOR SELECT USING (
        auth_role() IN ('admin', 'dosen', 'mahasiswa')
    );

CREATE POLICY dosen_update_self ON dosen
    FOR UPDATE USING (
        auth_role() = 'dosen' AND nip = auth_nip()
    );

CREATE POLICY dosen_modify_admin ON dosen
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 7. KELAS — semua bisa baca, hanya admin bisa ubah
-- ─────────────────────────────────────────────────────────────
CREATE POLICY kelas_select_all ON kelas
    FOR SELECT USING (TRUE);

CREATE POLICY kelas_modify_admin ON kelas
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 8. MAHASISWA
--    - Admin: full access
--    - Dosen: bisa baca mahasiswa di kelasnya
--    - Mahasiswa: bisa baca & update profil sendiri
-- ─────────────────────────────────────────────────────────────
CREATE POLICY mhs_select_admin ON mahasiswa
    FOR SELECT USING (auth_role() = 'admin');

CREATE POLICY mhs_select_dosen ON mahasiswa
    FOR SELECT USING (
        auth_role() = 'dosen'
        AND kelas_id IN (
            SELECT kelas_id FROM jadwal_kuliah
            WHERE dosen_nip = auth_nip()
        )
    );

CREATE POLICY mhs_select_self ON mahasiswa
    FOR SELECT USING (
        auth_role() = 'mahasiswa' AND nim = auth_nim()
    );

CREATE POLICY mhs_update_self ON mahasiswa
    FOR UPDATE USING (
        auth_role() = 'mahasiswa' AND nim = auth_nim()
    );

CREATE POLICY mhs_modify_admin ON mahasiswa
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 9. FOTO WAJAH
--    - Admin: full access
--    - Mahasiswa: lihat & kelola foto sendiri
--    - Dosen: tidak bisa akses langsung (lewat service ML)
-- ─────────────────────────────────────────────────────────────
CREATE POLICY foto_select_self ON foto_wajah
    FOR SELECT USING (
        auth_role() = 'mahasiswa' AND nim = auth_nim()
    );

CREATE POLICY foto_insert_self ON foto_wajah
    FOR INSERT WITH CHECK (
        auth_role() = 'mahasiswa' AND nim = auth_nim()
    );

CREATE POLICY foto_modify_admin ON foto_wajah
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 10. JADWAL KULIAH
--     - Semua bisa baca
--     - Hanya admin bisa ubah
-- ─────────────────────────────────────────────────────────────
CREATE POLICY jadwal_select_all ON jadwal_kuliah
    FOR SELECT USING (TRUE);

CREATE POLICY jadwal_modify_admin ON jadwal_kuliah
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 11. SESI PRESENSI
--     - Admin & dosen bisa baca semua
--     - Mahasiswa bisa baca sesi dari jadwal kelasnya
--     - Dosen bisa buat & buka sesi dari jadwalnya sendiri
--     - Admin bisa ubah semua
-- ─────────────────────────────────────────────────────────────
CREATE POLICY sp_select_admin_dosen ON sesi_presensi
    FOR SELECT USING (auth_role() IN ('admin', 'dosen'));

CREATE POLICY sp_select_mhs ON sesi_presensi
    FOR SELECT USING (
        auth_role() = 'mahasiswa'
        AND jadwal_id IN (
            SELECT j.id FROM jadwal_kuliah j
            JOIN mahasiswa m ON m.kelas_id = j.kelas_id
            WHERE m.nim = auth_nim()
        )
    );

CREATE POLICY sp_insert_dosen ON sesi_presensi
    FOR INSERT WITH CHECK (
        auth_role() = 'dosen'
        AND jadwal_id IN (
            SELECT id FROM jadwal_kuliah
            WHERE dosen_nip = auth_nip()
        )
    );

CREATE POLICY sp_update_dosen ON sesi_presensi
    FOR UPDATE USING (
        auth_role() = 'dosen'
        AND dibuka_oleh = auth_nip()
    );

CREATE POLICY sp_modify_admin ON sesi_presensi
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 12. KEHADIRAN
--     - Admin: full access
--     - Dosen: baca kehadiran sesi yang ia punya
--     - Mahasiswa: baca & insert kehadiran sendiri
-- ─────────────────────────────────────────────────────────────
CREATE POLICY keh_select_admin ON kehadiran
    FOR SELECT USING (auth_role() = 'admin');

CREATE POLICY keh_select_dosen ON kehadiran
    FOR SELECT USING (
        auth_role() = 'dosen'
        AND sesi_presensi_id IN (
            SELECT sp.id FROM sesi_presensi sp
            JOIN jadwal_kuliah j ON j.id = sp.jadwal_id
            WHERE j.dosen_nip = auth_nip()
        )
    );

CREATE POLICY keh_select_self ON kehadiran
    FOR SELECT USING (
        auth_role() = 'mahasiswa' AND nim = auth_nim()
    );

CREATE POLICY keh_insert_self ON kehadiran
    FOR INSERT WITH CHECK (
        auth_role() = 'mahasiswa' AND nim = auth_nim()
    );

CREATE POLICY keh_update_dosen ON kehadiran
    FOR UPDATE USING (
        auth_role() = 'dosen'
        AND sesi_presensi_id IN (
            SELECT sp.id FROM sesi_presensi sp
            JOIN jadwal_kuliah j ON j.id = sp.jadwal_id
            WHERE j.dosen_nip = auth_nip()
        )
    );

CREATE POLICY keh_modify_admin ON kehadiran
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 13. PENGAJUAN KETIDAKHADIRAN
--     - Admin: full access
--     - Dosen: baca & update (terima/tolak) pengajuan kelasnya
--     - Mahasiswa: baca & buat pengajuan sendiri
-- ─────────────────────────────────────────────────────────────
CREATE POLICY peng_select_admin ON pengajuan_ketidakhadiran
    FOR SELECT USING (auth_role() = 'admin');

CREATE POLICY peng_select_dosen ON pengajuan_ketidakhadiran
    FOR SELECT USING (
        auth_role() = 'dosen'
        AND kehadiran_id IN (
            SELECT k.id FROM kehadiran k
            JOIN sesi_presensi sp ON sp.id = k.sesi_presensi_id
            JOIN jadwal_kuliah j  ON j.id  = sp.jadwal_id
            WHERE j.dosen_nip = auth_nip()
        )
    );

CREATE POLICY peng_select_self ON pengajuan_ketidakhadiran
    FOR SELECT USING (
        auth_role() = 'mahasiswa'
        AND kehadiran_id IN (
            SELECT id FROM kehadiran WHERE nim = auth_nim()
        )
    );

CREATE POLICY peng_insert_self ON pengajuan_ketidakhadiran
    FOR INSERT WITH CHECK (
        auth_role() = 'mahasiswa'
        AND kehadiran_id IN (
            SELECT id FROM kehadiran WHERE nim = auth_nim()
        )
    );

CREATE POLICY peng_update_dosen ON pengajuan_ketidakhadiran
    FOR UPDATE USING (
        auth_role() = 'dosen'
        AND kehadiran_id IN (
            SELECT k.id FROM kehadiran k
            JOIN sesi_presensi sp ON sp.id = k.sesi_presensi_id
            JOIN jadwal_kuliah j  ON j.id  = sp.jadwal_id
            WHERE j.dosen_nip = auth_nip()
        )
    );

CREATE POLICY peng_modify_admin ON pengajuan_ketidakhadiran
    FOR ALL USING (auth_role() = 'admin');

-- ─────────────────────────────────────────────────────────────
-- 14. ADMIN — hanya admin yang bisa akses tabel admin
-- ─────────────────────────────────────────────────────────────
CREATE POLICY admin_self ON admin
    FOR ALL USING (auth_role() = 'admin');
