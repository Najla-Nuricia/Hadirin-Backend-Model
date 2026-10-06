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
    response = client.post(
        "/auth/register",
        json={"nim": "24000003", "name": "New Student", "password": "secure123"},
    )

    assert response.status_code == 201
    assert response.json()["nim"] == "24000003"


def test_register_duplicate_nim_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"nim": "24000001", "name": "Duplicate", "password": "secure123"},
    )

    assert response.status_code == 409
