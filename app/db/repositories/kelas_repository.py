"""Repository for the `kelas` Supabase table."""

from typing import Any

from app.core.exceptions import BadRequestError, ConflictError, ExternalServiceError
from app.db.repositories.base import BaseRepository


_COLUMNS = (
    "id,nama,tingkat,program_studi_kode,tahun_ajaran_id,kapasitas,status,"
    "created_at,updated_at,program_studi(nama),tahun_ajaran(tahun)"
)


class KelasRepository(BaseRepository):
    """CRUD queries for class master data."""

    def list_all(
        self,
        search: str | None = None,
        program_studi_kode: str | None = None,
        tahun_ajaran_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            query = self.client.table("kelas").select(_COLUMNS)
            if search and search.strip():
                query = query.ilike("nama", f"%{search.strip()}%")
            if program_studi_kode and program_studi_kode.strip():
                query = query.eq("program_studi_kode", program_studi_kode.strip().upper())
            if tahun_ajaran_id and tahun_ajaran_id.strip():
                query = query.eq("tahun_ajaran_id", tahun_ajaran_id.strip())
            if status and status.strip():
                query = query.eq("status", status.strip().lower())
            return query.order("nama").execute().data or []
        except Exception as exc:
            raise ExternalServiceError(f"Gagal mengambil daftar kelas: {exc}") from exc

    def get_by_id(self, kelas_id: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("kelas")
                .select(_COLUMNS)
                .eq("id", kelas_id)
                .limit(1)
                .execute()
            )
            return self.first_or_none(response.data)
        except Exception as exc:
            raise ExternalServiceError(f"Gagal mengambil kelas: {exc}") from exc

    def get_by_nama_dan_tahun(self, nama: str, tahun_ajaran_id: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("kelas")
                .select(_COLUMNS)
                .eq("nama", nama)
                .eq("tahun_ajaran_id", tahun_ajaran_id)
                .limit(1)
                .execute()
            )
            return self.first_or_none(response.data)
        except Exception as exc:
            raise ExternalServiceError(f"Gagal memeriksa kelas: {exc}") from exc

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.table("kelas").insert(fields).execute()
        except Exception as exc:
            self._raise_write_error(exc, "menyimpan kelas")
        row = self.first_or_none(response.data)
        if not row or not row.get("id"):
            raise ExternalServiceError("Kelas gagal dimuat setelah dibuat.")
        return self.get_by_id(str(row["id"])) or row

    def update(self, kelas_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.client.table("kelas").update(fields).eq("id", kelas_id).execute()
        except Exception as exc:
            self._raise_write_error(exc, "memperbarui kelas")
        return self.get_by_id(kelas_id)

    def has_references(self, kelas_id: str) -> bool:
        try:
            for table in ("jadwal_kuliah", "mahasiswa"):
                response = (
                    self.client.table(table)
                    .select("nim" if table == "mahasiswa" else "id")
                    .eq("kelas_id", kelas_id)
                    .limit(1)
                    .execute()
                )
                if response.data:
                    return True
            return False
        except Exception as exc:
            raise ExternalServiceError(f"Gagal memeriksa referensi kelas: {exc}") from exc

    def delete(self, kelas_id: str) -> None:
        try:
            self.client.table("kelas").delete().eq("id", kelas_id).execute()
        except Exception as exc:
            self._raise_write_error(exc, "menghapus kelas")

    @staticmethod
    def _raise_write_error(exc: Exception, action: str) -> None:
        message = str(exc).lower()
        if "duplicate" in message or "23505" in message or "unique" in message:
            raise ConflictError("Kelas dengan nama tersebut sudah ada pada tahun ajaran itu.") from exc
        if "foreign key" in message or "23503" in message:
            raise ConflictError("Kelas masih digunakan oleh jadwal kuliah atau mahasiswa.") from exc
        if "check" in message or "23514" in message:
            raise BadRequestError("Data kelas melanggar constraint database.") from exc
        raise ExternalServiceError(f"Gagal {action}: {exc}") from exc
