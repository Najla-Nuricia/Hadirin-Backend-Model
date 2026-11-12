from fastapi.testclient import TestClient

from app.main import GEOFENCE_CENTER


def test_history_only_returns_authenticated_users_records(
    client: TestClient, student_headers: dict, open_session
) -> None:
    first_user_attendance = client.post(
        "/attendance/qr",
        headers=student_headers,
        json={"code": open_session()["qr_code"]},
    )
    second_user_login = client.post(
        "/auth/login",
        json={"nim": "24000002", "password": "password123"},
    )
    second_user_headers = {
        "Authorization": f"Bearer {second_user_login.json()['access_token']}"
    }
    latitude, longitude = GEOFENCE_CENTER
    second_user_attendance = client.post(
        "/attendance/gps",
        headers=second_user_headers,
        json={"latitude": latitude, "longitude": longitude},
    )

    assert first_user_attendance.status_code == 200
    assert second_user_login.status_code == 200
    assert second_user_attendance.status_code == 200

    first_user_history = client.get("/attendance/history", headers=student_headers)
    second_user_history = client.get(
        "/attendance/history", headers=second_user_headers
    )

    assert first_user_history.status_code == 200
    assert [record["method"] for record in first_user_history.json()] == ["qr"]
    qr_record = first_user_history.json()[0]
    assert qr_record["status"] == "hadir"
    assert qr_record["courseName"] == "Pemrograman Web Lanjut"
    assert qr_record["date"] == "05"
    assert qr_record["time"] == "08:00"
    assert second_user_history.status_code == 200
    assert [record["method"] for record in second_user_history.json()] == ["gps"]
