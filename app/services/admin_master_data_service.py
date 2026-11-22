"""Admin service for tahun ajaran and mata kuliah CRUD."""

from typing import Any

from app.core.exceptions import ConflictError, NotFoundError
from app.db.repositories.mata_kuliah_repository import MataKuliahRepository
from app.db.repositories.tahun_ajaran_repository import TahunAjaranRepository
from app.schemas.admin_master_data import (
    AdminMataKuliahItem,
    AdminMataKuliahListResponse,
    AdminMataKuliahMutationResponse,
    AdminMataKuliahWriteRequest,
    AdminTahunAjaranItem,
    AdminTahunAjaranListResponse,
    AdminTahunAjaranMutationResponse,
    AdminTahunAjaranWriteRequest,
)
from app.schemas.auth import MessageResponse


class AdminMasterDataService:
    """Validate and orchestrate master-data mutations."""

    def __init__(
        self,
        tahun_ajaran_repo: TahunAjaranRepository,
        mata_kuliah_repo: MataKuliahRepository,
    ) -> None:
        self.tahun_ajaran_repo = tahun_ajaran_repo
        self.mata_kuliah_repo = mata_kuliah_repo

    def list_tahun_ajaran(self, search: str | None = None) -> AdminTahunAjaranListResponse:
        rows = self.tahun_ajaran_repo.list_all(search=search)
        return AdminTahunAjaranListResponse(
            data=[AdminTahunAjaranItem.model_validate(row) for row in rows], total=len(rows)
        )

    def get_tahun_ajaran(self, item_id: str) -> AdminTahunAjaranItem:
        row = self.tahun_ajaran_repo.get_by_id(item_id)
        if not row:
            raise NotFoundError(f"Tahun ajaran dengan ID '{item_id}' tidak ditemukan.")
        return AdminTahunAjaranItem.model_validate(row)

    def create_tahun_ajaran(self, payload: AdminTahunAjaranWriteRequest) -> AdminTahunAjaranMutationResponse:
        if self.tahun_ajaran_repo.get_by_tahun(payload.tahun):
            raise ConflictError(f"Tahun ajaran '{payload.tahun}' sudah terdaftar.")
        row = self.tahun_ajaran_repo.create(self._tahun_fields(payload))
        return AdminTahunAjaranMutationResponse(
            message="Tahun ajaran berhasil dibuat.", data=AdminTahunAjaranItem.model_validate(row)
        )

    def update_tahun_ajaran(
        self, item_id: str, payload: AdminTahunAjaranWriteRequest
    ) -> AdminTahunAjaranMutationResponse:
        if not self.tahun_ajaran_repo.get_by_id(item_id):
            raise NotFoundError(f"Tahun ajaran dengan ID '{item_id}' tidak ditemukan.")
        duplicate = self.tahun_ajaran_repo.get_by_tahun(payload.tahun)
        if duplicate and str(duplicate.get("id")) != item_id:
            raise ConflictError(f"Tahun ajaran '{payload.tahun}' sudah terdaftar.")
        row = self.tahun_ajaran_repo.update(item_id, self._tahun_fields(payload))
        if not row:
            raise NotFoundError(f"Tahun ajaran dengan ID '{item_id}' tidak ditemukan.")
        return AdminTahunAjaranMutationResponse(
            message="Tahun ajaran berhasil diperbarui.", data=AdminTahunAjaranItem.model_validate(row)
        )

    def delete_tahun_ajaran(self, item_id: str) -> MessageResponse:
        if not self.tahun_ajaran_repo.get_by_id(item_id):
            raise NotFoundError(f"Tahun ajaran dengan ID '{item_id}' tidak ditemukan.")
        if self.tahun_ajaran_repo.has_references(item_id):
            raise ConflictError("Tahun ajaran masih digunakan oleh data kelas atau jadwal.")
        self.tahun_ajaran_repo.delete(item_id)
        return MessageResponse(message="Tahun ajaran berhasil dihapus.")

    def list_mata_kuliah(self, search: str | None = None) -> AdminMataKuliahListResponse:
        rows = self.mata_kuliah_repo.list_all(search=search)
        return AdminMataKuliahListResponse(
            data=[AdminMataKuliahItem.model_validate(row) for row in rows], total=len(rows)
        )

    def get_mata_kuliah(self, kode: str) -> AdminMataKuliahItem:
        normalized = kode.strip().upper()
        row = self.mata_kuliah_repo.get_by_kode(normalized)
        if not row:
            raise NotFoundError(f"Mata kuliah dengan kode '{normalized}' tidak ditemukan.")
        return AdminMataKuliahItem.model_validate(row)

    def create_mata_kuliah(self, payload: AdminMataKuliahWriteRequest) -> AdminMataKuliahMutationResponse:
        if self.mata_kuliah_repo.get_by_kode(payload.kode):
            raise ConflictError(f"Mata kuliah dengan kode '{payload.kode}' sudah terdaftar.")
        row = self.mata_kuliah_repo.create(self._mata_fields(payload))
        return AdminMataKuliahMutationResponse(
            message="Mata kuliah berhasil dibuat.", data=AdminMataKuliahItem.model_validate(row)
        )

    def update_mata_kuliah(
        self, kode: str, payload: AdminMataKuliahWriteRequest
    ) -> AdminMataKuliahMutationResponse:
        old_kode = kode.strip().upper()
        if not self.mata_kuliah_repo.get_by_kode(old_kode):
            raise NotFoundError(f"Mata kuliah dengan kode '{old_kode}' tidak ditemukan.")
        if payload.kode != old_kode:
            if self.mata_kuliah_repo.get_by_kode(payload.kode):
                raise ConflictError(f"Mata kuliah dengan kode '{payload.kode}' sudah terdaftar.")
            if self.mata_kuliah_repo.has_references(old_kode):
                raise ConflictError("Kode mata kuliah yang sudah dipakai jadwal tidak dapat diubah.")
        row = self.mata_kuliah_repo.update(old_kode, self._mata_fields(payload))
        if not row:
            raise NotFoundError(f"Mata kuliah dengan kode '{payload.kode}' tidak ditemukan.")
        return AdminMataKuliahMutationResponse(
            message="Mata kuliah berhasil diperbarui.", data=AdminMataKuliahItem.model_validate(row)
        )

    def delete_mata_kuliah(self, kode: str) -> MessageResponse:
        normalized = kode.strip().upper()
        if not self.mata_kuliah_repo.get_by_kode(normalized):
            raise NotFoundError(f"Mata kuliah dengan kode '{normalized}' tidak ditemukan.")
        if self.mata_kuliah_repo.has_references(normalized):
            raise ConflictError("Mata kuliah masih digunakan oleh jadwal.")
        self.mata_kuliah_repo.delete(normalized)
        return MessageResponse(message="Mata kuliah berhasil dihapus.")

    @staticmethod
    def _tahun_fields(payload: AdminTahunAjaranWriteRequest) -> dict[str, Any]:
        return {
            "tahun": payload.tahun,
            "status": payload.status,
            "semester_ganjil": payload.semester_ganjil,
            "semester_genap": payload.semester_genap,
            "tanggal_mulai": payload.tanggal_mulai.isoformat() if payload.tanggal_mulai else None,
            "tanggal_selesai": payload.tanggal_selesai.isoformat() if payload.tanggal_selesai else None,
        }

    @staticmethod
    def _mata_fields(payload: AdminMataKuliahWriteRequest) -> dict[str, Any]:
        return {"kode": payload.kode, "nama": payload.nama, "semester": payload.semester, "sks": payload.sks}
