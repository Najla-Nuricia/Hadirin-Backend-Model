-- Hapus tabel backup path foto lama setelah migrasi pgvector terverifikasi.
-- Isi tabel sudah di-backup ke /tmp/opencode/hadirin_legacy_photo_paths_before_drop.json
-- sebelum dijalankan. Tidak ada kode runtime yang membaca tabel ini.
DROP TABLE IF EXISTS hadirin_legacy_photo_paths;
