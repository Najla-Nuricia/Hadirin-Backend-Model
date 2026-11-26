-- Sesi presensi persisten: satu sesi per jadwal, tanpa is_open/QR dinamis.
-- Tanggal absen dipindah ke kehadiran agar check-in per jadwal per hari unik.
-- QR pintu tetap statis (HADIRIN:ROOM:<kode>) dan tidak tersimpan di DB.
-- Backup penuh: /tmp/opencode/sesi_presensi_before_rework.json

BEGIN;

-- 1. Tanggal kehadiran
ALTER TABLE public.kehadiran ADD COLUMN IF NOT EXISTS tanggal DATE;
UPDATE public.kehadiran k
SET tanggal = sp.tanggal
FROM public.sesi_presensi sp
WHERE sp.id = k.sesi_presensi_id AND k.tanggal IS NULL;
UPDATE public.kehadiran SET tanggal = created_at::date WHERE tanggal IS NULL;
ALTER TABLE public.kehadiran ALTER COLUMN tanggal SET NOT NULL;
ALTER TABLE public.kehadiran DROP CONSTRAINT IF EXISTS kehadiran_sesi_presensi_id_nim_key;

-- 2. Pindahkan semua kehadiran ke sesi terlama milik jadwal yang sama
WITH ranked AS (
    SELECT id,
           jadwal_id,
           row_number() OVER (PARTITION BY jadwal_id ORDER BY created_at, id) AS rn
    FROM public.sesi_presensi
), keeper AS (
    SELECT id, jadwal_id FROM ranked WHERE rn = 1
)
UPDATE public.kehadiran k
SET sesi_presensi_id = keeper.id
FROM keeper, public.sesi_presensi sp
WHERE sp.id = k.sesi_presensi_id
  AND keeper.jadwal_id = sp.jadwal_id
  AND k.sesi_presensi_id <> keeper.id;

-- 3. Buang duplikat kehadiran (jadwal, nim, tanggal), pindahkan pengajuan ke baris terlama
WITH ranked AS (
    SELECT k.id,
           sp.jadwal_id,
           k.nim,
           k.tanggal,
           row_number() OVER (
               PARTITION BY sp.jadwal_id, k.nim, k.tanggal
               ORDER BY k.created_at, k.id
           ) AS rn
    FROM public.kehadiran k
    JOIN public.sesi_presensi sp ON sp.id = k.sesi_presensi_id
), duplicate AS (
    SELECT id, jadwal_id, nim, tanggal FROM ranked WHERE rn > 1
), keep_row AS (
    SELECT id, jadwal_id, nim, tanggal FROM ranked WHERE rn = 1
)
UPDATE public.pengajuan_ketidakhadiran p
SET kehadiran_id = keep.id
FROM duplicate d
JOIN keep_row keep
  ON keep.jadwal_id = d.jadwal_id
 AND keep.nim = d.nim
 AND keep.tanggal = d.tanggal
WHERE p.kehadiran_id = d.id
  AND NOT EXISTS (
      SELECT 1 FROM public.pengajuan_ketidakhadiran p2
      WHERE p2.kehadiran_id = keep.id
  );

DELETE FROM public.pengajuan_ketidakhadiran
WHERE kehadiran_id IN (
    WITH ranked AS (
        SELECT k.id,
               sp.jadwal_id,
               k.nim,
               k.tanggal,
               row_number() OVER (
                   PARTITION BY sp.jadwal_id, k.nim, k.tanggal
                   ORDER BY k.created_at, k.id
               ) AS rn
        FROM public.kehadiran k
        JOIN public.sesi_presensi sp ON sp.id = k.sesi_presensi_id
    )
    SELECT id FROM ranked WHERE rn > 1
);

DELETE FROM public.kehadiran
WHERE id IN (
    WITH ranked AS (
        SELECT k.id,
               sp.jadwal_id,
               k.nim,
               k.tanggal,
               row_number() OVER (
                   PARTITION BY sp.jadwal_id, k.nim, k.tanggal
                   ORDER BY k.created_at, k.id
               ) AS rn
        FROM public.kehadiran k
        JOIN public.sesi_presensi sp ON sp.id = k.sesi_presensi_id
    )
    SELECT id FROM ranked WHERE rn > 1
);

ALTER TABLE public.kehadiran
ADD CONSTRAINT kehadiran_sesi_nim_tanggal_key UNIQUE (sesi_presensi_id, nim, tanggal);
CREATE INDEX IF NOT EXISTS idx_kehadiran_sesi_tanggal
ON public.kehadiran (sesi_presensi_id, tanggal);

-- 4. Hapus policy yang bergantung pada kolom yang dihapus
DROP POLICY IF EXISTS sp_update_dosen ON public.sesi_presensi;
DROP POLICY IF EXISTS sp_insert_dosen ON public.sesi_presensi;

-- 5. Hapus sesi duplikat (kehadiran sudah dipindah ke sesi terlama)
DELETE FROM public.sesi_presensi sp
USING (
    SELECT id,
           row_number() OVER (PARTITION BY jadwal_id ORDER BY created_at, id) AS rn
    FROM public.sesi_presensi
) r
WHERE sp.id = r.id AND r.rn > 1;

-- 6. Skema sesi: tanpa tanggal, QR, dan is_open
-- View lama bergantung pada sesi_presensi.tanggal; dibuat ulang di bagian 8.
DROP VIEW IF EXISTS public.v_rekap_kehadiran;
ALTER TABLE public.sesi_presensi
DROP CONSTRAINT IF EXISTS sesi_presensi_jadwal_id_tanggal_key;
ALTER TABLE public.sesi_presensi
DROP COLUMN IF EXISTS tanggal,
DROP COLUMN IF EXISTS qr_token,
DROP COLUMN IF EXISTS qr_expires_at,
DROP COLUMN IF EXISTS is_open,
DROP COLUMN IF EXISTS dibuka_oleh;
ALTER TABLE public.sesi_presensi
ADD CONSTRAINT sesi_presensi_jadwal_id_key UNIQUE (jadwal_id);

-- 7. Sesi otomatis untuk setiap jadwal baru + backfill existing
CREATE OR REPLACE FUNCTION public.auto_create_sesi_presensi()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    INSERT INTO public.sesi_presensi (jadwal_id)
    VALUES (NEW.id)
    ON CONFLICT (jadwal_id) DO NOTHING;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.auto_create_sesi_presensi() FROM PUBLIC;

DROP TRIGGER IF EXISTS trg_auto_create_sesi_presensi ON public.jadwal_kuliah;
CREATE TRIGGER trg_auto_create_sesi_presensi
AFTER INSERT ON public.jadwal_kuliah
FOR EACH ROW EXECUTE FUNCTION public.auto_create_sesi_presensi();

INSERT INTO public.sesi_presensi (jadwal_id)
SELECT j.id
FROM public.jadwal_kuliah j
LEFT JOIN public.sesi_presensi s ON s.jadwal_id = j.id
WHERE s.id IS NULL
ON CONFLICT (jadwal_id) DO NOTHING;

-- 8. View rekap memakai tanggal kehadiran
CREATE OR REPLACE VIEW public.v_rekap_kehadiran WITH (security_invoker = true) AS
SELECT
    k.id                        AS kehadiran_id,
    k.tanggal,
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

COMMIT;
