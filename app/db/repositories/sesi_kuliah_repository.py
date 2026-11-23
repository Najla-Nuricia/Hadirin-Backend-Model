"""Repository for the `sesi_kuliah` Supabase table."""

from typing import Any

from app.core.exceptions import ExternalServiceError
from app.db.repositories.base import BaseRepository


_COLUMNS = "nomor,jam_mulai,jam_selesai"


class SesiKuliahRepository(BaseRepository):
    """Read queries for class session (time slot) master data."""

    def list_all(self) -> list[dict[str, Any]]:
        try:
            res = self.client.table("sesi_kuliah").select(_COLUMNS).order("nomor").execute()
            return res.data or []
        except Exception as exc:
            raise ExternalServiceError(f"Gagal mengambil daftar sesi kuliah: {exc}") from exc
