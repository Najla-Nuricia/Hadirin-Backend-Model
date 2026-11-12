"""Repository for `sesi_presensi`, `kehadiran`, `v_rekap_kehadiran`, and attendance photos."""

from typing import Any

from app.core.exceptions import ExternalServiceError
from app.db.repositories.base import BaseRepository


class KehadiranRepository(BaseRepository):
    """Database and Storage operations for attendance sessions and student records."""

    def list_rekap_by_nim(
        self,
        nim: str,
        status_filter: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return student's attendance history rows from `v_rekap_kehadiran`."""
        query = self.client.table("v_rekap_kehadiran").select("*").eq("nim", nim)
        if status_filter:
            query = query.eq("status", status_filter.strip().lower())
        query = query.order("tanggal", desc=True).order("sesi_presensi_id", desc=True)
        if limit is not None:
            query = query.limit(limit)
        res = query.execute()
        return res.data or []

    def get_rekap_by_kehadiran_id(self, kehadiran_id: str) -> dict[str, Any] | None:
        """Fetch a single attendance detail row from `v_rekap_kehadiran`."""
        res = (
            self.client.table("v_rekap_kehadiran")
            .select("*")
            .eq("kehadiran_id", kehadiran_id)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def list_kehadiran_by_nim(self, nim: str) -> list[dict[str, Any]]:
        """Fetch raw `kehadiran` rows for a student including `face_photo_path`."""
        res = (
            self.client.table("kehadiran")
            .select("*")
            .eq("nim", nim)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []

    def get_sesi_by_id(self, sesi_id: str) -> dict[str, Any] | None:
        """Fetch an attendance session by UUID."""
        res = self.client.table("sesi_presensi").select("*").eq("id", sesi_id).limit(1).execute()
        return self.first_or_none(res.data)

    def get_sesi_by_qr_token(self, qr_token: str) -> dict[str, Any] | None:
        """Fetch an attendance session matching an active QR token."""
        res = (
            self.client.table("sesi_presensi")
            .select("*")
            .eq("qr_token", qr_token.strip())
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def get_sesi_by_jadwal_and_date(self, jadwal_id: str, tanggal_iso: str) -> dict[str, Any] | None:
        """Fetch an attendance session for a schedule on a specific date."""
        res = (
            self.client.table("sesi_presensi")
            .select("*")
            .eq("jadwal_id", jadwal_id)
            .eq("tanggal", tanggal_iso)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def list_open_sesi_by_jadwal_ids(
        self,
        jadwal_ids: list[str],
        tanggal_iso: str | None = None,
    ) -> list[dict[str, Any]]:
        """List currently open attendance sessions belonging to a student's schedules."""
        if not jadwal_ids:
            return []
        query = (
            self.client.table("sesi_presensi")
            .select("*")
            .in_("jadwal_id", jadwal_ids)
            .eq("is_open", True)
        )
        if tanggal_iso:
            query = query.eq("tanggal", tanggal_iso)
        res = query.order("created_at", desc=True).execute()
        return res.data or []

    def create_sesi_presensi(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert a new attendance session row."""
        try:
            res = self.client.table("sesi_presensi").insert(payload).execute()
            row = self.first_or_none(res.data)
            if not row:
                raise ExternalServiceError("Gagal membuat sesi presensi.")
            return row
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError(f"Gagal menyimpan sesi presensi: {exc}") from exc

    def get_or_create_sesi_presensi(
        self,
        jadwal_id: str,
        tanggal_iso: str,
        defaults: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return existing `(jadwal_id, tanggal)` session or create a new one."""
        existing = self.get_sesi_by_jadwal_and_date(jadwal_id, tanggal_iso)
        if existing:
            return existing
        payload = {"jadwal_id": jadwal_id, "tanggal": tanggal_iso, "is_open": False}
        if defaults:
            payload.update(defaults)
        return self.create_sesi_presensi(payload)

    def delete_sesi_presensi(self, sesi_id: str) -> bool:
        """Delete an attendance session by UUID."""
        res = self.client.table("sesi_presensi").delete().eq("id", sesi_id).execute()
        return bool(res.data)

    def get_kehadiran_by_sesi_and_nim(self, sesi_presensi_id: str, nim: str) -> dict[str, Any] | None:
        """Fetch an attendance row for a `(sesi_presensi_id, nim)` pair."""
        res = (
            self.client.table("kehadiran")
            .select("*")
            .eq("sesi_presensi_id", sesi_presensi_id)
            .eq("nim", nim)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def upsert_kehadiran(
        self,
        sesi_presensi_id: str,
        nim: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Insert or update a student's attendance record for a session."""
        existing = self.get_kehadiran_by_sesi_and_nim(sesi_presensi_id, nim)
        if existing:
            res = (
                self.client.table("kehadiran")
                .update(fields)
                .eq("id", existing["id"])
                .execute()
            )
            return self.first_or_none(res.data) or {**existing, **fields}

        payload = {"sesi_presensi_id": sesi_presensi_id, "nim": nim, **fields}
        res = self.client.table("kehadiran").insert(payload).execute()
        row = self.first_or_none(res.data)
        if not row:
            raise ExternalServiceError("Gagal menyimpan data kehadiran.")
        return row

    def delete_kehadiran_by_id(self, kehadiran_id: str) -> bool:
        """Delete an attendance row by UUID."""
        res = self.client.table("kehadiran").delete().eq("id", kehadiran_id).execute()
        return bool(res.data)

    def upload_attendance_photo(
        self,
        storage_path: str,
        content: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        """Upload face verification snapshot to the attendance bucket."""
        return self.upload_to_bucket(
            bucket=self.settings.storage_bucket_presensi,
            storage_path=storage_path,
            content=content,
            content_type=content_type,
        )

    def delete_attendance_photo(self, storage_path: str | None) -> None:
        """Delete an attendance snapshot from Storage if present."""
        if storage_path:
            self.delete_from_bucket(self.settings.storage_bucket_presensi, [storage_path])

