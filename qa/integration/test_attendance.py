"""Integration tests for static room QR and GPS attendance backed by DB."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.config import Settings

METERS_PER_DEGREE_LATITUDE = 111_194.93
JADWAL_TI3A_SENIN = "33333333-0000-0000-0000-000000000001"
RUANGAN_TI3A_SENIN = "J301"


def _point_north(settings: Settings, meters: float) -> dict[str, float]:
    return {
        "latitude": settings.campus_latitude + meters / METERS_PER_DEGREE_LATITUDE,
        "longitude": settings.campus_longitude,
    }


def test_gps_attendance_geofence_and_accuracy(
    client: TestClient,
    temp_student: dict[str, object],
    settings: Settings,
    session_clock: dict,
    ensure_sesi,
) -> None:
    headers = temp_student["headers"]  # type: ignore[assignment]
    sesi = ensure_sesi(JADWAL_TI3A_SENIN)
    base = {
        "sesi_presensi_id": sesi["sesi_presensi_id"],
        "latitude": settings.campus_latitude,
        "longitude": settings.campus_longitude,
    }

    valid = client.post("/attendance/gps", headers=headers, json=base)  # type: ignore[arg-type]
    assert valid.status_code == 200, valid.text
    body = valid.json()
    assert body["method"] == "gps"
    assert body["distance_meters"] == 0
    assert body["area"] == settings.geofence_name
    assert body["radius_meters"] == settings.max_gps_distance_meters

    inside = client.post(
        "/attendance/gps",
        headers=headers,  # type: ignore[arg-type]
        json={**base, **_point_north(settings, settings.max_gps_distance_meters - 5)},
    )
    assert inside.status_code == 200
    assert inside.json()["distance_meters"] == round(settings.max_gps_distance_meters - 5)

    outside = client.post(
        "/attendance/gps",
        headers=headers,  # type: ignore[arg-type]
        json={**base, **_point_north(settings, settings.max_gps_distance_meters + 5)},
    )
    assert outside.status_code == 403
    assert settings.geofence_name in outside.json()["detail"]

    low_acc = client.post(
        "/attendance/gps",
        headers=headers,  # type: ignore[arg-type]
        json={**base, "accuracy": settings.geofence_max_accuracy_meters + 1},
    )
    assert low_acc.status_code == 422
    assert "Akurasi GPS" in low_acc.json()["detail"]

    bad_coords = client.post(
        "/attendance/gps",
        headers=headers,  # type: ignore[arg-type]
        json={**base, "latitude": 91},
    )
    assert bad_coords.status_code == 422


def test_static_room_qr_validates_room_and_time(
    client: TestClient,
    temp_student: dict[str, object],
    settings: Settings,
    session_clock: dict,
    ensure_sesi,
) -> None:
    headers = temp_student["headers"]  # type: ignore[assignment]
    sesi = ensure_sesi(JADWAL_TI3A_SENIN)
    valid = client.post(
        "/attendance/room-qr/validate",
        headers=headers,  # type: ignore[arg-type]
        json={
            "qr_token": f"HADIRIN:ROOM:{RUANGAN_TI3A_SENIN}",
            "latitude": settings.campus_latitude,
            "longitude": settings.campus_longitude,
        },
    )
    assert valid.status_code == 200, valid.text
    assert valid.json()["sesi_presensi_id"] == sesi["sesi_presensi_id"]

    wrong_room = client.post(
        "/attendance/room-qr/validate",
        headers=headers,  # type: ignore[arg-type]
        json={"qr_token": "HADIRIN:ROOM:LPR9"},
    )
    assert wrong_room.status_code == 403

    session_clock["now"] += timedelta(hours=3)
    outside_window = client.post(
        "/attendance/room-qr/validate",
        headers=headers,  # type: ignore[arg-type]
        json={"qr_token": f"HADIRIN:ROOM:{RUANGAN_TI3A_SENIN}"},
    )
    assert outside_window.status_code == 403
    assert "jadwal" in outside_window.json()["detail"].lower()


def test_gps_attendance_is_idempotent_per_day(
    client: TestClient,
    temp_student: dict[str, object],
    settings: Settings,
    session_clock: dict,
    ensure_sesi,
) -> None:
    headers = temp_student["headers"]  # type: ignore[assignment]
    sesi = ensure_sesi(JADWAL_TI3A_SENIN)
    payload = {
        "sesi_presensi_id": sesi["sesi_presensi_id"],
        "latitude": settings.campus_latitude,
        "longitude": settings.campus_longitude,
    }

    first = client.post("/attendance/gps", headers=headers, json=payload)  # type: ignore[arg-type]
    second = client.post("/attendance/gps", headers=headers, json=payload)  # type: ignore[arg-type]
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["kehadiran_id"] == second.json()["kehadiran_id"]

    history = client.get("/attendance/history", headers=headers)  # type: ignore[arg-type]
    assert history.status_code == 200
    assert sum(
        row["sesi_presensi_id"] == sesi["sesi_presensi_id"]
        for row in history.json()["data"]
    ) == 1

    session_clock["now"] += timedelta(days=7)
    next_day = client.post("/attendance/gps", headers=headers, json=payload)  # type: ignore[arg-type]
    assert next_day.status_code == 200, next_day.text
    assert next_day.json()["kehadiran_id"] != first.json()["kehadiran_id"]
