"""Pydantic schema exports."""

from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserSummary,
)
from app.schemas.jadwal import JadwalItem, JadwalListResponse, PengingatItem, PengingatResponse
from app.schemas.mahasiswa import (
    MahasiswaCreateRequest,
    MahasiswaListResponse,
    MahasiswaMutationResponse,
    MahasiswaProfileResponse,
    MahasiswaUpdateMeRequest,
    MahasiswaUpdateRequest,
)
from app.schemas.pengajuan import (
    DocumentUploadResponse,
    PengajuanCreateRequest,
    PengajuanItem,
    PengajuanListResponse,
    PengajuanMutationResponse,
    PengajuanUpdateRequest,
)
from app.schemas.presensi import (
    ActiveSessionItem,
    ActiveSessionListResponse,
    AttendanceRecordResponse,
    FaceAttendanceRequest,
    PresensiHistoryItem,
    PresensiHistoryResponse,
    PresensiSummaryResponse,
    QrAttendanceRequest,
)
from app.schemas.wajah import (
    FaceBase64Payload,
    FaceRegistrationResponse,
    FaceStatusResponse,
    FaceVerifyResponse,
)

__all__ = [
    "ActiveSessionItem",
    "ActiveSessionListResponse",
    "AttendanceRecordResponse",
    "ChangePasswordRequest",
    "DocumentUploadResponse",
    "FaceAttendanceRequest",
    "FaceBase64Payload",
    "FaceRegistrationResponse",
    "FaceStatusResponse",
    "FaceVerifyResponse",
    "JadwalItem",
    "JadwalListResponse",
    "LoginRequest",
    "MahasiswaCreateRequest",
    "MahasiswaListResponse",
    "MahasiswaMutationResponse",
    "MahasiswaProfileResponse",
    "MahasiswaUpdateMeRequest",
    "MahasiswaUpdateRequest",
    "MessageResponse",
    "PengajuanCreateRequest",
    "PengajuanItem",
    "PengajuanListResponse",
    "PengajuanMutationResponse",
    "PengajuanUpdateRequest",
    "PengingatItem",
    "PengingatResponse",
    "PresensiHistoryItem",
    "PresensiHistoryResponse",
    "PresensiSummaryResponse",
    "QrAttendanceRequest",
    "RegisterRequest",
    "RegisterResponse",
    "TokenResponse",
    "UserSummary",
]

