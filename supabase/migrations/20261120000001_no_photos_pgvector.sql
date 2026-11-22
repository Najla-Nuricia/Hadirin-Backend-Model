-- ============================================================
-- HADIRIN — 2026-11-20
-- 1) Stop storing raw face photos (keep only embedding rows).
-- 2) Migrate foto_wajah.embedding JSONB -> vector(512) (pgvector).
-- Aman dijalankan berulang kali (idempotent) via Supabase SQL Editor
-- atau `supabase db push`. Re-run tidak menghapus data embedding.
-- ============================================================

SET search_path = public, extensions;

CREATE EXTENSION IF NOT EXISTS vector;

-- ── Backup metadata path foto lama sebelum kolom dihapus ──────
-- Hanya berisi path/teks, bukan byte gambar. Boleh dihapus setelah
-- verifikasi migrasi; sengaja tidak diberi policy RLS (deny by default).
CREATE TABLE IF NOT EXISTS hadirin_legacy_photo_paths (
    source_table TEXT         NOT NULL,
    ref_id       TEXT         NOT NULL,
    nim          VARCHAR(20)  NOT NULL,
    storage_path TEXT         NOT NULL,
    migrated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

ALTER TABLE hadirin_legacy_photo_paths ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'foto_wajah'
          AND column_name = 'storage_path'
    ) THEN
        INSERT INTO hadirin_legacy_photo_paths (source_table, ref_id, nim, storage_path)
        SELECT 'foto_wajah', id::text, nim, storage_path
        FROM foto_wajah
        WHERE storage_path IS NOT NULL;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'kehadiran'
          AND column_name = 'face_photo_path'
    ) THEN
        INSERT INTO hadirin_legacy_photo_paths (source_table, ref_id, nim, storage_path)
        SELECT 'kehadiran', id::text, nim, face_photo_path
        FROM kehadiran
        WHERE face_photo_path IS NOT NULL;
    END IF;
END $$;

-- ── JSONB -> vector(512) ──────────────────────────────────────
-- Baris dengan array bukan 512 dimensi atau NULL sengaja dibuat NULL
-- supaya migrasi tidak gagal; baris valid dipertahankan apa adanya.
-- Text perantara dipakai agar tidak ada subquery di dalam USING.
DO $$
DECLARE
    v_type TEXT;
BEGIN
    SELECT data_type INTO v_type
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'foto_wajah'
      AND column_name = 'embedding';

    IF v_type IS NULL THEN
        ALTER TABLE foto_wajah ADD COLUMN embedding vector(512);
    ELSIF v_type = 'jsonb' THEN
        ALTER TABLE foto_wajah ADD COLUMN IF NOT EXISTS _embedding_migration_text TEXT;

        UPDATE foto_wajah
        SET _embedding_migration_text = CASE
            WHEN embedding IS NOT NULL
                 AND jsonb_typeof(embedding) = 'array'
                 AND jsonb_array_length(embedding) = 512
            THEN (
                SELECT '[' || string_agg(v, ',' ORDER BY ord) || ']'
                FROM jsonb_array_elements_text(embedding) WITH ORDINALITY AS t(v, ord)
            )
            ELSE NULL
        END;

        ALTER TABLE foto_wajah
            ALTER COLUMN embedding TYPE vector(512)
            USING _embedding_migration_text::vector(512);

        ALTER TABLE foto_wajah DROP COLUMN _embedding_migration_text;
    END IF;
    -- v_type = 'USER-DEFINED' (vector) => sudah termigrasi, tidak diubah.
END $$;

-- ── Hapus referensi foto mentah ───────────────────────────────
ALTER TABLE foto_wajah DROP COLUMN IF EXISTS storage_path;
ALTER TABLE kehadiran  DROP COLUMN IF EXISTS face_photo_path;

-- ── Verifikasi ringkas (bisa dijalankan ulang) ────────────────
DO $$
DECLARE
    v_type TEXT;
BEGIN
    SELECT data_type INTO v_type
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'foto_wajah'
      AND column_name = 'embedding';

    IF v_type IS DISTINCT FROM 'USER-DEFINED' THEN
        RAISE EXCEPTION 'Migrasi gagal: tipe foto_wajah.embedding = %, expected vector', v_type;
    END IF;
END $$;
