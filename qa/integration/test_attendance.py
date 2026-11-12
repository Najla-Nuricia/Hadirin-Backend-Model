from fastapi.testclient import TestClient

from app.main import (
    GEOFENCE_CENTER,
    GEOFENCE_MAX_ACCURACY_METERS,
    GEOFENCE_NAME,
    GEOFENCE_RADIUS_METERS,
)

METERS_PER_DEGREE_LATITUDE = 111_194.93


def point_north_of_center(meters: float) -> dict:
    latitude, longitude = GEOFENCE_CENTER
    return {
        "latitude": latitude + meters / METERS_PER_DEGREE_LATITUDE,
        "longitude": longitude,
    }


def test_attendance_with_valid_gps(client: TestClient, auth_headers: dict) -> None:
    latitude, longitude = GEOFENCE_CENTER
    response = client.post(
        "/attendance/gps",
        headers=auth_headers,
        json={"latitude": latitude, "longitude": longitude},
    )

    assert response.status_code == 200
    assert response.json()["method"] == "gps"
    assert response.json()["distance_meters"] == 0
    assert response.json()["area"] == GEOFENCE_NAME
    assert response.json()["radius_meters"] == GEOFENCE_RADIUS_METERS


def test_gps_outside_area_is_rejected(
    client: TestClient, auth_headers: dict
) -> None:
    response = client.post(
        "/attendance/gps",
        headers=auth_headers,
        json={"latitude": 0, "longitude": 0},
    )

    assert response.status_code == 403


def test_gps_geofence_boundary(client: TestClient, auth_headers: dict) -> None:
    inside = client.post(
        "/attendance/gps",
        headers=auth_headers,
        json=point_north_of_center(GEOFENCE_RADIUS_METERS - 5),
    )
    outside = client.post(
        "/attendance/gps",
        headers=auth_headers,
        json=point_north_of_center(GEOFENCE_RADIUS_METERS + 5),
    )

    assert inside.status_code == 200
    assert inside.json()["distance_meters"] == round(GEOFENCE_RADIUS_METERS - 5)
    assert outside.status_code == 403
    assert GEOFENCE_NAME in outside.json()["detail"]


def test_gps_with_impossible_coordinates_is_rejected(
    client: TestClient, auth_headers: dict
) -> None:
    response = client.post(
        "/attendance/gps",
        headers=auth_headers,
        json={"latitude": 91, "longitude": 106.8},
    )

    assert response.status_code == 422


def test_gps_with_low_accuracy_is_rejected(
    client: TestClient, auth_headers: dict
) -> None:
    latitude, longitude = GEOFENCE_CENTER
    response = client.post(
        "/attendance/gps",
        headers=auth_headers,
        json={
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": GEOFENCE_MAX_ACCURACY_METERS + 1,
        },
    )

    assert response.status_code == 422
    assert "Akurasi GPS" in response.json()["detail"]


def test_gps_with_acceptable_accuracy_is_accepted(
    client: TestClient, auth_headers: dict
) -> None:
    latitude, longitude = GEOFENCE_CENTER
    response = client.post(
        "/attendance/gps",
        headers=auth_headers,
        json={
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": GEOFENCE_MAX_ACCURACY_METERS,
        },
    )

    assert response.status_code == 200


def test_invalid_qr_is_rejected(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/attendance/qr",
        headers=auth_headers,
        json={"code": "NOT-A-VALID-QR"},
    )

    assert response.status_code == 403
