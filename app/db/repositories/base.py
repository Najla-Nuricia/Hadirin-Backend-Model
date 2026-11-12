"""Shared base repository helpers for Supabase DB and Storage operations."""

from typing import Any

from supabase import Client

from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError


class BaseRepository:
    """Common Supabase helper utilities shared by domain repositories."""

    def __init__(self, client: Client, settings: Settings | None = None) -> None:
        self.client = client
        self.settings = settings or get_settings()

    @staticmethod
    def first_or_none(data: list[dict[str, Any]] | None) -> dict[str, Any] | None:
        """Return first row from Supabase result list, or None if empty."""
        if not data:
            return None
        return data[0]

    @staticmethod
    def fetch_rows_in(
        client: Client,
        table: str,
        columns: str,
        filter_column: str,
        values: list[str],
        order_by: str,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Read every matching row across Supabase response pages without truncation."""
        if not values:
            return []
        rows: list[dict[str, Any]] = []
        while True:
            res = (
                client.table(table)
                .select(columns, count="exact")
                .in_(filter_column, values)
                .order(order_by)
                .range(len(rows), len(rows) + page_size - 1)
                .execute()
            )
            page = res.data or []
            rows.extend(page)
            if not page or len(rows) >= (res.count or 0):
                return rows

    def upload_to_bucket(
        self,
        bucket: str,
        storage_path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        upsert: bool = True,
    ) -> str:
        """Upload raw bytes to a Supabase Storage bucket and return the path."""
        try:
            self.client.storage.from_(bucket).upload(
                path=storage_path,
                file=content,
                file_options={
                    "content-type": content_type,
                    "upsert": "true" if upsert else "false",
                },
            )
            return storage_path
        except Exception as exc:
            raise ExternalServiceError(f"Gagal mengunggah file ke storage ({bucket}): {exc}") from exc

    def create_signed_url(
        self,
        bucket: str,
        storage_path: str | None,
        expires_in: int = 3600,
    ) -> str | None:
        """Generate a temporary signed URL for a private storage object."""
        if not storage_path:
            return None
        try:
            res = self.client.storage.from_(bucket).create_signed_url(storage_path, expires_in)
            if isinstance(res, dict):
                return res.get("signedURL") or res.get("signedUrl")
            return None
        except Exception:
            return None

    def delete_from_bucket(self, bucket: str, paths: list[str]) -> None:
        """Remove storage objects cleanly; ignore empty lists."""
        cleaned = [p for p in paths if p]
        if not cleaned:
            return
        try:
            self.client.storage.from_(bucket).remove(cleaned)
        except Exception as exc:
            raise ExternalServiceError(f"Gagal menghapus file dari storage ({bucket}): {exc}") from exc

