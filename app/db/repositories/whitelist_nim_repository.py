"""Repository for the admin-managed student NIM whitelist."""

from typing import Any

from app.core.exceptions import ConflictError, ExternalServiceError
from app.db.repositories.base import BaseRepository


_COLUMNS = "nim,created_at,updated_at,mahasiswa(nama_lengkap,kelas(nama))"


class WhitelistNimRepository(BaseRepository):
    """CRUD and registration-state queries for ``whitelist_nim``."""

    def list_all(self, search: str | None = None) -> list[dict[str, Any]]:
        try:
            query = self.client.table("whitelist_nim").select(_COLUMNS)
            if search and search.strip():
                query = query.ilike("nim", f"%{search.strip()}%")
            response = query.order("nim").execute()
            return response.data or []
        except Exception as exc:
            raise ExternalServiceError(f"Gagal mengambil daftar whitelist NIM: {exc}") from exc

    def get_by_nim(self, nim: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("whitelist_nim")
                .select(_COLUMNS)
                .eq("nim", nim)
                .limit(1)
                .execute()
            )
            return self.first_or_none(response.data)
        except Exception as exc:
            raise ExternalServiceError(f"Gagal memeriksa whitelist NIM: {exc}") from exc

    def create(self, nim: str) -> dict[str, Any]:
        try:
            response = (
                self.client.table("whitelist_nim")
                .insert({"nim": nim})
                .execute()
            )
        except Exception as exc:
            self._raise_write_error(exc, "menyimpan whitelist NIM")
        row = self.first_or_none(response.data)
        if not row:
            raise ExternalServiceError("Whitelist NIM gagal dimuat setelah dibuat.")
        return self.get_by_nim(nim) or row

    def update(self, old_nim: str, new_nim: str) -> dict[str, Any] | None:
        try:
            self.client.table("whitelist_nim").update({"nim": new_nim}).eq(
                "nim", old_nim
            ).execute()
        except Exception as exc:
            self._raise_write_error(exc, "memperbarui whitelist NIM")
        return self.get_by_nim(new_nim)

    def has_student(self, nim: str) -> bool:
        try:
            response = (
                self.client.table("mahasiswa")
                .select("nim")
                .eq("nim", nim)
                .limit(1)
                .execute()
            )
            return bool(response.data)
        except Exception as exc:
            raise ExternalServiceError(f"Gagal memeriksa status registrasi NIM: {exc}") from exc

    def delete(self, nim: str) -> None:
        try:
            self.client.table("whitelist_nim").delete().eq("nim", nim).execute()
        except Exception as exc:
            self._raise_write_error(exc, "menghapus whitelist NIM")

    @staticmethod
    def _raise_write_error(exc: Exception, action: str) -> None:
        message = str(exc).lower()
        if "duplicate" in message or "23505" in message or "unique" in message:
            raise ConflictError("NIM tersebut sudah ada di whitelist.") from exc
        if "foreign key" in message or "23503" in message:
            raise ConflictError("NIM yang sudah terdaftar tidak dapat diubah atau dihapus.") from exc
        raise ExternalServiceError(f"Gagal {action}: {exc}") from exc
