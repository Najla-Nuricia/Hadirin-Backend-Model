from fastapi.testclient import TestClient


def test_history_only_returns_authenticated_users_records(
    client: TestClient, auth_headers: dict
) -> None:
    first_user_attendance = client.post(
        "/attendance/qr",
        headers=auth_headers,
        json={"code": "HADIRIN-DEMO-QR"},
    )
    second_user_login = client.post(
        "/auth/login",
        json={"nim": "24000002", "password": "password123"},
    )
    second_user_headers = {
        "Authorization": f"Bearer {second_user_login.json()['access_token']}"
    }
    second_user_attendance = client.post(
        "/attendance/gps",
        headers=second_user_headers,
        json={"latitude": -6.2, "longitude": 106.8167},
    )

    assert first_user_attendance.status_code == 200
    assert second_user_login.status_code == 200
    assert second_user_attendance.status_code == 200

    first_user_history = client.get("/attendance/history", headers=auth_headers)
    second_user_history = client.get(
        "/attendance/history", headers=second_user_headers
    )

    assert first_user_history.status_code == 200
    assert [record["method"] for record in first_user_history.json()] == ["qr"]
    assert second_user_history.status_code == 200
    assert [record["method"] for record in second_user_history.json()] == ["gps"]
