"""Repository for the `mata_kuliah` Supabase table."""

from typing import Any

from app.core.exceptions import BadRequestError, ConflictError, ExternalServiceError
from app.db.repositories.base import BaseRepository


_COLUMNS = "kode,nama,semester,sks,created_at,updated_at"


class MataKuliahRepository(BaseRepository):
    """CRUD queries for course master data."""

    def list_all(self, search: str | None = None) -> list[dict[str, Any]]:
        try:
            query = self.client.table("mata_kuliah").select(_COLUMNS)
            if search and search.strip():
                term = search.strip()
                query = query.or_(f"kode.ilike.%{term}%,nama.ilike.%{term}%")
            return query.order("kode").execute().data or []
        except Exception as exc:
            raise ExternalServiceError(f"Gagal mengambil daftar mata kuliah: {exc}") from exc

    def get_by_kode(self, kode: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("mata_kuliah")
                .select(_COLUMNS)
                .eq("kode", kode)
                .limit(1)
                .execute()
            )
            return self.first_or_none(response.data)
        except Exception as exc:
            raise ExternalServiceError(f"Gagal mengambil mata kuliah: {exc}") from exc

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.table("mata_kuliah").insert(fields).execute()
        except Exception as exc:
            self._raise_write_error(exc, "menyimpan mata kuliah")
        row = self.first_or_none(response.data)
        if not row or not row.get("kode"):
            raise ExternalServiceError("Mata kuliah gagal dimuat setelah dibuat.")
        return self.get_by_kode(str(row["kode"])) or row

    def update(self, kode: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.client.table("mata_kuliah").update(fields).eq("kode", kode).execute()
        except Exception as exc:
            self._raise_write_error(exc, "memperbarui mata kuliah")
        return self.get_by_kode(str(fields.get("kode", kode)))

    def has_references(self, kode: str) -> bool:
        try:
            response = (
                self.client.table("jadwal_kuliah")
                .select("id")
                .eq("mata_kuliah_kode", kode)
                .limit(1)
                .execute()
            )
            return bool(response.data)
        except Exception as exc:
            raise ExternalServiceError(f"Gagal memeriksa referensi mata kuliah: {exc}") from exc

    def delete(self, kode: str) -> None:
        try:
            self.client.table("mata_kuliah").delete().eq("kode", kode).execute()
        except Exception as exc:
            self._raise_write_error(exc, "menghapus mata kuliah")

    @staticmethod
    def _raise_write_error(exc: Exception, action: str) -> None:
        message = str(exc).lower()
        if "duplicate" in message or "23505" in message or "unique" in message:
            raise ConflictError("Mata kuliah dengan kode tersebut sudah ada.") from exc
        if "foreign key" in message or "23503" in message:
            raise ConflictError("Mata kuliah masih digunakan oleh jadwal.") from exc
        if "check" in message or "23514" in message:
            raise BadRequestError("Data mata kuliah melanggar constraint database.") from exc
        raise ExternalServiceError(f"Gagal {action}: {exc}") from exc
