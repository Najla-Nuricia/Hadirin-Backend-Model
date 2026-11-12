"""Attendance check-in (QR + GPS, Face Recognition + Storage) and history routes."""

from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from app.api.deps import get_current_student, get_presensi_service
from app.api.helpers import collect_uploaded_files, parse_json_body
from app.core.exceptions import BadRequestError
from app.schemas.presensi import (
    ActiveSessionListResponse,
    AttendanceRecordResponse,
    FaceAttendanceRequest,
    GpsAttendanceRequest,
    PresensiHistoryResponse,
    QrAttendanceRequest,
)
from app.services import PresensiService
from app.services.face_recognition.face_service import FaceService

router = APIRouter(prefix="/attendance", tags=["Presensi & Kehadiran"])


@router.get("/sesi-aktif", response_model=ActiveSessionListResponse)
def list_active_sessions(
    current_student: dict[str, Any] = Depends(get_current_student),
    presensi_service: PresensiService = Depends(get_presensi_service),
) -> ActiveSessionListResponse:
    """Return open `sesi_presensi` sessions available for the student's class."""
    return presensi_service.list_active_sessions(str(current_student["nim"]))


@router.get("/history", response_model=PresensiHistoryResponse)
def get_attendance_history(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int | None = Query(default=None, ge=1, le=200),
    current_student: dict[str, Any] = Depends(get_current_student),
    presensi_service: PresensiService = Depends(get_presensi_service),
) -> PresensiHistoryResponse:
    """Return the authenticated student's attendance history from `v_rekap_kehadiran`."""
    return presensi_service.get_history(
        nim=str(current_student["nim"]),
        status_filter=status_filter,
        limit=limit,
    )


@router.post("/gps", response_model=AttendanceRecordResponse)
def record_gps_attendance(
    payload: GpsAttendanceRequest,
    current_student: dict[str, Any] = Depends(get_current_student),
    presensi_service: PresensiService = Depends(get_presensi_service),
) -> AttendanceRecordResponse:
    """Validate GPS coordinates & accuracy against campus geofence and record attendance."""
    return presensi_service.submit_gps_attendance(str(current_student["nim"]), payload)


@router.post("/qr", response_model=AttendanceRecordResponse)
def record_qr_attendance(
    payload: QrAttendanceRequest,
    current_student: dict[str, Any] = Depends(get_current_student),
    presensi_service: PresensiService = Depends(get_presensi_service),
) -> AttendanceRecordResponse:
    """Validate an open QR session token + campus GPS geofence and record attendance."""
    return presensi_service.submit_qr_attendance(str(current_student["nim"]), payload)


@router.post("/face", response_model=AttendanceRecordResponse)
async def record_face_attendance(
    request: Request,
    file: UploadFile | None = File(default=None),
    current_student: dict[str, Any] = Depends(get_current_student),
    presensi_service: PresensiService = Depends(get_presensi_service),
) -> AttendanceRecordResponse:
    """Verify student face photo via MobileFaceNet and record attendance in `kehadiran`."""
    nim = str(current_student["nim"])
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        raw = await parse_json_body(request)
        payload = FaceAttendanceRequest.model_validate(raw)
        img_bytes, _, img_mime = FaceService.decode_base64_sample(payload.image_base64)
        return presensi_service.submit_face_attendance(
            nim=nim,
            image_bytes=img_bytes,
            content_type=img_mime,
            sesi_presensi_id=payload.sesi_presensi_id,
            qr_token=payload.qr_token,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy=payload.accuracy,
            catatan=payload.catatan,
        )

    uploads = await collect_uploaded_files(request=request, bound_single=file)
    if not uploads:
        raise BadRequestError("Unggah foto wajah untuk melakukan presensi.")
    chosen = uploads[0]
    img_bytes = await chosen.read()
    form = await request.form()

    latitude = _parse_optional_float(form.get("latitude"), "latitude")
    longitude = _parse_optional_float(form.get("longitude"), "longitude")
    accuracy = _parse_optional_float(form.get("accuracy"), "accuracy")

    return presensi_service.submit_face_attendance(
        nim=nim,
        image_bytes=img_bytes,
        content_type=chosen.content_type or "image/jpeg",
        sesi_presensi_id=str(form.get("sesi_presensi_id")) if form.get("sesi_presensi_id") else None,
        qr_token=str(form.get("qr_token")) if form.get("qr_token") else None,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        catatan=str(form.get("catatan")) if form.get("catatan") else None,
    )


def _parse_optional_float(raw: object, field_name: str) -> float | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(str(raw))
    except ValueError as exc:
        raise BadRequestError(f"Field `{field_name}` harus berupa angka.") from exc

