"""Repository for `pengajuan_ketidakhadiran` and Storage bucket `dokumen-pengajuan`."""

from typing import Any

from app.core.exceptions import ConflictError, ExternalServiceError
from app.db.repositories.base import BaseRepository

_PENGAJUAN_SELECT = (
    "*, kehadiran!inner(id, nim, status, sesi_presensi_id, "
    "sesi_presensi(id, tanggal, jadwal_id))"
)


class PengajuanRepository(BaseRepository):
    """CRUD and document storage operations for absence permission requests."""

    def list_by_nim(self, nim: str) -> list[dict[str, Any]]:
        """List all absence requests submitted by a student ordered newest first."""
        res = (
            self.client.table("pengajuan_ketidakhadiran")
            .select(_PENGAJUAN_SELECT)
            .eq("kehadiran.nim", nim)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []

    def get_by_id(self, pengajuan_id: str) -> dict[str, Any] | None:
        """Fetch a single absence request joined with attendance and session context."""
        res = (
            self.client.table("pengajuan_ketidakhadiran")
            .select(_PENGAJUAN_SELECT)
            .eq("id", pengajuan_id)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def get_by_kehadiran_id(self, kehadiran_id: str) -> dict[str, Any] | None:
        """Check whether an absence request already exists for a `kehadiran_id`."""
        res = (
            self.client.table("pengajuan_ketidakhadiran")
            .select(_PENGAJUAN_SELECT)
            .eq("kehadiran_id", kehadiran_id)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert a new absence request row and return the enriched record."""
        try:
            res = self.client.table("pengajuan_ketidakhadiran").insert(payload).execute()
        except Exception as exc:
            msg = str(exc).lower()
            if "duplicate" in msg or "23505" in msg or "unique" in msg:
                raise ConflictError("Pengajuan untuk sesi perkuliahan tersebut sudah ada.") from exc
            raise ExternalServiceError(f"Gagal menyimpan pengajuan surat izin: {exc}") from exc

        row = self.first_or_none(res.data)
        if not row:
            raise ExternalServiceError("Data pengajuan gagal dimuat setelah dibuat.")
        return self.get_by_id(row["id"]) or row

    def update_by_id(self, pengajuan_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Update fields on an existing absence request."""
        if fields:
            self.client.table("pengajuan_ketidakhadiran").update(fields).eq("id", pengajuan_id).execute()
        return self.get_by_id(pengajuan_id)

    def delete_by_id(self, pengajuan_id: str) -> bool:
        """Delete an absence request row by UUID."""
        res = self.client.table("pengajuan_ketidakhadiran").delete().eq("id", pengajuan_id).execute()
        return bool(res.data)

    def upload_document(
        self,
        storage_path: str,
        content: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload a supporting absence document to `dokumen-pengajuan` bucket."""
        return self.upload_to_bucket(
            bucket=self.settings.storage_bucket_pengajuan,
            storage_path=storage_path,
            content=content,
            content_type=content_type,
        )

    def get_document_signed_url(self, storage_path: str | None) -> str | None:
        """Return a signed URL for an uploaded absence document."""
        if not storage_path or "/" not in storage_path:
            return None
        return self.create_signed_url(self.settings.storage_bucket_pengajuan, storage_path)

    def delete_document(self, storage_path: str | None) -> None:
        """Delete a stored document if `storage_path` is a bucket object key."""
        if storage_path and "/" in storage_path:
            try:
                self.delete_from_bucket(self.settings.storage_bucket_pengajuan, [storage_path])
            except ExternalServiceError:
                pass

