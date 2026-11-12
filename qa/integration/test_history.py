"""Integration tests for health checks and attendance history backed by `v_rekap_kehadiran`."""

from fastapi.testclient import TestClient


def test_health_endpoint_reports_db_and_ml_status(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"
    assert body["ml_weights_ready"] is True


def test_attendance_history_authenticated(
    client: TestClient,
    seeded_auth_headers: dict[str, str],
) -> None:
    response = client.get("/attendance/history", headers=seeded_auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["data"], list)
    assert payload["total"] == len(payload["data"])


def test_attendance_history_for_seeded_student(client: TestClient) -> None:
    login_resp = client.post(
        "/auth/login",
        json={"nim": "2211001", "password": "mahasiswa123"},
    )
    assert login_resp.status_code == 200
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    riwayat = client.get("/mahasiswa/presensi/riwayat", headers=headers)
    assert riwayat.status_code == 200
    data = riwayat.json()
    assert data["total"] >= 1
    first = data["data"][0]
    assert first["nim"] == "2211001"
    assert first["courseName"]
    assert first["status"] in {"hadir", "izin", "sakit", "alfa"}


def test_attendance_history_unauthenticated(client: TestClient) -> None:
    response = client.get("/attendance/history")
    assert response.status_code == 401
