"""Pydantic schemas for admin course-schedule management."""

from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

HariKuliah = Literal["senin", "selasa", "rabu", "kamis", "jumat", "sabtu"]
SemesterPeriode = Literal["ganjil", "genap"]


class AdminJadwalWriteRequest(BaseModel):
    """Full schedule payload used by both create and update admin endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    tahun_ajaran: str = Field(
        ...,
        min_length=4,
        max_length=40,
        description="Tahun ajaran ('2026/2027') atau UUID tahun ajaran.",
        validation_alias=AliasChoices("tahun_ajaran", "tahunAjaran", "tahun_ajaran_id"),
    )
    kelas: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Nama kelas ('TI-3A') atau UUID kelas.",
        validation_alias=AliasChoices("kelas", "nama_kelas", "kelas_id", "kelasId"),
    )
    mata_kuliah_kode: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Kode mata kuliah, mis. TI501.",
        validation_alias=AliasChoices("mata_kuliah_kode", "matkul_kode", "kode_mata_kuliah"),
    )
    dosen_nip: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="NIP dosen pengampu.",
        validation_alias=AliasChoices("dosen_nip", "nip"),
    )
    ruangan_kode: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Kode ruangan, mis. J301.",
        validation_alias=AliasChoices("ruangan_kode", "kode_ruangan", "ruang"),
    )
    hari: HariKuliah
    semester: SemesterPeriode
    sesi_mulai: int = Field(..., ge=1, le=12, description="Nomor sesi mulai (1-12).")
    sesi_selesai: int = Field(..., ge=1, le=12, description="Nomor sesi selesai (1-12).")

    @field_validator(
        "tahun_ajaran", "kelas", "mata_kuliah_kode", "dosen_nip", "ruangan_kode", "hari", "semester",
        mode="before",
    )
    @classmethod
    def _normalize_text(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _validate_sesi_range(self) -> "AdminJadwalWriteRequest":
        if self.sesi_mulai > self.sesi_selesai:
            raise ValueError("sesi_mulai tidak boleh lebih besar dari sesi_selesai.")
        return self


class AdminJadwalItem(BaseModel):
    """Normalized `jadwal_kuliah` row returned by admin schedule endpoints."""

    id: str
    tahun_ajaran_id: str
    tahun_ajaran: str
    semester: str
    hari: str
    sesi_mulai: int
    sesi_selesai: int
    jam_mulai: str | None = None
    jam_selesai: str | None = None
    mata_kuliah_kode: str
    matkul_nama: str
    sks: int
    dosen_nip: str
    dosen_nama: str
    program_studi_kode: str
    prodi_nama: str
    kelas_id: str
    kelas_nama: str
    kelas_tingkat: int
    ruangan_kode: str
    ruangan_nama: str


class AdminJadwalFilter(BaseModel):
    """Echo of filters applied to the admin schedule list."""

    tahun_ajaran: str | None = None
    semester: str | None = None
    tingkat: int | None = None
    kelas: str | None = None


class AdminJadwalListResponse(BaseModel):
    """Schedule list for admin with total count and applied filters."""

    data: list[AdminJadwalItem]
    total: int
    filters: AdminJadwalFilter


class AdminJadwalMutationResponse(BaseModel):
    """Create/update response carrying the affected schedule."""

    message: str
    data: AdminJadwalItem
