"""Integration tests for GPS geofence validation and dynamic QR attendance backed by DB."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.repositories import JadwalRepository, KehadiranRepository
from app.db.session import get_supabase_client

METERS_PER_DEGREE_LATITUDE = 111_194.93


def _point_north(settings: Settings, meters: float) -> dict[str, float]:
    return {
        "latitude": settings.campus_latitude + meters / METERS_PER_DEGREE_LATITUDE,
        "longitude": settings.campus_longitude,
    }


def test_gps_attendance_geofence_and_accuracy(
    client: TestClient,
    seeded_auth_headers: dict[str, str],
    settings: Settings,
) -> None:
    valid = client.post(
        "/attendance/gps",
        headers=seeded_auth_headers,
        json={
            "latitude": settings.campus_latitude,
            "longitude": settings.campus_longitude,
            "accuracy": settings.geofence_max_accuracy_meters,
        },
    )
    assert valid.status_code == 200, valid.text
    body = valid.json()
    assert body["method"] == "gps"
    assert body["distance_meters"] == 0
    assert body["area"] == settings.geofence_name
    assert body["radius_meters"] == settings.max_gps_distance_meters

    inside = client.post(
        "/attendance/gps",
        headers=seeded_auth_headers,
        json=_point_north(settings, settings.max_gps_distance_meters - 5),
    )
    assert inside.status_code == 200
    assert inside.json()["distance_meters"] == round(settings.max_gps_distance_meters - 5)

    outside = client.post(
        "/attendance/gps",
        headers=seeded_auth_headers,
        json=_point_north(settings, settings.max_gps_distance_meters + 5),
    )
    assert outside.status_code == 403
    assert settings.geofence_name in outside.json()["detail"]

    low_acc = client.post(
        "/attendance/gps",
        headers=seeded_auth_headers,
        json={
            "latitude": settings.campus_latitude,
            "longitude": settings.campus_longitude,
            "accuracy": settings.geofence_max_accuracy_meters + 1,
        },
    )
    assert low_acc.status_code == 422
    assert "Akurasi GPS" in low_acc.json()["detail"]

    bad_coords = client.post(
        "/attendance/gps",
        headers=seeded_auth_headers,
        json={"latitude": 91, "longitude": settings.campus_longitude},
    )
    assert bad_coords.status_code == 422


def test_qr_attendance_valid_and_validations(
    client: TestClient,
    temp_student: dict[str, object],
    settings: Settings,
) -> None:
    supabase = get_supabase_client(settings)
    jadwal_repo = JadwalRepository(client=supabase, settings=settings)
    kehadiran_repo = KehadiranRepository(client=supabase, settings=settings)

    ti3a_jadwals = jadwal_repo.list_by_kelas_nama("TI-3A")
    assert len(ti3a_jadwals) >= 1
    target_jadwal = ti3a_jadwals[0]

    unique_date = "2099-01-15"
    qr_token = f"HADIRIN_TEST_{uuid4().hex[:10]}"
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    kehadiran_repo.client.table("sesi_presensi").delete().eq("jadwal_id", target_jadwal["id"]).eq("tanggal", unique_date).execute()

    sesi = kehadiran_repo.create_sesi_presensi(
        {
            "jadwal_id": target_jadwal["id"],
            "tanggal": unique_date,
            "qr_token": qr_token,
            "qr_expires_at": expires_at,
            "is_open": True,
            "dibuka_oleh": target_jadwal.get("dosen_nip"),
        }
    )
    sesi_id = str(sesi["id"])
    headers = temp_student["headers"]
    nim = str(temp_student["nim"])

    try:
        active_resp = client.get("/attendance/sesi-aktif", headers=headers)  # type: ignore[arg-type]
        assert active_resp.status_code == 200
        assert any(s["sesi_presensi_id"] == sesi_id for s in active_resp.json()["data"])

        out_of_range = client.post(
            "/attendance/qr",
            json={"qr_token": qr_token, "latitude": -6.200000, "longitude": 106.816666},
            headers=headers,  # type: ignore[arg-type]
        )
        assert out_of_range.status_code == 403

        bad_qr = client.post(
            "/attendance/qr",
            json={
                "qr_token": "NON_EXISTENT_QR_9999",
                "latitude": settings.campus_latitude,
                "longitude": settings.campus_longitude,
            },
            headers=headers,  # type: ignore[arg-type]
        )
        assert bad_qr.status_code == 403

        ok = client.post(
            "/attendance/qr",
            json={
                "qr_token": qr_token,
                "latitude": settings.campus_latitude,
                "longitude": settings.campus_longitude,
            },
            headers=headers,  # type: ignore[arg-type]
        )
        assert ok.status_code == 200, ok.text
        data = ok.json()
        assert data["status"] == "hadir"
        assert data["sesi_presensi_id"] == sesi_id

        summary = client.get("/mahasiswa/presensi/summary", headers=headers).json()  # type: ignore[arg-type]
        assert summary["hadir"] == 1
        assert summary["total_pertemuan"] == 1
    finally:
        existing_k = kehadiran_repo.get_kehadiran_by_sesi_and_nim(sesi_id, nim)
        if existing_k:
            kehadiran_repo.delete_kehadiran_by_id(str(existing_k["id"]))
        kehadiran_repo.delete_sesi_presensi(sesi_id)
