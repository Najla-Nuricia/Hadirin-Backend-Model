"""Integration tests for registration, Supabase Auth login, stateless JWT, and password updates."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.repositories import AuthRepository, MahasiswaRepository
from app.db.session import get_supabase_client


def test_login_valid_credentials(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"nim": "24000001", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert len(data["access_token"].split(".")) == 3
    assert data["token_type"] == "bearer"
    assert data["user"]["nim"] == "24000001"
    assert data["user"]["name"] == "Demo Student One"
    assert data["user"]["kelas"] == "TI-3A"


def test_login_by_email(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"nim": "24000001@student.polinema.ac.id", "password": "password123"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["nim"] == "24000001"


def test_login_wrong_password_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"nim": "24000001", "password": "wrong-password-123"},
    )
    assert response.status_code == 401


def test_login_nonexistent_user_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"nim": "99999999", "password": "password123"},
    )
    assert response.status_code == 401


def test_register_valid_user_and_cleanup(client: TestClient, settings: Settings) -> None:
    new_nim = f"2499{uuid4().hex[:6]}"
    try:
        response = client.post(
            "/auth/register",
            json={
                "nim": new_nim,
                "name": "New Registered Student",
                "password": "securePassword123",
            },
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["nim"] == new_nim
        assert data["name"] == "New Registered Student"
        assert data["role"] == "Mahasiswa"

        # Real Supabase Auth sign-in must work with the chosen password and reject wrong ones.
        ok_login = client.post(
            "/auth/login",
            json={"nim": new_nim, "password": "securePassword123"},
        )
        assert ok_login.status_code == 200

        bad_login = client.post(
            "/auth/login",
            json={"nim": new_nim, "password": "otherPassword"},
        )
        assert bad_login.status_code == 401
    finally:
        supabase = get_supabase_client(settings)
        mhs_repo = MahasiswaRepository(client=supabase, settings=settings)
        auth_repo = AuthRepository(client=supabase, settings=settings)
        row = mhs_repo.get_by_nim(new_nim)
        if row:
            mhs_repo.delete_by_nim(new_nim)
            if row.get("auth_user_id"):
                try:
                    auth_repo.delete_auth_user(str(row["auth_user_id"]))
                except Exception:
                    pass


def test_register_duplicate_nim_conflict(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "nim": "24000001",
            "name": "Duplicate",
            "password": "securePassword123",
        },
    )
    assert response.status_code == 409


def test_change_password_persistence(client: TestClient, temp_student: dict[str, object]) -> None:
    nim = str(temp_student["nim"])
    old_pw = str(temp_student["password"])
    headers = temp_student["headers"]
    new_pw = "UpdatedPass987!"

    # Wrong current password must fail with 400.
    bad = client.put(
        "/auth/change-password",
        json={"current_password": "not-the-password", "new_password": new_pw},
        headers=headers,  # type: ignore[arg-type]
    )
    assert bad.status_code == 400

    # Valid change succeeds and persists to Supabase Auth.
    ok = client.put(
        "/auth/change-password",
        json={
            "current_password": old_pw,
            "new_password": new_pw,
            "confirm_password": new_pw,
        },
        headers=headers,  # type: ignore[arg-type]
    )
    assert ok.status_code == 200, ok.text

    old_login = client.post("/auth/login", json={"nim": nim, "password": old_pw})
    assert old_login.status_code == 401

    new_login = client.post("/auth/login", json={"nim": nim, "password": new_pw})
    assert new_login.status_code == 200
