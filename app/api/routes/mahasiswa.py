"""Student profile, schedule, reminder, attendance summary/history, and student CRUD routes."""

from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_auth_service,
    get_current_student,
    get_jadwal_service,
    get_mahasiswa_service,
    get_presensi_service,
)
from app.schemas.auth import ChangePasswordRequest, MessageResponse
from app.schemas.jadwal import JadwalListResponse, PengingatResponse
from app.schemas.mahasiswa import (
    MahasiswaCreateRequest,
    MahasiswaListResponse,
    MahasiswaMutationResponse,
    MahasiswaProfileResponse,
    MahasiswaUpdateMeRequest,
    MahasiswaUpdateRequest,
)
from app.schemas.presensi import PresensiHistoryResponse, PresensiSummaryResponse
from app.services import (
    AuthService,
    JadwalService,
    MahasiswaService,
    PresensiService,
)

router = APIRouter(prefix="/mahasiswa", tags=["Mahasiswa & Jadwal"])


@router.get("/me", response_model=MahasiswaProfileResponse)
def get_my_profile(
    current_student: dict[str, Any] = Depends(get_current_student),
    mahasiswa_service: MahasiswaService = Depends(get_mahasiswa_service),
) -> MahasiswaProfileResponse:
    """Return full profile details for the authenticated student."""
    return mahasiswa_service.get_profile(str(current_student["nim"]))


@router.put("/me", response_model=MahasiswaMutationResponse)
@router.patch("/me", response_model=MahasiswaMutationResponse)
def update_my_profile(
    payload: MahasiswaUpdateMeRequest,
    current_student: dict[str, Any] = Depends(get_current_student),
    mahasiswa_service: MahasiswaService = Depends(get_mahasiswa_service),
) -> MahasiswaMutationResponse:
    """Update editable account fields for the authenticated student."""
    return mahasiswa_service.update_profile(str(current_student["nim"]), payload)


@router.put("/me/password", response_model=MessageResponse)
def update_my_password(
    payload: ChangePasswordRequest,
    current_student: dict[str, Any] = Depends(get_current_student),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Change password for the authenticated student."""
    return auth_service.change_password(str(current_student["nim"]), payload)


@router.get("/jadwal", response_model=JadwalListResponse)
def get_my_jadwal(
    hari: str | None = Query(default=None, description="Filter hari: senin..sabtu"),
    day_of_week: int | None = Query(default=None, ge=1, le=7, description="Filter hari 1=Senin..7=Minggu"),
    current_student: dict[str, Any] = Depends(get_current_student),
    jadwal_service: JadwalService = Depends(get_jadwal_service),
) -> JadwalListResponse:
    """Return class schedules from `v_jadwal_lengkap` for the student's class."""
    return jadwal_service.get_student_jadwal(
        str(current_student["nim"]),
        hari=hari,
        day_of_week=day_of_week,
    )


@router.get("/pengingat", response_model=PengingatResponse)
def get_my_pengingat(
    current_student: dict[str, Any] = Depends(get_current_student),
    jadwal_service: JadwalService = Depends(get_jadwal_service),
) -> PengingatResponse:
    """Return the active or next upcoming scheduled course reminder for the student."""
    return jadwal_service.get_student_pengingat(str(current_student["nim"]))


@router.get("/presensi/summary", response_model=PresensiSummaryResponse)
def get_my_presensi_summary(
    current_student: dict[str, Any] = Depends(get_current_student),
    presensi_service: PresensiService = Depends(get_presensi_service),
) -> PresensiSummaryResponse:
    """Return attendance counters aggregated from `v_rekap_kehadiran`."""
    return presensi_service.get_summary(str(current_student["nim"]))


@router.get("/presensi/riwayat", response_model=PresensiHistoryResponse)
def get_my_presensi_riwayat(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int | None = Query(default=None, ge=1, le=200),
    current_student: dict[str, Any] = Depends(get_current_student),
    presensi_service: PresensiService = Depends(get_presensi_service),
) -> PresensiHistoryResponse:
    """Return detailed attendance history rows from `v_rekap_kehadiran`."""
    return presensi_service.get_history(
        nim=str(current_student["nim"]),
        status_filter=status_filter,
        limit=limit,
    )


@router.get("", response_model=MahasiswaListResponse)
def list_mahasiswa(
    kelas_id: str | None = Query(default=None),
    kelas: str | None = Query(default=None),
    search: str | None = Query(default=None),
    _: dict[str, Any] = Depends(get_current_student),
    mahasiswa_service: MahasiswaService = Depends(get_mahasiswa_service),
) -> MahasiswaListResponse:
    """List student records stored in Supabase."""
    return mahasiswa_service.list_students(
        kelas_id=kelas_id,
        kelas=kelas,
        search=search,
    )


@router.post(
    "",
    response_model=MahasiswaMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mahasiswa(
    payload: MahasiswaCreateRequest,
    _: dict[str, Any] = Depends(get_current_student),
    mahasiswa_service: MahasiswaService = Depends(get_mahasiswa_service),
) -> MahasiswaMutationResponse:
    """Create a student row in Supabase."""
    return mahasiswa_service.create_student(payload)


@router.get("/{nim}", response_model=MahasiswaProfileResponse)
def get_mahasiswa_by_nim(
    nim: str,
    _: dict[str, Any] = Depends(get_current_student),
    mahasiswa_service: MahasiswaService = Depends(get_mahasiswa_service),
) -> MahasiswaProfileResponse:
    """Fetch a student profile by NIM."""
    return mahasiswa_service.get_profile(nim)


@router.put("/{nim}", response_model=MahasiswaMutationResponse)
def update_mahasiswa_by_nim(
    nim: str,
    payload: MahasiswaUpdateRequest,
    _: dict[str, Any] = Depends(get_current_student),
    mahasiswa_service: MahasiswaService = Depends(get_mahasiswa_service),
) -> MahasiswaMutationResponse:
    """Update a student record by NIM."""
    return mahasiswa_service.update_profile(nim, payload)


@router.delete("/{nim}", response_model=MessageResponse)
def delete_mahasiswa_by_nim(
    nim: str,
    _: dict[str, Any] = Depends(get_current_student),
    mahasiswa_service: MahasiswaService = Depends(get_mahasiswa_service),
) -> MessageResponse:
    """Delete a student record by NIM."""
    return mahasiswa_service.delete_student(nim)

