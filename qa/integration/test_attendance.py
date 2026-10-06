from fastapi.testclient import TestClient

from app.main import DEMO_CAMPUS_LOCATION, DEMO_VALID_QR_CODE


def test_attendance_with_valid_gps(client: TestClient, auth_headers: dict) -> None:
    latitude, longitude = DEMO_CAMPUS_LOCATION
    response = client.post(
        "/attendance/gps",
        headers=auth_headers,
        json={"latitude": latitude, "longitude": longitude},
    )

    assert response.status_code == 200
    assert response.json()["method"] == "gps"
    assert response.json()["distance_meters"] == 0


def test_gps_outside_area_is_rejected(
    client: TestClient, auth_headers: dict
) -> None:
    response = client.post(
        "/attendance/gps",
        headers=auth_headers,
        json={"latitude": 0, "longitude": 0},
    )

    assert response.status_code == 403


def test_attendance_with_valid_qr(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/attendance/qr",
        headers=auth_headers,
        json={"code": DEMO_VALID_QR_CODE},
    )

    assert response.status_code == 200
    assert response.json()["method"] == "qr"


def test_invalid_qr_is_rejected(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/attendance/qr",
        headers=auth_headers,
        json={"code": "NOT-A-VALID-QR"},
    )

    assert response.status_code == 403
