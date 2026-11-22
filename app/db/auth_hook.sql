-- ============================================================
-- HADIRIN — Auth Hook: Custom JWT Claims
-- Jalankan SETELAH schema.sql dan seed.sql
-- 
-- Fungsi ini dipanggil Supabase Auth setiap kali user login.
-- Ia menambahkan custom claims (role, nim/nip) ke JWT token
-- sehingga RLS policies bisa mengenali siapa user tersebut.
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- FUNCTION: custom_access_token_hook
-- Dipanggil oleh Supabase Auth (Auth Hook) saat token dibuat.
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event JSONB)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    claims        JSONB;
    user_id       UUID;
    v_role        TEXT;
    v_nim         TEXT;
    v_nip         TEXT;
BEGIN
    -- Ambil user_id dari event
    user_id := (event ->> 'user_id')::UUID;
    claims  := event -> 'claims';

    -- ── Cek apakah user adalah ADMIN ──────────────────────────
    SELECT 'admin' INTO v_role
    FROM public.admin
    WHERE auth_user_id = user_id
    LIMIT 1;

    IF v_role IS NOT NULL THEN
        claims := jsonb_set(claims, '{role}', '"admin"');
        RETURN jsonb_set(event, '{claims}', claims);
    END IF;

    -- ── Cek apakah user adalah DOSEN ──────────────────────────
    SELECT 'dosen', nip INTO v_role, v_nip
    FROM public.dosen
    WHERE auth_user_id = user_id
    LIMIT 1;

    IF v_role IS NOT NULL THEN
        claims := jsonb_set(claims, '{role}', '"dosen"');
        claims := jsonb_set(claims, '{nip}',  to_jsonb(v_nip));
        RETURN jsonb_set(event, '{claims}', claims);
    END IF;

    -- ── Cek apakah user adalah MAHASISWA ──────────────────────
    SELECT 'mahasiswa', nim INTO v_role, v_nim
    FROM public.mahasiswa
    WHERE auth_user_id = user_id
    LIMIT 1;

    IF v_role IS NOT NULL THEN
        claims := jsonb_set(claims, '{role}', '"mahasiswa"');
        claims := jsonb_set(claims, '{nim}',  to_jsonb(v_nim));
        RETURN jsonb_set(event, '{claims}', claims);
    END IF;

    -- ── Tidak ditemukan di tabel manapun (user belum terdaftar)
    claims := jsonb_set(claims, '{role}', '"anonymous"');
    RETURN jsonb_set(event, '{claims}', claims);
END;
$$;

-- ─────────────────────────────────────────────────────────────
-- GRANT: izinkan Supabase Auth memanggil fungsi ini
-- ─────────────────────────────────────────────────────────────
GRANT EXECUTE ON FUNCTION public.custom_access_token_hook TO supabase_auth_admin;
REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook FROM PUBLIC, anon, authenticated;

-- ─────────────────────────────────────────────────────────────
-- CARA AKTIVASI DI SUPABASE DASHBOARD:
--
-- 1. Buka: Authentication → Hooks
-- 2. Klik "Add hook" → pilih "Custom Access Token"
-- 3. Pilih schema: public
-- 4. Pilih function: custom_access_token_hook
-- 5. Save
--
-- Setelah aktif, setiap JWT login akan otomatis memiliki:
--   { "role": "mahasiswa", "nim": "2211001" }
--   { "role": "dosen",     "nip": "198501012010121001" }
--   { "role": "admin" }
-- ─────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────
-- FUNCTION: link_auth_user
-- Dipanggil saat user baru mendaftar via Supabase Auth,
-- untuk menghubungkan auth.users.id ke tabel mahasiswa/dosen/admin.
--
-- Gunakan di backend (FastAPI) setelah supabase.auth.sign_up()
-- dengan memanggil RPC ini.
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.link_auth_user(
    p_auth_user_id UUID,
    p_peran        TEXT,     -- 'admin' | 'dosen' | 'mahasiswa'
    p_identifier   TEXT      -- NIM untuk mahasiswa, NIP untuk dosen, email untuk admin
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_result JSONB;
BEGIN
    CASE p_peran
        WHEN 'mahasiswa' THEN
            UPDATE public.mahasiswa
            SET auth_user_id = p_auth_user_id
            WHERE nim = p_identifier
              AND auth_user_id IS NULL;

            IF NOT FOUND THEN
                RETURN jsonb_build_object(
                    'success', FALSE,
                    'message', 'NIM tidak ditemukan atau sudah terhubung ke akun lain'
                );
            END IF;

        WHEN 'dosen' THEN
            UPDATE public.dosen
            SET auth_user_id = p_auth_user_id
            WHERE nip = p_identifier
              AND auth_user_id IS NULL;

            IF NOT FOUND THEN
                RETURN jsonb_build_object(
                    'success', FALSE,
                    'message', 'NIP tidak ditemukan atau sudah terhubung ke akun lain'
                );
            END IF;

        WHEN 'admin' THEN
            UPDATE public.admin
            SET auth_user_id = p_auth_user_id
            WHERE email = p_identifier
              AND auth_user_id IS NULL;

            IF NOT FOUND THEN
                RETURN jsonb_build_object(
                    'success', FALSE,
                    'message', 'Email admin tidak ditemukan atau sudah terhubung'
                );
            END IF;

        ELSE
            RETURN jsonb_build_object(
                'success', FALSE,
                'message', 'Peran tidak valid. Gunakan: mahasiswa, dosen, atau admin'
            );
    END CASE;

    RETURN jsonb_build_object('success', TRUE, 'message', 'Akun berhasil dihubungkan');
END;
$$;

GRANT EXECUTE ON FUNCTION public.link_auth_user TO authenticated, service_role;
