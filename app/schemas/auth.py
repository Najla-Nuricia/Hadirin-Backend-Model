"""Pydantic request and response schemas for authentication and password management."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    """Payload to register a new student account."""

    model_config = ConfigDict(populate_by_name=True)

    nim: str = Field(..., min_length=3, max_length=20)
    name: str = Field(
        ...,
        min_length=2,
        max_length=120,
        validation_alias=AliasChoices("name", "nama_lengkap", "fullName"),
    )
    password: str = Field(..., min_length=6, max_length=128)
    email: str | None = Field(default=None, max_length=150)
    no_hp: str | None = Field(
        default=None,
        max_length=20,
        validation_alias=AliasChoices("no_hp", "phoneNumber"),
    )
    kelas_id: str | None = Field(default=None)
    kelas: str | None = Field(
        default=None,
        max_length=40,
        validation_alias=AliasChoices("kelas", "className"),
    )

    @field_validator("nim", "name")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field wajib diisi.")
        return cleaned

    @field_validator("email", "no_hp", "kelas", "kelas_id")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LoginRequest(BaseModel):
    """Payload for student login via NIM or email and password."""

    model_config = ConfigDict(populate_by_name=True)

    nim: str = Field(
        ...,
        min_length=3,
        max_length=150,
        validation_alias=AliasChoices("nim", "identifier", "email", "username"),
    )
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("nim")
    @classmethod
    def _strip_nim(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("NIM atau email wajib diisi.")
        return cleaned


class ChangePasswordRequest(BaseModel):
    """Payload to change the authenticated student's password."""

    model_config = ConfigDict(populate_by_name=True)

    current_password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        validation_alias=AliasChoices("current_password", "old_password", "oldPassword"),
    )
    new_password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        validation_alias=AliasChoices("new_password", "newPassword"),
    )
    confirm_password: str | None = Field(
        default=None,
        max_length=128,
        validation_alias=AliasChoices("confirm_password", "confirmPassword"),
    )


class UserSummary(BaseModel):
    """Authenticated user snapshot returned on login and `/users/me`."""

    nim: str
    name: str
    nama_lengkap: str
    fullName: str
    email: str | None = None
    no_hp: str | None = None
    phoneNumber: str | None = None
    kelas_id: str | None = None
    kelas: str | None = None
    className: str | None = None
    tingkat: int | None = None
    prodi_kode: str | None = None
    prodi: str | None = None
    role: str = "Mahasiswa"
    has_face_registered: bool = False
    face_sample_count: int = 0


class TokenResponse(BaseModel):
    """JWT login response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserSummary


class RegisterResponse(UserSummary):
    """Registration success payload returning created student profile and message."""

    message: str = "Registrasi berhasil"


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str

