"""Pydantic schemas for student absence permission (`surat izin` / `sakit`)."""

from typing import Literal

from pydantic import BaseModel, Field


class PengajuanCreateRequest(BaseModel):
    """JSON request payload to submit an absence or compensation request."""

    jenis: Literal["izin", "sakit", "kompensasi"]
    alasan: str = Field(..., min_length=3, max_length=500)
    matakuliah: str | None = Field(default=None, max_length=150)
    tanggal: str | None = Field(default=None, max_length=32)
    sesi_presensi_id: str | None = None
    jadwal_id: str | None = None
    dokumen_path: str | None = Field(default=None, max_length=255)


class PengajuanUpdateRequest(BaseModel):
    """Payload to edit a pending absence request."""

    jenis: Literal["izin", "sakit", "kompensasi"] | None = None
    alasan: str | None = Field(default=None, min_length=3, max_length=500)
    dokumen_path: str | None = Field(default=None, max_length=255)


class PengajuanItem(BaseModel):
    """Normalized absence request item backed by `pengajuan_ketidakhadiran`."""

    id: str
    kehadiran_id: str
    sesi_presensi_id: str | None = None
    jadwal_id: str | None = None
    nim: str
    jenis: str
    alasan: str
    matakuliah: str | None = None
    tanggal: str | None = None
    dokumen_path: str | None = None
    dokumen_url: str | None = None
    status_pengajuan: str
    catatan_dosen: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PengajuanMutationResponse(BaseModel):
    """Response for create/update absence request endpoints."""

    message: str
    data: PengajuanItem


class PengajuanListResponse(BaseModel):
    """List wrapper for student's absence requests."""

    data: list[PengajuanItem]
    total: int


class DocumentUploadResponse(BaseModel):
    """Response when uploading an absence supporting file to Storage."""

    message: str
    dokumen_path: str
    dokumen_url: str | None = None
    content_type: str
    size_bytes: int

