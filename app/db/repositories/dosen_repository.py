"""Repository for lecturer records, teaching schedules, sessions, and class attendance."""

from typing import Any

from app.db.repositories.base import BaseRepository

JADWAL_DOSEN_COLUMNS = (
    "id, hari, semester, kelas_id, dosen_nip, sesi_mulai, sesi_selesai, "
    "kelas(id, nama, program_studi_kode), "
    "mata_kuliah(kode, nama, sks), "
    "ruangan(kode, nama)"
)

SESI_PRESENSI_COLUMNS = (
    "id, jadwal_id, tanggal, qr_token, qr_expires_at, is_open, "
    "jadwal_kuliah(dosen_nip, kelas_id, kelas(nama), mata_kuliah(nama))"
)

DOSEN_COLUMNS = "nip, nama, email, no_hp, auth_user_id"


class DosenRepository(BaseRepository):
    """Supabase queries for `dosen`, `jadwal_kuliah`, `sesi_presensi`, and class rosters."""

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Fetch lecturer profile by lowercase email."""
        res = (
            self.client.table("dosen")
            .select(DOSEN_COLUMNS)
            .eq("email", email.strip().lower())
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def get_by_nip(self, nip: str) -> dict[str, Any] | None:
        """Fetch lecturer profile by NIP."""
        res = (
            self.client.table("dosen")
            .select(DOSEN_COLUMNS)
            .eq("nip", nip.strip())
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def list_active_jadwal(self, dosen_nip: str) -> list[dict[str, Any]]:
        """List active-academic-year course schedules taught by the lecturer."""
        res = (
            self.client.table("jadwal_kuliah")
            .select(f"{JADWAL_DOSEN_COLUMNS}, tahun_ajaran!inner(status)")
            .eq("dosen_nip", dosen_nip)
            .eq("tahun_ajaran.status", "aktif")
            .execute()
        )
        rows = res.data or []
        return self._attach_slot_times(rows)

    def get_jadwal_by_id(self, jadwal_id: str) -> dict[str, Any] | None:
        """Fetch a single `jadwal_kuliah` row joined with class/course/time metadata."""
        res = (
            self.client.table("jadwal_kuliah")
            .select(JADWAL_DOSEN_COLUMNS)
            .eq("id", jadwal_id)
            .limit(1)
            .execute()
        )
        row = self.first_or_none(res.data)
        if not row:
            return None
        return self._attach_slot_times([row])[0]

    def _attach_slot_times(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Attach `jam_mulai` and `jam_selesai` from `v_jadwal_lengkap`."""
        jadwal_ids = [str(r["id"]) for r in rows if r.get("id")]
        if not jadwal_ids:
            return rows
        times = self.fetch_rows_in(
            client=self.client,
            table="v_jadwal_lengkap",
            columns="id, jam_mulai, jam_selesai",
            filter_column="id",
            values=jadwal_ids,
            order_by="id",
            page_size=self.settings.supabase_page_size,
        )
        time_map = {str(item["id"]): item for item in times}
        for row in rows:
            slot = time_map.get(str(row["id"])) or {}
            row["jam_mulai"] = slot.get("jam_mulai")
            row["jam_selesai"] = slot.get("jam_selesai")
        return rows

    def get_sesi_with_jadwal(self, sesi_id: str) -> dict[str, Any] | None:
        """Fetch a `sesi_presensi` row joined with lecturer ownership metadata."""
        res = (
            self.client.table("sesi_presensi")
            .select(SESI_PRESENSI_COLUMNS)
            .eq("id", sesi_id)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def get_latest_sesi_for_jadwal(
        self,
        jadwal_id: str,
        tanggal_iso: str | None = None,
    ) -> dict[str, Any] | None:
        """Return latest attendance session for a schedule, optionally pinned to a date."""
        query = (
            self.client.table("sesi_presensi")
            .select("id, tanggal, is_open")
            .eq("jadwal_id", jadwal_id)
        )
        if tanggal_iso is not None:
            query = query.eq("tanggal", tanggal_iso)
        res = query.order("tanggal", desc=True).limit(1).execute()
        return self.first_or_none(res.data)

    def list_students_by_kelas_ids(
        self,
        kelas_ids: list[str],
        columns: str = "nim, kelas_id",
    ) -> list[dict[str, Any]]:
        """Paginated fetch of students enrolled in any of `kelas_ids`."""
        return self.fetch_rows_in(
            client=self.client,
            table="mahasiswa",
            columns=columns,
            filter_column="kelas_id",
            values=kelas_ids,
            order_by="nim",
            page_size=self.settings.supabase_page_size,
        )

    def list_sesi_by_jadwal_ids(self, jadwal_ids: list[str]) -> list[dict[str, Any]]:
        """Paginated fetch of `sesi_presensi` rows for lecturer schedules."""
        return self.fetch_rows_in(
            client=self.client,
            table="sesi_presensi",
            columns="id, jadwal_id, tanggal, is_open",
            filter_column="jadwal_id",
            values=jadwal_ids,
            order_by="id",
            page_size=self.settings.supabase_page_size,
        )

    def list_rekap_by_jadwal_ids(self, jadwal_ids: list[str]) -> list[dict[str, Any]]:
        """Paginated fetch of `v_rekap_kehadiran` rows for lecturer schedules."""
        return self.fetch_rows_in(
            client=self.client,
            table="v_rekap_kehadiran",
            columns="kehadiran_id, sesi_presensi_id, nim, status",
            filter_column="jadwal_id",
            values=jadwal_ids,
            order_by="kehadiran_id",
            page_size=self.settings.supabase_page_size,
        )

    def list_kehadiran_for_sesi(self, sesi_id: str) -> list[dict[str, Any]]:
        """Paginated fetch of `kehadiran` + `pengajuan_ketidakhadiran` rows for a session."""
        return self.fetch_rows_in(
            client=self.client,
            table="kehadiran",
            columns=(
                "nim, status, jam_masuk, catatan, "
                "pengajuan_ketidakhadiran(alasan, dokumen_path, status_pengajuan)"
            ),
            filter_column="sesi_presensi_id",
            values=[sesi_id],
            order_by="nim",
            page_size=self.settings.supabase_page_size,
        )

    def upsert_open_sesi(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Open or refresh today's `sesi_presensi` row via `(jadwal_id, tanggal)` upsert."""
        res = (
            self.client.table("sesi_presensi")
            .upsert(payload, on_conflict="jadwal_id,tanggal")
            .execute()
        )
        return self.first_or_none(res.data)

    def update_sesi_qr(self, sesi_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Rotate QR fields on a currently open session."""
        res = (
            self.client.table("sesi_presensi")
            .update(fields)
            .eq("id", sesi_id)
            .eq("is_open", True)
            .execute()
        )
        return self.first_or_none(res.data)

    def close_sesi(self, sesi_id: str) -> dict[str, Any] | None:
        """Close an attendance session and clear its active QR token."""
        res = (
            self.client.table("sesi_presensi")
            .update({"is_open": False, "qr_token": None, "qr_expires_at": None})
            .eq("id", sesi_id)
            .execute()
        )
        return self.first_or_none(res.data)
