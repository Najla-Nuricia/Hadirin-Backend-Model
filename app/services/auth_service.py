"""Authentication service handling registration, Supabase Auth verification, JWT, and passwords."""

from app.core.config import Settings, get_settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, UnauthorizedError
from app.core.security import create_access_token, hash_password
from app.db.repositories import AuthRepository, FotoWajahRepository, MahasiswaRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserSummary,
)
from app.services.common import build_student_profile_dict


class AuthService:
    """Coordinates account registration, credential verification, JWT issuing, and password updates."""

    def __init__(
        self,
        auth_repo: AuthRepository,
        mahasiswa_repo: MahasiswaRepository,
        foto_wajah_repo: FotoWajahRepository,
        settings: Settings | None = None,
    ) -> None:
        self.auth_repo = auth_repo
        self.mahasiswa_repo = mahasiswa_repo
        self.foto_wajah_repo = foto_wajah_repo
        self.settings = settings or get_settings()

    def register(self, payload: RegisterRequest) -> RegisterResponse:
        """Register a new student in `auth.users` and `mahasiswa`, linked atomically."""
        if self.mahasiswa_repo.get_by_nim(payload.nim):
            raise ConflictError("NIM sudah terdaftar.")

        if payload.email and self.mahasiswa_repo.get_by_email(payload.email):
            raise ConflictError("Email sudah digunakan oleh mahasiswa lain.")

        resolved_kelas_id = self._resolve_kelas_id(payload.kelas_id, payload.kelas)
        auth_email = payload.email or self.settings.synthetic_email_for_nim(payload.nim)

        # Ensure bcrypt password hash pipeline validates input cleanly.
        hash_password(payload.password)

        auth_user_id = self.auth_repo.create_auth_user(
            email=auth_email,
            password=payload.password,
            user_metadata={"nim": payload.nim, "nama_lengkap": payload.name, "peran": "mahasiswa"},
        )

        insert_payload: dict[str, object] = {
            "nim": payload.nim,
            "nama_lengkap": payload.name,
            "email": payload.email,
            "no_hp": payload.no_hp,
            "kelas_id": resolved_kelas_id,
            "auth_user_id": auth_user_id,
        }

        try:
            created = self.mahasiswa_repo.create(insert_payload)
            self.auth_repo.link_student_auth_user(auth_user_id, payload.nim)
        except Exception:
            self.auth_repo.delete_auth_user(auth_user_id)
            raise

        profile = build_student_profile_dict(created, face_sample_count=0)
        return RegisterResponse(**profile, message="Registrasi berhasil")

    def login(self, payload: LoginRequest) -> TokenResponse:
        """Authenticate a student against Supabase GoTrue and return an HS256 JWT."""
        student = self._find_student_by_identifier(payload.nim)
        if not student or not student.get("auth_user_id"):
            raise UnauthorizedError("NIM/email atau password salah.")

        auth_email = student.get("email") or self.settings.synthetic_email_for_nim(student["nim"])
        verified_user_id = self.auth_repo.verify_credentials(auth_email, payload.password)
        if not verified_user_id:
            raise UnauthorizedError("NIM/email atau password salah.")

        face_rows = self.foto_wajah_repo.list_by_nim(student["nim"], active_only=True)
        profile = build_student_profile_dict(student, face_sample_count=len(face_rows))

        access_token = create_access_token(
            subject=student["nim"],
            role="mahasiswa",
            extra_claims={"auth_user_id": str(student["auth_user_id"])},
            settings=self.settings,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.settings.jwt_expire_minutes * 60,
            user=UserSummary(**profile),
        )

    def change_password(self, nim: str, payload: ChangePasswordRequest) -> MessageResponse:
        """Verify current password and update the password in Supabase Auth."""
        if payload.confirm_password is not None and payload.new_password != payload.confirm_password:
            raise BadRequestError("Konfirmasi password baru tidak cocok.")
        if payload.new_password == payload.current_password:
            raise BadRequestError("Password baru tidak boleh sama dengan password saat ini.")

        student = self.mahasiswa_repo.get_by_nim(nim)
        if not student or not student.get("auth_user_id"):
            raise NotFoundError("Akun mahasiswa tidak ditemukan.")

        auth_email = student.get("email") or self.settings.synthetic_email_for_nim(nim)
        if not self.auth_repo.verify_credentials(auth_email, payload.current_password):
            raise BadRequestError("Password saat ini tidak sesuai.")

        hash_password(payload.new_password)
        self.auth_repo.update_auth_password(str(student["auth_user_id"]), payload.new_password)
        return MessageResponse(message="Password berhasil diubah.")

    def _find_student_by_identifier(self, identifier: str) -> dict | None:
        cleaned = identifier.strip()
        if "@" in cleaned:
            return self.mahasiswa_repo.get_by_email(cleaned)
        return self.mahasiswa_repo.get_by_nim(cleaned)

    def _resolve_kelas_id(self, kelas_id: str | None, kelas_name: str | None) -> str | None:
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
        return None

