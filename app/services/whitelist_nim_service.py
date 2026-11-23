"""Business rules for the admin-managed student NIM whitelist."""

from typing import Any

from app.core.exceptions import ConflictError, NotFoundError
from app.db.repositories.whitelist_nim_repository import WhitelistNimRepository
from app.schemas.auth import MessageResponse
from app.schemas.whitelist_nim import (
    WhitelistNimItem,
    WhitelistNimListResponse,
    WhitelistNimMutationResponse,
    WhitelistNimWriteRequest,
)


class WhitelistNimService:
    """Validate whitelist mutations and expose registration status."""

    def __init__(self, repository: WhitelistNimRepository) -> None:
        self.repository = repository

    def list(self, search: str | None = None) -> WhitelistNimListResponse:
        rows = self.repository.list_all(search=search)
        items = [self._item(row) for row in rows]
        if search and search.strip():
            term = search.strip().lower()
            items = [
                item
                for item in items
                if term in item.nim.lower()
                or term in item.nama_mahasiswa.lower()
                or term in item.kelas.lower()
            ]
        return WhitelistNimListResponse(data=items, total=len(items))

    def create(self, payload: WhitelistNimWriteRequest) -> WhitelistNimMutationResponse:
        if self.repository.get_by_nim(payload.nim):
            raise ConflictError(f"NIM '{payload.nim}' sudah ada di whitelist.")
        row = self.repository.create(payload.nim)
        return WhitelistNimMutationResponse(
            message="NIM berhasil ditambahkan ke whitelist.", data=self._item(row)
        )

    def update(
        self, old_nim: str, payload: WhitelistNimWriteRequest
    ) -> WhitelistNimMutationResponse:
        old_nim = old_nim.strip()
        if not self.repository.get_by_nim(old_nim):
            raise NotFoundError(f"NIM '{old_nim}' tidak ditemukan di whitelist.")
        if old_nim != payload.nim:
            if self.repository.has_student(old_nim):
                raise ConflictError("NIM yang sudah terdaftar tidak dapat diubah.")
            if self.repository.get_by_nim(payload.nim):
                raise ConflictError(f"NIM '{payload.nim}' sudah ada di whitelist.")
        row = self.repository.update(old_nim, payload.nim)
        if not row:
            raise NotFoundError(f"NIM '{payload.nim}' tidak ditemukan setelah diperbarui.")
        return WhitelistNimMutationResponse(
            message="Whitelist NIM berhasil diperbarui.", data=self._item(row)
        )

    def delete(self, nim: str) -> MessageResponse:
        nim = nim.strip()
        if not self.repository.get_by_nim(nim):
            raise NotFoundError(f"NIM '{nim}' tidak ditemukan di whitelist.")
        if self.repository.has_student(nim):
            raise ConflictError("NIM yang sudah terdaftar tidak dapat dihapus dari whitelist.")
        self.repository.delete(nim)
        return MessageResponse(message="NIM berhasil dihapus dari whitelist.")

    @staticmethod
    def _item(row: dict[str, Any]) -> WhitelistNimItem:
        student = row.get("mahasiswa")
        if isinstance(student, list):
            student = student[0] if student else None
        student = student if isinstance(student, dict) else None
        kelas = student.get("kelas") if student else None
        if isinstance(kelas, list):
            kelas = kelas[0] if kelas else None
        kelas_name = kelas.get("nama") if isinstance(kelas, dict) else None
        return WhitelistNimItem(
            nim=str(row["nim"]),
            nama_mahasiswa=str(student.get("nama_lengkap") or "-") if student else "-",
            kelas=str(kelas_name or "-") if kelas else "-",
            status="Sudah Registrasi" if student else "Belum Registrasi",
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
