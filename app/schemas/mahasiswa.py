"""Pydantic schemas for student profile and account management."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.schemas.auth import UserSummary


class MahasiswaProfileResponse(UserSummary):
    """Student profile payload with normalized keys for Flutter and REST clients."""


class MahasiswaUpdateMeRequest(BaseModel):
    """Payload for updating the logged-in student's profile."""

    model_config = ConfigDict(populate_by_name=True)

    nama_lengkap: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
        validation_alias=AliasChoices("nama_lengkap", "fullName", "name"),
    )
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

    @field_validator("nama_lengkap", "email", "no_hp", "kelas", "kelas_id")
    @classmethod
    def _clean_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class MahasiswaCreateRequest(BaseModel):
    """Payload to create a student record."""

    model_config = ConfigDict(populate_by_name=True)

    nim: str = Field(..., min_length=3, max_length=20)
    nama_lengkap: str = Field(
        ...,
        min_length=2,
        max_length=120,
        validation_alias=AliasChoices("nama_lengkap", "fullName", "name"),
    )
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


class MahasiswaUpdateRequest(MahasiswaUpdateMeRequest):
    """Payload to update a student record by NIM."""


class MahasiswaMutationResponse(BaseModel):
    """Mutation response containing the updated student profile."""

    message: str
    data: MahasiswaProfileResponse


class MahasiswaListResponse(BaseModel):
    """Response wrapper for student list queries."""

    data: list[MahasiswaProfileResponse]
    total: int

