"""Pydantic schemas for attendance submission, summary, and history."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class PresensiSummaryResponse(BaseModel):
    """Aggregated attendance counters calculated from `v_rekap_kehadiran`."""

    nim: str
    nama_lengkap: str | None = None
    total_pertemuan: int = 0
    hadir: int = 0
    izin: int = 0
    sakit: int = 0
    alfa: int = 0
    persentase_kehadiran: float = 0.0


class PresensiHistoryItem(BaseModel):
    """Normalized attendance history entry."""

    kehadiran_id: str
    sesi_presensi_id: str
    jadwal_id: str | None = None
    tanggal: str
    date: str
    matkul_nama: str
    courseName: str
    kelas_nama: str | None = None
    dosen_nama: str | None = None
    nim: str
    nama_mahasiswa: str | None = None
    status: str
    status_label: str
    jam_masuk: str | None = None
    time: str
    catatan: str | None = None
    status_pengajuan: str | None = None
    jenis_pengajuan: str | None = None
    face_photo_path: str | None = None
    face_photo_url: str | None = None


class PresensiHistoryResponse(BaseModel):
    """Attendance history list response."""

    data: list[PresensiHistoryItem]
    total: int


class ActiveSessionItem(BaseModel):
    """Open attendance session currently accepting check-ins for the student's class."""

    sesi_presensi_id: str
    jadwal_id: str
    tanggal: str
    matkul_nama: str
    kelas_nama: str
    ruangan_nama: str | None = None
    jam_mulai: str | None = None
    jam_selesai: str | None = None
    is_open: bool = True
    qr_expires_at: str | None = None


class ActiveSessionListResponse(BaseModel):
    """List of open attendance sessions for the student."""

    data: list[ActiveSessionItem]
    total: int


class GpsAttendanceRequest(BaseModel):
    """Payload to validate GPS geofence and optionally record attendance in an open session."""

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy: float | None = Field(default=None, ge=0.0)
    sesi_presensi_id: str | None = None
    catatan: str | None = Field(default=None, max_length=255)


class QrAttendanceRequest(BaseModel):
    """Payload to record attendance via dynamic QR token (`qr_token` or `code`) and optional GPS."""

    model_config = ConfigDict(populate_by_name=True)

    qr_token: str = Field(
        ...,
        min_length=1,
        max_length=128,
        validation_alias=AliasChoices("qr_token", "code"),
    )
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    accuracy: float | None = Field(default=None, ge=0.0)
    catatan: str | None = Field(default=None, max_length=255)


class FaceAttendanceRequest(BaseModel):
    """JSON payload variant for face-verified attendance check-in."""

    image_base64: str = Field(..., min_length=16)
    sesi_presensi_id: str | None = None
    qr_token: str | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    accuracy: float | None = Field(default=None, ge=0.0)
    catatan: str | None = Field(default=None, max_length=255)


class AttendanceRecordResponse(BaseModel):
    """Response after recording student attendance."""

    method: str | None = None
    nim: str | None = None
    status: str
    message: str
    kehadiran_id: str | None = None
    sesi_presensi_id: str | None = None
    jadwal_id: str | None = None
    tanggal: str
    date: str | None = None
    time: str | None = None
    jam_masuk: str | None = None
    matkul_nama: str | None = None
    courseName: str | None = None
    kelas: str | None = None
    distance_meters: float | None = None
    jarak_meter: float | None = None
    area: str | None = None
    radius_meters: float | None = None
    similarity: float | None = None
    threshold: float | None = None
    face_photo_path: str | None = None
    face_photo_url: str | None = None

