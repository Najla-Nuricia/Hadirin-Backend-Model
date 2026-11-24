"""Schemas for the admin student NIM whitelist."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


WhitelistRegistrationStatus = Literal["Belum Registrasi", "Sudah Registrasi"]


class WhitelistNimWriteRequest(BaseModel):
    """Payload used when an admin creates or renames a whitelisted NIM."""

    nim: str = Field(..., min_length=3, max_length=20)

    @field_validator("nim", mode="before")
    @classmethod
    def normalize_nim(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned.isdigit():
            raise ValueError("NIM hanya boleh berisi angka.")
        return cleaned


class WhitelistNimItem(BaseModel):
    """Whitelist row enriched with the linked student's profile when available."""

    nim: str
    nama_mahasiswa: str = "-"
    kelas: str = "-"
    status: WhitelistRegistrationStatus
    created_at: str | None = None
    updated_at: str | None = None


class WhitelistNimListResponse(BaseModel):
    data: list[WhitelistNimItem]
    total: int


class WhitelistNimMutationResponse(BaseModel):
    message: str
    data: WhitelistNimItem
