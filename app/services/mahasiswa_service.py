"""Service for student profile management and student account CRUD."""

from app.core.config import Settings, get_settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.db.repositories import AuthRepository, FotoWajahRepository, MahasiswaRepository
from app.schemas.auth import MessageResponse
from app.schemas.mahasiswa import (
    MahasiswaCreateRequest,
    MahasiswaListResponse,
    MahasiswaMutationResponse,
    MahasiswaProfileResponse,
    MahasiswaUpdateMeRequest,
    MahasiswaUpdateRequest,
)
from app.services.common import build_student_profile_dict


class MahasiswaService:
    """Manages student profiles (`/mahasiswa/me`) and CRUD operations."""

    def __init__(
        self,
        mahasiswa_repo: MahasiswaRepository,
        foto_wajah_repo: FotoWajahRepository,
        auth_repo: AuthRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.mahasiswa_repo = mahasiswa_repo
        self.foto_wajah_repo = foto_wajah_repo
        self.auth_repo = auth_repo
        self.settings = settings or get_settings()

    def get_profile(self, nim: str) -> MahasiswaProfileResponse:
        """Fetch full profile of a student including active face registration status."""
        student = self.mahasiswa_repo.get_by_nim(nim)
        if not student:
            raise NotFoundError(f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.")
        face_rows = self.foto_wajah_repo.list_by_nim(nim, active_only=True)
        return MahasiswaProfileResponse(**build_student_profile_dict(student, len(face_rows)))

    def update_profile(
        self,
        nim: str,
        payload: MahasiswaUpdateMeRequest | MahasiswaUpdateRequest,
    ) -> MahasiswaMutationResponse:
        """Update allowed profile fields and synchronize Auth email when modified."""
        existing = self.mahasiswa_repo.get_by_nim(nim)
        if not existing:
            raise NotFoundError(f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.")

        fields = self._build_update_fields(payload)
        new_email = fields.get("email")

        updated = self.mahasiswa_repo.update_by_nim(nim, fields)
        if not updated:
            raise NotFoundError(f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.")

        if (
            self.auth_repo
            and new_email
            and new_email != existing.get("email")
            and existing.get("auth_user_id")
        ):
            self.auth_repo.update_auth_email(str(existing["auth_user_id"]), str(new_email))

        face_rows = self.foto_wajah_repo.list_by_nim(nim, active_only=True)
        return MahasiswaMutationResponse(
            message="Profil berhasil diperbarui.",
            data=MahasiswaProfileResponse(**build_student_profile_dict(updated, len(face_rows))),
        )

    def list_students(
        self,
        kelas_id: str | None = None,
        kelas: str | None = None,
        search: str | None = None,
    ) -> MahasiswaListResponse:
        """Return list of students stored in Supabase."""
        effective_kelas_id = kelas_id
        if not effective_kelas_id and kelas:
            resolved = self.mahasiswa_repo.get_kelas_by_name(kelas)
            if not resolved:
                return MahasiswaListResponse(data=[], total=0)
            effective_kelas_id = str(resolved["id"])
        rows = self.mahasiswa_repo.list_all(kelas_id=effective_kelas_id, search=search)
        items = [MahasiswaProfileResponse(**build_student_profile_dict(row)) for row in rows]
        return MahasiswaListResponse(data=items, total=len(items))

    def create_student(self, payload: MahasiswaCreateRequest) -> MahasiswaMutationResponse:
        """Create a student row in `mahasiswa`."""
        if self.mahasiswa_repo.get_by_nim(payload.nim):
            raise ConflictError("NIM sudah terdaftar.")

        kelas_id = self._resolve_kelas_id(payload.kelas_id, payload.kelas)
        created = self.mahasiswa_repo.create(
            {
                "nim": payload.nim,
                "nama_lengkap": payload.nama_lengkap,
                "email": payload.email,
                "no_hp": payload.no_hp,
                "kelas_id": kelas_id,
            }
        )
        return MahasiswaMutationResponse(
            message="Mahasiswa berhasil dibuat.",
            data=MahasiswaProfileResponse(**build_student_profile_dict(created)),
        )

    def delete_student(self, nim: str) -> MessageResponse:
        """Delete a student record along with associated face images and Auth user."""
        existing = self.mahasiswa_repo.get_by_nim(nim)
        if not existing:
            raise NotFoundError(f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.")

        self.foto_wajah_repo.delete_by_nim(nim)
        self.mahasiswa_repo.delete_by_nim(nim)

        auth_user_id = existing.get("auth_user_id")
        if auth_user_id and self.auth_repo:
            try:
                self.auth_repo.delete_auth_user(str(auth_user_id))
            except Exception:
                pass

        return MessageResponse(message=f"Mahasiswa {nim} berhasil dihapus.")

    def _build_update_fields(self, payload: MahasiswaUpdateMeRequest) -> dict[str, object]:
        fields: dict[str, object] = {}
        if payload.nama_lengkap is not None:
            fields["nama_lengkap"] = payload.nama_lengkap
        if payload.email is not None:
            fields["email"] = payload.email
        if payload.no_hp is not None:
            fields["no_hp"] = payload.no_hp
        if payload.kelas_id is not None or payload.kelas is not None:
            fields["kelas_id"] = self._resolve_kelas_id(payload.kelas_id, payload.kelas)
        return fields

    def _resolve_kelas_id(self, kelas_id: str | None, kelas_name: str | None) -> str:
        if kelas_id:
            kelas = self.mahasiswa_repo.get_kelas_by_id(kelas_id)
            if not kelas:
                raise BadRequestError(f"Kelas dengan ID '{kelas_id}' tidak ditemukan.")
            return kelas["id"]
        if kelas_name:
            kelas = self.mahasiswa_repo.get_kelas_by_name(kelas_name)
            if not kelas:
                raise BadRequestError(f"Kelas '{kelas_name}' tidak ditemukan di database.")
            return kelas["id"]
        raise BadRequestError("Informasi kelas wajib valid.")

