"""Schemas for admin academic master-data CRUD."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TahunAjaranStatus = Literal["aktif", "non_aktif"]


class AdminTahunAjaranWriteRequest(BaseModel):
    """Create/update payload for an academic year."""

    model_config = ConfigDict(populate_by_name=True)

    tahun: str = Field(..., min_length=9, max_length=9, description="Format YYYY/YYYY.")
    status: TahunAjaranStatus = "non_aktif"
    semester_ganjil: bool = True
    semester_genap: bool = True
    tanggal_mulai: date | None = None
    tanggal_selesai: date | None = None

    @field_validator("tahun", mode="before")
    @classmethod
    def validate_tahun(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        parts = cleaned.split("/")
        if len(parts) != 2 or any(len(part) != 4 or not part.isdigit() for part in parts):
            raise ValueError("tahun harus menggunakan format YYYY/YYYY.")
        if int(parts[1]) != int(parts[0]) + 1:
            raise ValueError("Tahun ajaran harus terdiri dari dua tahun berurutan.")
        return cleaned

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower().replace("-", "_")
            return "non_aktif" if normalized == "nonaktif" else normalized
        return value

    @model_validator(mode="after")
    def validate_semesters_and_dates(self) -> "AdminTahunAjaranWriteRequest":
        if not self.semester_ganjil and not self.semester_genap:
            raise ValueError("Minimal satu semester harus dipilih.")
        if (
            self.tanggal_mulai is not None
            and self.tanggal_selesai is not None
            and self.tanggal_selesai < self.tanggal_mulai
        ):
            raise ValueError("tanggal_selesai tidak boleh sebelum tanggal_mulai.")
        return self


class AdminTahunAjaranItem(BaseModel):
    """Response item for an academic year."""

    id: str
    tahun: str
    status: str
    semester_ganjil: bool
    semester_genap: bool
    tanggal_mulai: date | None = None
    tanggal_selesai: date | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AdminMataKuliahWriteRequest(BaseModel):
    """Create/update payload for a course."""

    model_config = ConfigDict(populate_by_name=True)

    kode: str = Field(..., min_length=1, max_length=20)
    nama: str = Field(..., min_length=2, max_length=100)
    semester: int = Field(..., ge=1, le=8)
    sks: int = Field(..., ge=1, le=20)

    @field_validator("kode", mode="before")
    @classmethod
    def normalize_kode(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("kode mata kuliah wajib diisi.")
        return cleaned

    @field_validator("nama", mode="before")
    @classmethod
    def normalize_nama(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("nama mata kuliah wajib diisi.")
        return cleaned


class AdminMataKuliahItem(BaseModel):
    """Response item for a course."""

    kode: str
    nama: str
    semester: int
    sks: int
    created_at: str | None = None
    updated_at: str | None = None


class AdminDosenItem(BaseModel):
    """Response item for a lecturer option."""

    nip: str
    nama: str
    email: str


class AdminProgramStudiItem(BaseModel):
    """Response item for a study-program option."""

    kode: str
    nama: str


class AdminRuanganItem(BaseModel):
    """Response item for a room option."""

    kode: str
    nama: str


class AdminRuanganQrItem(BaseModel):
    """Response item for a room static door QR code."""

    kode: str
    nama: str
    qr_token: str
    qr_data: str
    format: str = "statis"
    title: str
    instruksi: str


class AdminRuanganQrListResponse(BaseModel):
    data: list[AdminRuanganQrItem]
    total: int


class AdminSesiKuliahItem(BaseModel):
    """Response item for a class time-slot option."""

    nomor: int
    jam_mulai: str | None = None
    jam_selesai: str | None = None


class AdminTahunAjaranListResponse(BaseModel):
    data: list[AdminTahunAjaranItem]
    total: int


class AdminMataKuliahListResponse(BaseModel):
    data: list[AdminMataKuliahItem]
    total: int


class AdminDosenListResponse(BaseModel):
    data: list[AdminDosenItem]
    total: int


class AdminProgramStudiListResponse(BaseModel):
    data: list[AdminProgramStudiItem]
    total: int


class AdminRuanganListResponse(BaseModel):
    data: list[AdminRuanganItem]
    total: int


class AdminSesiKuliahListResponse(BaseModel):
    data: list[AdminSesiKuliahItem]
    total: int


class AdminTahunAjaranMutationResponse(BaseModel):
    message: str
    data: AdminTahunAjaranItem


class AdminMataKuliahMutationResponse(BaseModel):
    message: str
    data: AdminMataKuliahItem
