"""Pydantic schemas for lecturer authentication, dashboard, attendance list, and QR sessions."""

from pydantic import BaseModel, Field, field_validator


class DosenLoginRequest(BaseModel):
    """Credentials payload for lecturer sign-in."""

    email: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class DosenProfileResponse(BaseModel):
    """Normalized lecturer profile compatible with mobile and QA clients."""

    nip: str
    staffId: str
    fullName: str
    email: str
    phoneNumber: str = ""
    role: str = "Dosen"


class DosenLoginResponse(DosenProfileResponse):
    """Lecturer authentication response issuing a Bearer JWT access token."""

    token: str
    access_token: str
    token_type: str = "bearer"


class AttendanceCountsSummary(BaseModel):
    """Aggregated attendance counts per schedule, class, session, or dashboard."""

    hadir: int = 0
    izin: int = 0
    sakit: int = 0
    alfa: int = 0
    total: int = 0
    persentase_kehadiran: int = 0


class DosenJadwalSummaryItem(BaseModel):
    """Single course schedule item enriched with session counts and attendance stats."""

    jadwal_id: str
    course_code: str | None = None
    course_name: str | None = None
    sks: int | None = None
    kelas_id: str
    kelas: str | None = None
    prodi: str | None = None
    hari: str
    day_of_week: int | None = None
    start_time: str = ""
    end_time: str = ""
    room: str | None = None
    semester: str | int | None = None
    hari_ini: bool = False
    jumlah_mahasiswa: int = 0
    jumlah_sesi: int = 0
    sesi_terakhir: str | None = None
    sesi_aktif_id: str | None = None
    ringkasan_kehadiran: AttendanceCountsSummary


class DosenKelasSummaryItem(BaseModel):
    """Class-level attendance aggregation on the lecturer dashboard."""

    kelas_id: str
    kelas: str | None = None
    prodi: str | None = None
    jumlah_mahasiswa: int = 0
    jumlah_jadwal: int = 0
    jumlah_sesi: int = 0
    ringkasan_kehadiran: AttendanceCountsSummary


class DosenDashboardResponse(BaseModel):
    """Lecturer dashboard response with active semester classes, schedules, and stats."""

    dosen: DosenProfileResponse
    tanggal: str
    hari: str | None = None
    total_kelas: int = 0
    total_jadwal: int = 0
    total_mahasiswa: int = 0
    ringkasan_kehadiran: AttendanceCountsSummary
    kelas: list[DosenKelasSummaryItem]
    jadwal: list[DosenJadwalSummaryItem]


class DosenStudentDocument(BaseModel):
    """Attached permission document metadata shown in lecturer attendance lists."""

    fileName: str
    path: str


class DosenStudentAttendanceItem(BaseModel):
    """Single student attendance row in a lecturer's course session."""

    nim: str
    name: str
    className: str | None = None
    status: str = "alfa"
    checkInTime: str | None = None
    note: str | None = None
    document: DosenStudentDocument | None = None
    pengajuan_status: str | None = None


class DosenKehadiranListResponse(BaseModel):
    """Full attendance roster for a specific lecturer course session."""

    jadwal_id: str
    sesi_presensi_id: str
    courseName: str | None = None
    className: str | None = None
    date: str
    is_open: bool
    summary: AttendanceCountsSummary
    students: list[DosenStudentAttendanceItem]


class SesiPresensiQrResponse(BaseModel):
    """Dynamic QR session state returned when opening, refreshing, or closing a session."""

    sesi_presensi_id: str
    jadwal_id: str
    tanggal: str
    course_name: str | None = None
    kelas: str | None = None
    is_open: bool
    qr_code: str | None = None
    qr_expires_at: str | None = None
    qr_ttl_seconds: int
