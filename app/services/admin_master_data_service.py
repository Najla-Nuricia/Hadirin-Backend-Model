"""Admin service for tahun ajaran, mata kuliah, ruangan, dosen, and kelas CRUD."""

from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, ExternalServiceError, NotFoundError
from app.db.repositories.auth_repository import AuthRepository
from app.db.repositories.dosen_repository import DosenRepository
from app.db.repositories.kelas_repository import KelasRepository
from app.db.repositories.mata_kuliah_repository import MataKuliahRepository
from app.db.repositories.program_studi_repository import ProgramStudiRepository
from app.db.repositories.ruangan_repository import RuanganRepository
from app.db.repositories.tahun_ajaran_repository import TahunAjaranRepository
from app.schemas.admin_master_data import (
    AdminDosenItem,
    AdminDosenListResponse,
    AdminDosenMutationResponse,
    AdminDosenWriteRequest,
    AdminKelasItem,
    AdminKelasListResponse,
    AdminKelasMutationResponse,
    AdminKelasWriteRequest,
    AdminMataKuliahItem,
    AdminMataKuliahListResponse,
    AdminMataKuliahMutationResponse,
    AdminMataKuliahWriteRequest,
    AdminRuanganItem,
    AdminRuanganListResponse,
    AdminRuanganMutationResponse,
    AdminRuanganWriteRequest,
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
        ruangan_repo: RuanganRepository | None = None,
        dosen_repo: DosenRepository | None = None,
        kelas_repo: KelasRepository | None = None,
        program_studi_repo: ProgramStudiRepository | None = None,
        auth_repo: AuthRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.tahun_ajaran_repo = tahun_ajaran_repo
        self.mata_kuliah_repo = mata_kuliah_repo
        self.ruangan_repo = ruangan_repo
        self.dosen_repo = dosen_repo
        self.kelas_repo = kelas_repo
        self.program_studi_repo = program_studi_repo
        self.auth_repo = auth_repo
        self.settings = settings or get_settings()

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

    # ── Ruangan ────────────────────────────────────────────────────────────

    def _require_ruangan_repo(self) -> RuanganRepository:
        if self.ruangan_repo is None:
            raise ExternalServiceError("Repositori ruangan belum dikonfigurasi.")
        return self.ruangan_repo

    def list_ruangan(self, search: str | None = None) -> AdminRuanganListResponse:
        rows = self._require_ruangan_repo().list_all(search=search)
        return AdminRuanganListResponse(
            data=[AdminRuanganItem.model_validate(row) for row in rows], total=len(rows)
        )

    def get_ruangan(self, kode: str) -> AdminRuanganItem:
        normalized = kode.strip().upper()
        row = self._require_ruangan_repo().get_by_kode(normalized)
        if not row:
            raise NotFoundError(f"Ruangan dengan kode '{normalized}' tidak ditemukan.")
        return AdminRuanganItem.model_validate(row)

    def create_ruangan(self, payload: AdminRuanganWriteRequest) -> AdminRuanganMutationResponse:
        repo = self._require_ruangan_repo()
        if repo.get_by_kode(payload.kode):
            raise ConflictError(f"Ruangan dengan kode '{payload.kode}' sudah terdaftar.")
        row = repo.create({"kode": payload.kode, "nama": payload.nama})
        return AdminRuanganMutationResponse(
            message="Ruangan berhasil dibuat.", data=AdminRuanganItem.model_validate(row)
        )

    def update_ruangan(
        self, kode: str, payload: AdminRuanganWriteRequest
    ) -> AdminRuanganMutationResponse:
        repo = self._require_ruangan_repo()
        old_kode = kode.strip().upper()
        if not repo.get_by_kode(old_kode):
            raise NotFoundError(f"Ruangan dengan kode '{old_kode}' tidak ditemukan.")
        if payload.kode != old_kode:
            if repo.get_by_kode(payload.kode):
                raise ConflictError(f"Ruangan dengan kode '{payload.kode}' sudah terdaftar.")
            if repo.has_references(old_kode):
                raise ConflictError("Kode ruangan yang sudah dipakai jadwal tidak dapat diubah.")
        row = repo.update(old_kode, {"kode": payload.kode, "nama": payload.nama})
        if not row:
            raise NotFoundError(f"Ruangan dengan kode '{payload.kode}' tidak ditemukan.")
        return AdminRuanganMutationResponse(
            message="Ruangan berhasil diperbarui.", data=AdminRuanganItem.model_validate(row)
        )

    def delete_ruangan(self, kode: str) -> MessageResponse:
        repo = self._require_ruangan_repo()
        normalized = kode.strip().upper()
        if not repo.get_by_kode(normalized):
            raise NotFoundError(f"Ruangan dengan kode '{normalized}' tidak ditemukan.")
        if repo.has_references(normalized):
            raise ConflictError("Ruangan masih digunakan oleh jadwal kuliah.")
        repo.delete(normalized)
        return MessageResponse(message="Ruangan berhasil dihapus.")

    # ── Dosen ──────────────────────────────────────────────────────────────

    def _require_dosen_repo(self) -> DosenRepository:
        if self.dosen_repo is None:
            raise ExternalServiceError("Repositori dosen belum dikonfigurasi.")
        return self.dosen_repo

    def list_dosen(self, search: str | None = None) -> AdminDosenListResponse:
        rows = self._require_dosen_repo().list_all(search=search)
        return AdminDosenListResponse(
            data=[AdminDosenItem.model_validate(row) for row in rows], total=len(rows)
        )

    def get_dosen(self, nip: str) -> AdminDosenItem:
        normalized = nip.strip()
        row = self._require_dosen_repo().get_by_nip(normalized)
        if not row:
            raise NotFoundError(f"Dosen dengan NIP '{normalized}' tidak ditemukan.")
        return AdminDosenItem.model_validate(row)

    def create_dosen(self, payload: AdminDosenWriteRequest) -> AdminDosenMutationResponse:
        """Create the Supabase Auth account (default password) then the `dosen` row."""
        repo = self._require_dosen_repo()
        auth_repo = self._require_auth_repo()
        if repo.get_by_nip(payload.nip):
            raise ConflictError(f"Dosen dengan NIP '{payload.nip}' sudah terdaftar.")
        if payload.email and repo.get_by_email(payload.email):
            raise ConflictError(f"Email '{payload.email}' sudah digunakan dosen lain.")

        auth_email = payload.email or self.settings.synthetic_email_for_nim(payload.nip)
        auth_user_id = auth_repo.create_auth_user(
            email=auth_email,
            password=self.settings.dosen_initial_password,
            user_metadata={"nip": payload.nip, "nama": payload.nama, "peran": "dosen"},
        )

        try:
            created = repo.create(
                {
                    "nip": payload.nip,
                    "nama": payload.nama,
                    "email": payload.email,
                    "no_hp": payload.no_hp,
                    "auth_user_id": auth_user_id,
                }
            )
            auth_repo.link_dosen_auth_user(auth_user_id, payload.nip)
        except Exception:
            try:
                auth_repo.delete_auth_user(auth_user_id)
            except Exception:
                pass
            raise

        return AdminDosenMutationResponse(
            message="Dosen berhasil dibuat.",
            data=AdminDosenItem.model_validate(created),
            initial_password=self.settings.dosen_initial_password,
        )

    def update_dosen(
        self, nip: str, payload: AdminDosenWriteRequest
    ) -> AdminDosenMutationResponse:
        repo = self._require_dosen_repo()
        old_nip = nip.strip()
        existing = repo.get_by_nip(old_nip)
        if not existing:
            raise NotFoundError(f"Dosen dengan NIP '{old_nip}' tidak ditemukan.")

        if payload.nip != old_nip:
            if repo.get_by_nip(payload.nip):
                raise ConflictError(f"Dosen dengan NIP '{payload.nip}' sudah terdaftar.")
            if repo.has_references(old_nip):
                raise ConflictError("NIP dosen yang sudah dipakai jadwal tidak dapat diubah.")

        if payload.email:
            duplicate = repo.get_by_email(payload.email)
            if duplicate and str(duplicate.get("nip")) != old_nip:
                raise ConflictError(f"Email '{payload.email}' sudah digunakan dosen lain.")

        previous_email = existing.get("email")
        auth_user_id = existing.get("auth_user_id")

        row = repo.update(
            old_nip,
            {
                "nip": payload.nip,
                "nama": payload.nama,
                "email": payload.email,
                "no_hp": payload.no_hp,
            },
        )
        if not row:
            raise NotFoundError(f"Dosen dengan NIP '{payload.nip}' tidak ditemukan.")

        if (
            self.auth_repo
            and auth_user_id
            and payload.email
            and payload.email != previous_email
        ):
            self.auth_repo.update_auth_email(str(auth_user_id), payload.email)

        return AdminDosenMutationResponse(
            message="Dosen berhasil diperbarui.", data=AdminDosenItem.model_validate(row)
        )

    def delete_dosen(self, nip: str) -> MessageResponse:
        repo = self._require_dosen_repo()
        normalized = nip.strip()
        existing = repo.get_by_nip(normalized)
        if not existing:
            raise NotFoundError(f"Dosen dengan NIP '{normalized}' tidak ditemukan.")
        if repo.has_references(normalized):
            raise ConflictError("Dosen masih digunakan oleh jadwal atau sesi presensi.")
        repo.delete(normalized)
        if self.auth_repo and existing.get("auth_user_id"):
            try:
                self.auth_repo.delete_auth_user(str(existing["auth_user_id"]))
            except Exception:
                pass
        return MessageResponse(message="Dosen berhasil dihapus.")

    # ── Kelas ──────────────────────────────────────────────────────────────

    def _require_kelas_repo(self) -> KelasRepository:
        if self.kelas_repo is None:
            raise ExternalServiceError("Repositori kelas belum dikonfigurasi.")
        return self.kelas_repo

    def _require_auth_repo(self) -> AuthRepository:
        if self.auth_repo is None:
            raise ExternalServiceError("Repositori autentikasi belum dikonfigurasi.")
        return self.auth_repo

    def list_kelas(
        self,
        search: str | None = None,
        program_studi_kode: str | None = None,
        tahun_ajaran_id: str | None = None,
        status: str | None = None,
    ) -> AdminKelasListResponse:
        rows = self._require_kelas_repo().list_all(
            search=search,
            program_studi_kode=program_studi_kode,
            tahun_ajaran_id=tahun_ajaran_id,
            status=status,
        )
        return AdminKelasListResponse(
            data=[self._kelas_item(row) for row in rows], total=len(rows)
        )

    def get_kelas(self, kelas_id: str) -> AdminKelasItem:
        row = self._require_kelas_repo().get_by_id(kelas_id)
        if not row:
            raise NotFoundError(f"Kelas dengan ID '{kelas_id}' tidak ditemukan.")
        return self._kelas_item(row)

    def create_kelas(self, payload: AdminKelasWriteRequest) -> AdminKelasMutationResponse:
        repo = self._require_kelas_repo()
        tahun_ajaran_id = str(payload.tahun_ajaran_id)
        self._ensure_tahun_ajaran_exists(tahun_ajaran_id)
        self._ensure_program_studi_exists(payload.program_studi_kode)
        if repo.get_by_nama_dan_tahun(payload.nama, tahun_ajaran_id):
            raise ConflictError(
                f"Kelas '{payload.nama}' sudah terdaftar pada tahun ajaran tersebut."
            )
        row = repo.create(self._kelas_fields(payload))
        return AdminKelasMutationResponse(
            message="Kelas berhasil dibuat.", data=self._kelas_item(row)
        )

    def update_kelas(
        self, kelas_id: str, payload: AdminKelasWriteRequest
    ) -> AdminKelasMutationResponse:
        repo = self._require_kelas_repo()
        if not repo.get_by_id(kelas_id):
            raise NotFoundError(f"Kelas dengan ID '{kelas_id}' tidak ditemukan.")
        tahun_ajaran_id = str(payload.tahun_ajaran_id)
        self._ensure_tahun_ajaran_exists(tahun_ajaran_id)
        self._ensure_program_studi_exists(payload.program_studi_kode)
        duplicate = repo.get_by_nama_dan_tahun(payload.nama, tahun_ajaran_id)
        if duplicate and str(duplicate.get("id")) != kelas_id:
            raise ConflictError(
                f"Kelas '{payload.nama}' sudah terdaftar pada tahun ajaran tersebut."
            )
        row = repo.update(kelas_id, self._kelas_fields(payload))
        if not row:
            raise NotFoundError(f"Kelas dengan ID '{kelas_id}' tidak ditemukan.")
        return AdminKelasMutationResponse(
            message="Kelas berhasil diperbarui.", data=self._kelas_item(row)
        )

    def delete_kelas(self, kelas_id: str) -> MessageResponse:
        repo = self._require_kelas_repo()
        if not repo.get_by_id(kelas_id):
            raise NotFoundError(f"Kelas dengan ID '{kelas_id}' tidak ditemukan.")
        if repo.has_references(kelas_id):
            raise ConflictError("Kelas masih digunakan oleh jadwal kuliah atau mahasiswa.")
        repo.delete(kelas_id)
        return MessageResponse(message="Kelas berhasil dihapus.")

    def _ensure_tahun_ajaran_exists(self, tahun_ajaran_id: str) -> None:
        if not self.tahun_ajaran_repo.get_by_id(tahun_ajaran_id):
            raise NotFoundError(
                f"Tahun ajaran dengan ID '{tahun_ajaran_id}' tidak ditemukan."
            )

    def _ensure_program_studi_exists(self, kode: str) -> None:
        if self.program_studi_repo and not self.program_studi_repo.get_by_kode(kode):
            raise NotFoundError(f"Program studi dengan kode '{kode}' tidak ditemukan.")

    @staticmethod
    def _kelas_item(row: dict[str, Any]) -> AdminKelasItem:
        program_studi = row.get("program_studi") or {}
        tahun_ajaran = row.get("tahun_ajaran") or {}
        return AdminKelasItem(
            id=str(row["id"]),
            nama=str(row.get("nama") or ""),
            tingkat=int(row.get("tingkat") or 1),
            program_studi_kode=str(row.get("program_studi_kode") or ""),
            tahun_ajaran_id=str(row.get("tahun_ajaran_id") or ""),
            kapasitas=int(row.get("kapasitas") or 0),
            status=str(row.get("status") or "aktif"),
            program_studi_nama=program_studi.get("nama"),
            tahun_ajaran_tahun=tahun_ajaran.get("tahun"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    @staticmethod
    def _kelas_fields(payload: AdminKelasWriteRequest) -> dict[str, Any]:
        return {
            "nama": payload.nama,
            "tingkat": payload.tingkat,
            "program_studi_kode": payload.program_studi_kode,
            "tahun_ajaran_id": str(payload.tahun_ajaran_id),
            "kapasitas": payload.kapasitas,
            "status": payload.status,
        }

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
