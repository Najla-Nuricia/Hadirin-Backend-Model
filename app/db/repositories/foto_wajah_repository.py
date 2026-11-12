"""Repository for `foto_wajah` table and Storage bucket `foto-wajah`."""

from typing import Any

from app.core.exceptions import ExternalServiceError
from app.db.repositories.base import BaseRepository


class FotoWajahRepository(BaseRepository):
    """Database and Storage operations for student face embeddings and samples."""

    def list_by_nim(self, nim: str, active_only: bool = True) -> list[dict[str, Any]]:
        """Fetch stored face records (`storage_path`, `embedding`) for a student."""
        query = self.client.table("foto_wajah").select("*").eq("nim", nim)
        if active_only:
            query = query.eq("is_active", True)
        res = query.order("created_at", desc=False).execute()
        return res.data or []

    def create_many(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Bulk insert face embedding rows."""
        if not rows:
            return []
        try:
            res = self.client.table("foto_wajah").insert(rows).execute()
            return res.data or []
        except Exception as exc:
            raise ExternalServiceError(f"Gagal menyimpan embedding wajah ke database: {exc}") from exc

    def deactivate_by_nim(self, nim: str) -> list[dict[str, Any]]:
        """Mark all active face rows for a student as inactive; return prior rows."""
        previous = self.list_by_nim(nim, active_only=True)
        if previous:
            self.client.table("foto_wajah").update({"is_active": False}).eq("nim", nim).eq("is_active", True).execute()
        return previous

    def delete_by_nim(self, nim: str) -> list[dict[str, Any]]:
        """Delete all `foto_wajah` rows for a student and remove stored images."""
        existing = self.list_by_nim(nim, active_only=False)
        if existing:
            self.client.table("foto_wajah").delete().eq("nim", nim).execute()
            paths = [row.get("storage_path") for row in existing if row.get("storage_path")]
            if paths:
                try:
                    self.delete_from_bucket(self.settings.storage_bucket_wajah, paths)
                except ExternalServiceError:
                    pass
        return existing

    def upload_face_image(
        self,
        storage_path: str,
        content: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        """Upload a registered face image sample to `foto-wajah` bucket."""
        return self.upload_to_bucket(
            bucket=self.settings.storage_bucket_wajah,
            storage_path=storage_path,
            content=content,
            content_type=content_type,
        )

    def delete_face_images(self, storage_paths: list[str]) -> None:
        """Delete registered face images from `foto-wajah` bucket."""
        if storage_paths:
            try:
                self.delete_from_bucket(self.settings.storage_bucket_wajah, storage_paths)
            except ExternalServiceError:
                pass

    def get_face_signed_url(self, storage_path: str | None) -> str | None:
        """Return a temporary signed URL for a registered face image."""
        return self.create_signed_url(self.settings.storage_bucket_wajah, storage_path)

