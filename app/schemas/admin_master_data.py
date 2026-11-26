"""Schemas for admin academic master-data CRUD."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TahunAjaranStatus = Literal["aktif", "non_aktif"]
KelasStatus = Literal["aktif", "non_aktif"]


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
    """Response item for a lecturer (admin option list and CRUD)."""

    nip: str
    nama: str
    email: str | None = None
    no_hp: str | None = None
    auth_user_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AdminProgramStudiItem(BaseModel):
    """Response item for a study-program option."""

    kode: str
    nama: str


class AdminRuanganItem(BaseModel):
    """Response item for a room (admin option list and CRUD)."""

    kode: str
    nama: str
    created_at: str | None = None
    updated_at: str | None = None


class AdminRuanganWriteRequest(BaseModel):
    """Create/update payload for a room."""

    model_config = ConfigDict(populate_by_name=True)

    kode: str = Field(..., min_length=1, max_length=20, json_schema_extra={"example": "J301"})
    nama: str = Field(..., min_length=2, max_length=100, json_schema_extra={"example": "Ruang J301"})

    @field_validator("kode", mode="before")
    @classmethod
    def normalize_kode(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("kode ruangan wajib diisi.")
        return cleaned

    @field_validator("nama", mode="before")
    @classmethod
    def normalize_nama(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("nama ruangan wajib diisi.")
        return cleaned


class AdminDosenWriteRequest(BaseModel):
    """Create/update payload for a lecturer."""

    model_config = ConfigDict(populate_by_name=True)

    nip: str = Field(
        ..., min_length=3, max_length=30, json_schema_extra={"example": "198501012010121001"}
    )
    nama: str = Field(..., min_length=2, max_length=100, json_schema_extra={"example": "Budi Santoso"})
    email: str | None = Field(default=None, max_length=150, json_schema_extra={"example": "budi@polinema.ac.id"})
    no_hp: str | None = Field(default=None, max_length=20, json_schema_extra={"example": "081234567890"})

    @field_validator("nip", mode="before")
    @classmethod
    def normalize_nip(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("NIP dosen wajib diisi.")
        return cleaned

    @field_validator("nama", mode="before")
    @classmethod
    def normalize_nama(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("nama dosen wajib diisi.")
        return cleaned

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        cleaned = value.strip().lower()
        if not cleaned:
            return None
        if cleaned.count("@") != 1 or cleaned.startswith("@") or cleaned.endswith("@"):
            raise ValueError("Email dosen tidak valid.")
        return cleaned

    @field_validator("no_hp", mode="before")
    @classmethod
    def normalize_no_hp(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        cleaned = " ".join(value.strip().split())
        return cleaned or None


class AdminKelasItem(BaseModel):
    """Response item for a class."""

    id: str
    nama: str
    tingkat: int
    program_studi_kode: str
    tahun_ajaran_id: str
    kapasitas: int
    status: str
    program_studi_nama: str | None = None
    tahun_ajaran_tahun: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AdminKelasWriteRequest(BaseModel):
    """Create/update payload for a class."""

    model_config = ConfigDict(populate_by_name=True)

    nama: str = Field(..., min_length=1, max_length=20, json_schema_extra={"example": "TI-1A"})
    tingkat: int = Field(..., ge=1, le=8, json_schema_extra={"example": 1})
    program_studi_kode: str = Field(
        ..., min_length=1, max_length=20, json_schema_extra={"example": "D4-TI"}
    )
    tahun_ajaran_id: UUID = Field(..., json_schema_extra={"example": "6c1f0b7e-1a2b-4c3d-9e8f-1234567890ab"})
    kapasitas: int = Field(default=30, ge=1, le=200, json_schema_extra={"example": 30})
    status: KelasStatus = "aktif"

    @field_validator("nama", mode="before")
    @classmethod
    def normalize_nama(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = " ".join(value.strip().split()).upper()
        if not cleaned:
            raise ValueError("nama kelas wajib diisi.")
        return cleaned

    @field_validator("program_studi_kode", mode="before")
    @classmethod
    def normalize_prodi(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("program studi kelas wajib diisi.")
        return cleaned

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
            return "non_aktif" if normalized == "nonaktif" else normalized
        return value

    @field_validator("tahun_ajaran_id", mode="before")
    @classmethod
    def normalize_tahun_ajaran_id(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("tahun ajaran wajib dipilih.")
            return cleaned
        return value


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


class AdminKelasListResponse(BaseModel):
    data: list[AdminKelasItem]
    total: int


class AdminTahunAjaranMutationResponse(BaseModel):
    message: str
    data: AdminTahunAjaranItem


class AdminMataKuliahMutationResponse(BaseModel):
    message: str
    data: AdminMataKuliahItem


class AdminRuanganMutationResponse(BaseModel):
    message: str
    data: AdminRuanganItem


class AdminDosenMutationResponse(BaseModel):
    message: str
    data: AdminDosenItem
    initial_password: str | None = Field(
        default=None,
        description="Password awal akun dosen (hanya dikembalikan saat pembuatan akun).",
    )


class AdminKelasMutationResponse(BaseModel):
    message: str
    data: AdminKelasItem

