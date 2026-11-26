"""Repository for `sesi_presensi`, `kehadiran`, and `v_rekap_kehadiran`."""

from typing import Any

from app.core.exceptions import ExternalServiceError
from app.db.repositories.base import BaseRepository


class KehadiranRepository(BaseRepository):
    """Database operations for attendance sessions and student records."""

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
        """Fetch raw `kehadiran` rows for a student."""
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

    def get_sesi_by_jadwal_id(self, jadwal_id: str) -> dict[str, Any] | None:
        """Fetch the single persistent session belonging to a schedule."""
        res = (
            self.client.table("sesi_presensi")
            .select("*")
            .eq("jadwal_id", jadwal_id)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def list_sesi_by_jadwal_ids(self, jadwal_ids: list[str]) -> list[dict[str, Any]]:
        """List persistent sessions for the given schedules."""
        if not jadwal_ids:
            return []
        res = (
            self.client.table("sesi_presensi")
            .select("*")
            .in_("jadwal_id", jadwal_ids)
            .execute()
        )
        return res.data or []

    def delete_sesi_presensi(self, sesi_id: str) -> bool:
        """Delete an attendance session by UUID."""
        res = self.client.table("sesi_presensi").delete().eq("id", sesi_id).execute()
        return bool(res.data)

    def get_kehadiran_by_sesi_nim_tanggal(
        self,
        sesi_presensi_id: str,
        nim: str,
        tanggal_iso: str,
    ) -> dict[str, Any] | None:
        """Fetch an attendance row for `(sesi, nim, tanggal)`."""
        res = (
            self.client.table("kehadiran")
            .select("*")
            .eq("sesi_presensi_id", sesi_presensi_id)
            .eq("nim", nim)
            .eq("tanggal", tanggal_iso)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def list_kehadiran_for_sesi(
        self,
        sesi_presensi_id: str,
        tanggal_iso: str | None = None,
    ) -> list[dict[str, Any]]:
        """List attendance rows for a persistent session, optionally on one date."""
        query = (
            self.client.table("kehadiran")
            .select("*")
            .eq("sesi_presensi_id", sesi_presensi_id)
        )
        if tanggal_iso:
            query = query.eq("tanggal", tanggal_iso)
        res = query.execute()
        return res.data or []

    def upsert_kehadiran(
        self,
        sesi_presensi_id: str,
        nim: str,
        tanggal_iso: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Insert or update attendance for `(sesi, nim, tanggal)`."""
        existing = self.get_kehadiran_by_sesi_nim_tanggal(sesi_presensi_id, nim, tanggal_iso)
        if existing:
            res = (
                self.client.table("kehadiran")
                .update(fields)
                .eq("id", existing["id"])
                .execute()
            )
            return self.first_or_none(res.data) or {**existing, **fields}

        payload = {
            "sesi_presensi_id": sesi_presensi_id,
            "nim": nim,
            "tanggal": tanggal_iso,
            **fields,
        }
        res = self.client.table("kehadiran").insert(payload).execute()
        row = self.first_or_none(res.data)
        if not row:
            raise ExternalServiceError("Gagal menyimpan data kehadiran.")
        return row

    def delete_kehadiran_by_id(self, kehadiran_id: str) -> bool:
        """Delete an attendance row by UUID."""
        res = self.client.table("kehadiran").delete().eq("id", kehadiran_id).execute()
        return bool(res.data)

