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
    DosenMatkulListResponse,
    DosenTestingToggleRequest,
    DosenTestingToggleResponse,
)
from app.services.dosen_service import DosenService
from app.services.testing_toggles import testing_toggles

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


@router.get("/dosen/matkul", response_model=DosenMatkulListResponse)
def list_dosen_matkul(
    kelas_id: UUID = Query(..., description="ID kelas yang dipilih dosen."),
    tanggal: date = Query(
        ...,
        description="Tanggal pilihan (YYYY-MM-DD). Dikonversi ke hari jadwal (Senin-Jumat).",
    ),
    current_dosen: dict[str, Any] = Depends(get_current_dosen),
    dosen_service: DosenService = Depends(get_dosen_service),
) -> DosenMatkulListResponse:
    """Return matkul options limited to this lecturer's schedule for the class and date."""
    return dosen_service.list_matkul_options(
        nip=str(current_dosen["nip"]),
        kelas_id=str(kelas_id),
        tanggal_iso=tanggal.isoformat(),
    )


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


@router.get("/dosen/testing/lokasi-bypass", response_model=DosenTestingToggleResponse)
def get_location_bypass(
    current_dosen: dict[str, Any] = Depends(get_current_dosen),
) -> DosenTestingToggleResponse:
    """Return this lecturer's location-bypass toggle for testing."""
    nip = str(current_dosen["nip"])
    return DosenTestingToggleResponse(
        dosen_nip=nip,
        location_bypass=testing_toggles.is_location_bypass_enabled(nip),
    )


@router.put("/dosen/testing/lokasi-bypass", response_model=DosenTestingToggleResponse)
def set_location_bypass(
    payload: DosenTestingToggleRequest,
    current_dosen: dict[str, Any] = Depends(get_current_dosen),
) -> DosenTestingToggleResponse:
    """Enable/disable this lecturer's location-bypass toggle for testing."""
    nip = str(current_dosen["nip"])
    testing_toggles.set_location_bypass(nip, payload.enabled)
    return DosenTestingToggleResponse(
        dosen_nip=nip,
        location_bypass=testing_toggles.is_location_bypass_enabled(nip),
    )
