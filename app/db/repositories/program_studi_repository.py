"""Repository for the `program_studi` Supabase table."""

from typing import Any

from app.core.exceptions import ExternalServiceError
from app.db.repositories.base import BaseRepository


_COLUMNS = "kode,nama,created_at,updated_at"


class ProgramStudiRepository(BaseRepository):
    """Read queries for study-program master data."""

    def list_all(self, search: str | None = None) -> list[dict[str, Any]]:
        try:
            query = self.client.table("program_studi").select(_COLUMNS)
            if search and search.strip():
                term = search.strip()
                query = query.or_(f"kode.ilike.%{term}%,nama.ilike.%{term}%")
            return query.order("kode").execute().data or []
        except Exception as exc:
            raise ExternalServiceError(f"Gagal mengambil daftar program studi: {exc}") from exc
