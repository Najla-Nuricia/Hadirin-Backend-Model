"""Pydantic schemas for student class schedules and dynamic lecture reminders."""

from pydantic import BaseModel


class JadwalItem(BaseModel):
    """Normalized class schedule entry derived from `v_jadwal_lengkap`."""

    id: str
    hari: str
    day_of_week: int
    semester: str
    tahun_ajaran: str
    matkul_kode: str
    matkul_nama: str
    courseName: str
    course_name: str
    sks: int
    dosen_nip: str | None = None
    dosen_nama: str | None = None
    lecturer_name: str | None = None
    prodi_kode: str | None = None
    prodi_nama: str | None = None
    kelas_nama: str
    kelas_tingkat: int | None = None
    ruangan_kode: str | None = None
    ruangan_nama: str | None = None
    room: str | None = None
    jam_mulai: str
    jam_selesai: str
    start_time: str
    end_time: str
    time: str
    sesi_mulai: int | None = None
    sesi_selesai: int | None = None
    has_alarm: bool = False
    is_session_open: bool = False
    active_sesi_id: str | None = None


class JadwalListResponse(BaseModel):
    """Schedule list response for a student's class."""

    data: list[JadwalItem]
    total: int
    kelas: str | None = None


class PengingatItem(BaseModel):
    """Upcoming/ongoing lecture reminder computed dynamically from DB schedules."""

    jadwal_id: str
    matkul_kode: str
    matkul_nama: str
    courseName: str
    hari: str
    day_of_week: int
    jam_mulai: str
    jam_selesai: str
    time: str
    ruangan_kode: str | None = None
    ruangan_nama: str | None = None
    room: str | None = None
    dosen_nama: str | None = None
    kelas_nama: str
    is_today: bool = False
    is_session_open: bool = False
    sesi_presensi_id: str | None = None
    status_label: str = "Jadwal Berikutnya"
    message: str | None = None


class PengingatResponse(BaseModel):
    """Reminder wrapper returned on `/mahasiswa/pengingat`."""

    data: PengingatItem | None = None
    message: str | None = None

