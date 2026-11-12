"""Lecturer authentication, dashboard, roster attendance, and QR session routes."""

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_dosen, get_dosen_service
from app.schemas.dosen import (
    DosenDashboardResponse,
    DosenKehadiranListResponse,
    DosenLoginRequest,
    DosenLoginResponse,
    SesiPresensiQrResponse,
)
from app.services.dosen_service import DosenService

router = APIRouter(tags=["Dosen"])


@router.post("/auth/dosen/login", response_model=DosenLoginResponse, tags=["Authentication"])
def login_dosen(
    payload: DosenLoginRequest,
    dosen_service: DosenService = Depends(get_dosen_service),
) -> DosenLoginResponse:
    """Authenticate lecturer email and password and return a Bearer JWT token."""
    return dosen_service.login(payload)


@router.get("/dosen/dashboard", response_model=DosenDashboardResponse)
def get_dosen_dashboard(
    current_dosen: dict[str, Any] = Depends(get_current_dosen),
    dosen_service: DosenService = Depends(get_dosen_service),
) -> DosenDashboardResponse:
    """Return active classes, schedules, and attendance counts for the signed-in lecturer."""
    return dosen_service.get_dashboard(current_dosen)


@router.get("/dosen/jadwal/{jadwal_id}/kehadiran", response_model=DosenKehadiranListResponse)
def get_jadwal_kehadiran(
    jadwal_id: UUID,
    tanggal: date | None = Query(
        default=None,
        description="Tanggal sesi (YYYY-MM-DD). Kosong = sesi terakhir jadwal ini.",
    ),
    current_dosen: dict[str, Any] = Depends(get_current_dosen),
    dosen_service: DosenService = Depends(get_dosen_service),
) -> DosenKehadiranListResponse:
    """Return full student roster and attendance statuses for a lecturer session."""
    return dosen_service.get_jadwal_kehadiran(
        jadwal_id=str(jadwal_id),
        nip=str(current_dosen["nip"]),
        tanggal_iso=tanggal.isoformat() if tanggal is not None else None,
    )


@router.post("/dosen/jadwal/{jadwal_id}/sesi-presensi", response_model=SesiPresensiQrResponse)
def buka_sesi_presensi(
    jadwal_id: UUID,
    current_dosen: dict[str, Any] = Depends(get_current_dosen),
    dosen_service: DosenService = Depends(get_dosen_service),
) -> SesiPresensiQrResponse:
    """Open today's attendance session for this schedule and generate a dynamic QR code."""
    return dosen_service.open_sesi_presensi(
        jadwal_id=str(jadwal_id),
        nip=str(current_dosen["nip"]),
    )


@router.post("/dosen/sesi-presensi/{sesi_id}/qr", response_model=SesiPresensiQrResponse)
def perbarui_qr_sesensi(
    sesi_id: UUID,
    current_dosen: dict[str, Any] = Depends(get_current_dosen),
    dosen_service: DosenService = Depends(get_dosen_service),
) -> SesiPresensiQrResponse:
    """Rotate QR token for an active open session, immediately invalidating old codes."""
    return dosen_service.refresh_qr_sesensi(
        sesi_id=str(sesi_id),
        nip=str(current_dosen["nip"]),
    )


@router.post("/dosen/sesi-presensi/{sesi_id}/tutup", response_model=SesiPresensiQrResponse)
def tutup_sesi_presensi(
    sesi_id: UUID,
    current_dosen: dict[str, Any] = Depends(get_current_dosen),
    dosen_service: DosenService = Depends(get_dosen_service),
) -> SesiPresensiQrResponse:
    """Close an attendance session and clear its dynamic QR code."""
    return dosen_service.close_sesi_presensi(
        sesi_id=str(sesi_id),
        nip=str(current_dosen["nip"]),
    )
