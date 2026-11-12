"""Shared normalization, timezone, and geometry helpers for service modules."""

from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any

WIB = timezone(timedelta(hours=7))

HARI_ORDER: dict[str, int] = {
    "senin": 0,
    "selasa": 1,
    "rabu": 2,
    "kamis": 3,
    "jumat": 4,
    "sabtu": 5,
    "minggu": 6,
}

HARI_TO_ISO_DAY: dict[str, int] = {name: index + 1 for name, index in HARI_ORDER.items()}
WEEKDAY_TO_HARI: dict[int, str] = {index: name for name, index in HARI_ORDER.items()}
ISO_DAY_TO_HARI: dict[int, str] = {index + 1: name for name, index in HARI_ORDER.items()}

STATUS_LABELS: dict[str, str] = {
    "hadir": "Hadir",
    "izin": "Izin",
    "sakit": "Sakit",
    "alfa": "Alfa",
}


def now_wib() -> datetime:
    """Return current datetime localized to WIB (UTC+7)."""
    return datetime.now(WIB)


def format_hhmm(time_value: str | None) -> str:
    """Format `HH:MM:SS` database time values into `HH:MM` display strings."""
    if not time_value:
        return "--:--"
    parts = str(time_value).split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return str(time_value)


def format_time_range(start: str | None, end: str | None) -> str:
    """Build a display time window string like `07:50 - 09:30`."""
    if not start and not end:
        return "-"
    return f"{format_hhmm(start)} - {format_hhmm(end)}"


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two WGS84 coordinates."""
    earth_radius_m = 6371000.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    c = 2 * asin(min(1.0, sqrt(a)))
    return round(earth_radius_m * c, 2)


def build_student_profile_dict(
    row: dict[str, Any],
    face_sample_count: int = 0,
) -> dict[str, Any]:
    """Normalize a `mahasiswa` row (joined with `kelas`) for API & mobile responses."""
    kelas_data = row.get("kelas") or {}
    if isinstance(kelas_data, list):
        kelas_data = kelas_data[0] if kelas_data else {}

    prodi_data = kelas_data.get("program_studi") or {}
    if isinstance(prodi_data, list):
        prodi_data = prodi_data[0] if prodi_data else {}

    nama = row.get("nama_lengkap") or ""
    email = row.get("email")
    no_hp = row.get("no_hp")
    kelas_nama = kelas_data.get("nama")
    prodi_kode = kelas_data.get("program_studi_kode") or prodi_data.get("kode")
    prodi_nama = prodi_data.get("nama") or prodi_kode

    return {
        "nim": row["nim"],
        "name": nama,
        "nama_lengkap": nama,
        "fullName": nama,
        "email": email,
        "no_hp": no_hp,
        "phoneNumber": no_hp,
        "kelas_id": row.get("kelas_id") or kelas_data.get("id"),
        "kelas": kelas_nama,
        "className": kelas_nama,
        "tingkat": kelas_data.get("tingkat"),
        "prodi_kode": prodi_kode,
        "prodi": prodi_nama,
        "role": "Mahasiswa",
        "has_face_registered": face_sample_count > 0,
        "face_sample_count": face_sample_count,
    }

