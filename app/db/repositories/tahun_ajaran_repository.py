"""Repository for the `tahun_ajaran` Supabase table."""

from typing import Any

from app.core.exceptions import ConflictError, ExternalServiceError
from app.db.repositories.base import BaseRepository


_COLUMNS = (
    "id,tahun,status,semester_ganjil,semester_genap,tanggal_mulai,"
    "tanggal_selesai,created_at,updated_at"
)


class TahunAjaranRepository(BaseRepository):
    """CRUD queries for academic-year master data."""

    def list_all(self, search: str | None = None) -> list[dict[str, Any]]:
        try:
            query = self.client.table("tahun_ajaran").select(_COLUMNS)
            if search and search.strip():
                query = query.ilike("tahun", f"%{search.strip()}%")
            return query.order("tahun", desc=True).execute().data or []
        except Exception as exc:
            raise ExternalServiceError(f"Gagal mengambil daftar tahun ajaran: {exc}") from exc

    def get_by_id(self, tahun_ajaran_id: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("tahun_ajaran")
                .select(_COLUMNS)
                .eq("id", tahun_ajaran_id)
                .limit(1)
                .execute()
            )
            return self.first_or_none(response.data)
        except Exception as exc:
            raise ExternalServiceError(f"Gagal mengambil tahun ajaran: {exc}") from exc

    def get_by_tahun(self, tahun: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("tahun_ajaran")
                .select(_COLUMNS)
                .eq("tahun", tahun)
                .limit(1)
                .execute()
            )
            return self.first_or_none(response.data)
        except Exception as exc:
            raise ExternalServiceError(f"Gagal memeriksa tahun ajaran: {exc}") from exc

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.table("tahun_ajaran").insert(fields).execute()
        except Exception as exc:
            self._raise_write_error(exc, "menyimpan tahun ajaran")
        row = self.first_or_none(response.data)
        if not row or not row.get("id"):
            raise ExternalServiceError("Tahun ajaran gagal dimuat setelah dibuat.")
        return self.get_by_id(str(row["id"])) or row

    def update(self, tahun_ajaran_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.client.table("tahun_ajaran").update(fields).eq("id", tahun_ajaran_id).execute()
        except Exception as exc:
            self._raise_write_error(exc, "memperbarui tahun ajaran")
        return self.get_by_id(tahun_ajaran_id)

    def has_references(self, tahun_ajaran_id: str) -> bool:
        try:
            for table in ("kelas", "jadwal_kuliah"):
                response = (
                    self.client.table(table)
                    .select("id")
                    .eq("tahun_ajaran_id", tahun_ajaran_id)
                    .limit(1)
                    .execute()
                )
                if response.data:
                    return True
            return False
        except Exception as exc:
            raise ExternalServiceError(f"Gagal memeriksa referensi tahun ajaran: {exc}") from exc

    def delete(self, tahun_ajaran_id: str) -> None:
        try:
            self.client.table("tahun_ajaran").delete().eq("id", tahun_ajaran_id).execute()
        except Exception as exc:
            self._raise_write_error(exc, "menghapus tahun ajaran")

    @staticmethod
    def _raise_write_error(exc: Exception, action: str) -> None:
        message = str(exc).lower()
        if "duplicate" in message or "23505" in message or "unique" in message:
            raise ConflictError("Tahun ajaran dengan data tersebut sudah ada.") from exc
        if "foreign key" in message or "23503" in message:
            raise ConflictError("Tahun ajaran masih digunakan oleh data kelas atau jadwal.") from exc
        raise ExternalServiceError(f"Gagal {action}: {exc}") from exc
