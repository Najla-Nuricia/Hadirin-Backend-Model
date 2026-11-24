-- ============================================================
-- HADIRIN — Whitelist NIM mahasiswa
-- ============================================================

CREATE TABLE whitelist_nim (
    nim         VARCHAR(20) PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Mahasiswa yang sudah ada harus tetap dapat login dan tidak boleh
-- kehilangan akses ketika aturan whitelist mulai diberlakukan.
INSERT INTO whitelist_nim (nim)
SELECT nim FROM mahasiswa
ON CONFLICT (nim) DO NOTHING;

ALTER TABLE mahasiswa
    ADD CONSTRAINT mahasiswa_nim_whitelist_fkey
    FOREIGN KEY (nim) REFERENCES whitelist_nim(nim) ON DELETE RESTRICT;

CREATE INDEX idx_whitelist_nim_nim ON whitelist_nim (nim);

CREATE TRIGGER set_whitelist_nim_updated_at
    BEFORE UPDATE ON whitelist_nim
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

ALTER TABLE whitelist_nim ENABLE ROW LEVEL SECURITY;

CREATE POLICY whitelist_nim_select_admin ON whitelist_nim
    FOR SELECT USING (auth_role() = 'admin');

CREATE POLICY whitelist_nim_modify_admin ON whitelist_nim
    FOR ALL USING (auth_role() = 'admin')
    WITH CHECK (auth_role() = 'admin');
