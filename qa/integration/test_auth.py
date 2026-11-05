from fastapi.testclient import TestClient


def test_login_with_valid_credentials(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"nim": "24000001", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_with_incorrect_password_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"nim": "24000001", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_with_empty_fields_is_rejected(client: TestClient) -> None:
    response = client.post("/auth/login", json={"nim": "", "password": ""})

    assert response.status_code == 422


def test_register_valid_user(client: TestClient) -> None:
    nim = "24000003"
    client.delete(f"/mahasiswa/{nim}")

    try:
        response = client.post(
            "/auth/register",
            json={"nim": nim, "name": "New Student", "password": "secure123"},
        )

        assert response.status_code == 201
        assert response.json()["nim"] == nim
    finally:
        client.delete(f"/mahasiswa/{nim}")


def test_register_duplicate_nim_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"nim": "24000001", "name": "Duplicate", "password": "secure123"},
    )

    assert response.status_code == 409


def test_login_with_flutter_demo_account(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"nim": "2341720001", "password": "mahasiswa123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Mahasiswa Demo"
    assert body["fullName"] == "Mahasiswa Demo"
    assert body["className"] == "3F-TI"
    assert body["phoneNumber"] == "081234567890"
    assert body["access_token"].startswith("jwt_")


def test_flutter_demo_profile_uses_frontend_field_names(
    client: TestClient,
) -> None:
    login = client.post(
        "/auth/login",
        json={"nim": "2341720001", "password": "mahasiswa123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/mahasiswa/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["fullName"] == "Mahasiswa Demo"
    assert body["nim"] == "2341720001"
    assert body["phoneNumber"] == "081234567890"
    assert body["role"] == "Mahasiswa"


def test_change_password_then_login_with_new_password(client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"nim": "2341720001", "password": "mahasiswa123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    changed = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "mahasiswa123", "new_password": "mahasiswa456"},
    )
    assert changed.status_code == 200

    old_login = client.post(
        "/auth/login",
        json={"nim": "2341720001", "password": "mahasiswa123"},
    )
    new_login = client.post(
        "/auth/login",
        json={"nim": "2341720001", "password": "mahasiswa456"},
    )

    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_change_password_rejects_wrong_current_password(
    client: TestClient, auth_headers: dict
) -> None:
    response = client.post(
        "/auth/change-password",
        headers=auth_headers,
        json={"current_password": "salah", "new_password": "password456"},
    )

    assert response.status_code == 401
