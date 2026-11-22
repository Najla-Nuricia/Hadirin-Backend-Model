"""Admin-only routes for managing course schedules (`jadwal_kuliah`)."""

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_admin_jadwal_service, get_current_admin
from app.schemas.admin_jadwal import (
    AdminJadwalListResponse,
    AdminJadwalMutationResponse,
    AdminJadwalWriteRequest,
)
from app.services.admin_jadwal_service import AdminJadwalService

router = APIRouter(prefix="/admin/jadwal", tags=["Admin Jadwal"])


@router.get(
    "",
    response_model=AdminJadwalListResponse,
    summary="Lihat daftar jadwal (admin)",
    description=(
        "Mengambil seluruh jadwal kuliah dengan filter opsional: **tahun ajaran** "
        "('2026/2027' atau UUID), **semester** (ganjil/genap), **tingkat** kelas (1-8), "
        "dan **kelas** (nama atau UUID). Wajib Bearer token admin.\n\n"
        "Contoh: `GET /admin/jadwal?tahun_ajaran=2026/2027&semester=ganjil&tingkat=1&kelas=TI-1A`"
    ),
    responses={
        200: {"description": "Daftar jadwal beserta jumlah dan filter yang dipakai."},
        401: {"description": "Bearer token admin tidak ada atau tidak valid."},
        403: {"description": "Token bukan token admin."},
    },
)
def list_admin_jadwal(
    tahun_ajaran: str | None = Query(
        default=None,
        description="Tahun ajaran ('2026/2027') atau UUID tahun ajaran.",
        examples=["2026/2027"],
    ),
    semester: Literal["ganjil", "genap"] | None = Query(
        default=None,
        description="Periode semester.",
        examples=["ganjil"],
    ),
    tingkat: int | None = Query(
        default=None,
        ge=1,
        le=8,
        description="Tingkat kelas (1-8).",
        examples=[1],
    ),
    kelas: str | None = Query(
        default=None,
        description="Nama kelas ('TI-3A') atau UUID kelas.",
        examples=["TI-1A"],
    ),
    current_admin: dict[str, Any] = Depends(get_current_admin),
    jadwal_service: AdminJadwalService = Depends(get_admin_jadwal_service),
) -> AdminJadwalListResponse:
    """List schedules with optional academic year, semester, level, and class filters."""
    return jadwal_service.list_jadwal(
        tahun_ajaran=tahun_ajaran,
        semester=semester,
        tingkat=tingkat,
        kelas=kelas,
    )


@router.post(
    "",
    response_model=AdminJadwalMutationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tambah jadwal (admin)",
    description=(
        "Membuat jadwal baru di `jadwal_kuliah`. Semua relasi (tahun ajaran, kelas, "
        "mata kuliah, dosen, ruangan, sesi) divalidasi, lalu konflik jadwal diperiksa "
        "untuk kelas, dosen, dan ruangan pada hari & sesi yang bertabrakan. "
        "Wajib Bearer token admin.\n\n"
        "Contoh request body:\n"
        '```json\n{"tahun_ajaran": "2026/2027", "kelas": "TI-1A", "mata_kuliah_kode": "TI101", '
        '"dosen_nip": "197905052005011005", "ruangan_kode": "J302", "hari": "sabtu", '
        '"sesi_mulai": 1, "sesi_selesai": 2, "semester": "ganjil"}\n```'
    ),
    responses={
        201: {"description": "Jadwal berhasil dibuat."},
        400: {"description": "Relasi data atau konsistensi semester tidak valid."},
        409: {"description": "Jadwal bertabrakan dengan jadwal lain."},
        401: {"description": "Bearer token admin tidak ada atau tidak valid."},
        403: {"description": "Token bukan token admin."},
    },
)
def create_admin_jadwal(
    payload: AdminJadwalWriteRequest,
    current_admin: dict[str, Any] = Depends(get_current_admin),
    jadwal_service: AdminJadwalService = Depends(get_admin_jadwal_service),
) -> AdminJadwalMutationResponse:
    """Create a new schedule after validating relations and checking conflicts."""
    return jadwal_service.create_jadwal(payload)


@router.put(
    "/{jadwal_id}",
    response_model=AdminJadwalMutationResponse,
    summary="Edit jadwal (admin)",
    description=(
        "Memperbarui seluruh data jadwal berdasarkan UUID. Relasi dan konflik "
        "divalidasi ulang dengan mengecualikan jadwal yang sedang diubah. "
        "Wajib Bearer token admin."
    ),
    responses={
        200: {"description": "Jadwal berhasil diperbarui."},
        400: {"description": "Relasi data atau konsistensi semester tidak valid."},
        404: {"description": "Jadwal tidak ditemukan."},
        409: {"description": "Jadwal bertabrakan dengan jadwal lain."},
        401: {"description": "Bearer token admin tidak ada atau tidak valid."},
        403: {"description": "Token bukan token admin."},
    },
)
def update_admin_jadwal(
    jadwal_id: UUID,
    payload: AdminJadwalWriteRequest,
    current_admin: dict[str, Any] = Depends(get_current_admin),
    jadwal_service: AdminJadwalService = Depends(get_admin_jadwal_service),
) -> AdminJadwalMutationResponse:
    """Replace an existing schedule after validating relations and conflicts."""
    return jadwal_service.update_jadwal(str(jadwal_id), payload)
