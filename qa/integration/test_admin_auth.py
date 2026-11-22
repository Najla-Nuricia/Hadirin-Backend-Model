"""Integration tests for admin JWT authentication and Mahasiswa/Dosen auth regression."""

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token


def _login_admin(client: TestClient) -> str:
    response = client.post(
        "/auth/admin/login",
        json={"username": "adminhadirin", "password": "admin123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_admin_login_success_returns_valid_jwt(client: TestClient) -> None:
    response = client.post(
        "/auth/admin/login",
        json={"username": "adminhadirin", "password": "admin123"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["username"] == "adminhadirin"
    assert body["role"] == "Admin"
    assert body["token_type"] == "bearer"
    assert body["token"] == body["access_token"]
    assert body["expires_in"] > 0

    payload = decode_access_token(body["access_token"], settings=get_settings())
    assert payload["sub"] == "adminhadirin"
    assert payload["role"] == "admin"
    assert payload["username"] == "adminhadirin"


def test_admin_login_accepts_supabase_email_identifier(client: TestClient) -> None:
    response = client.post(
        "/auth/admin/login",
        json={"username": "admin@hadirin.polinema.ac.id", "password": "admin123"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["username"] == "adminhadirin"


def test_admin_login_rejects_password_of_other_role(client: TestClient) -> None:
    """A password belonging to another role's account must not authenticate admin."""
    response = client.post(
        "/auth/admin/login",
        json={"username": "adminhadirin", "password": "dosen123"},
    )

    assert response.status_code == 401


def test_admin_login_rejects_wrong_password(client: TestClient) -> None:
    response = client.post(
        "/auth/admin/login",
        json={"username": "adminhadirin", "password": "salah123"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_admin_login_rejects_unknown_username(client: TestClient) -> None:
    response = client.post(
        "/auth/admin/login",
        json={"username": "bukanadmin", "password": "admin123"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_admin_endpoint_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/auth/admin/me")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_admin_endpoint_rejects_tampered_token(client: TestClient) -> None:
    token = _login_admin(client) + "tampered"

    response = client.get("/auth/admin/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_admin_endpoint_accepts_admin_token(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_login_admin(client)}"}

    response = client.get("/auth/admin/me", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["username"] == "adminhadirin"


def test_admin_endpoint_rejects_student_and_dosen_tokens(
    client: TestClient,
    seeded_auth_headers: dict[str, str],
    dosen_headers: dict[str, str],
) -> None:
    student_response = client.get("/auth/admin/me", headers=seeded_auth_headers)
    dosen_response = client.get("/auth/admin/me", headers=dosen_headers)

    assert student_response.status_code == 403
    assert dosen_response.status_code == 403
    assert student_response.json()["code"] == "forbidden"
    assert dosen_response.json()["code"] == "forbidden"


def test_admin_token_is_rejected_on_student_and_dosen_endpoints(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {_login_admin(client)}"}

    student_response = client.get("/mahasiswa/me", headers=headers)
    dosen_response = client.get("/dosen/dashboard", headers=headers)

    assert student_response.status_code in (401, 403)
    assert dosen_response.status_code in (401, 403)


def test_mahasiswa_and_dosen_auth_still_work(
    client: TestClient,
    settings: Settings,
    seeded_auth_headers: dict[str, str],
    dosen_headers: dict[str, str],
) -> None:
    """Regression: existing flows keep issuing usable tokens after admin auth changes."""
    student_me = client.get("/mahasiswa/me", headers=seeded_auth_headers)
    dosen_dashboard = client.get("/dosen/dashboard", headers=dosen_headers)

    assert student_me.status_code == 200, student_me.text
    assert dosen_dashboard.status_code == 200, dosen_dashboard.text
    assert decode_access_token(seeded_auth_headers["Authorization"].split()[1], settings=settings)["role"] == "mahasiswa"
    assert decode_access_token(dosen_headers["Authorization"].split()[1], settings=settings)["role"] == "dosen"
