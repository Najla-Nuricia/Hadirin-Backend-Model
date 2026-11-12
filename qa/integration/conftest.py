"""Shared Pytest fixtures and cleanup helpers for live FastAPI + Supabase integration tests."""

from collections.abc import Iterator
from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings, get_settings
from app.db.repositories import (
    AuthRepository,
    FotoWajahRepository,
    KehadiranRepository,
    MahasiswaRepository,
)
from app.db.session import get_supabase_client
from app.main import app
from app.services import common

DOSEN_TEST_PASSWORD = "dosen-test-password"
DOSEN_TI3A_EMAIL = "budi.santoso@polinema.ac.id"
SENTINEL_NOW = datetime(2099, 1, 5, 8, 0, tzinfo=common.WIB)


def _delete_sentinel_sessions(settings: Settings) -> None:
    supabase = get_supabase_client(settings)
    (
        supabase.table("sesi_presensi")
        .delete()
        .eq("tanggal", SENTINEL_NOW.date().isoformat())
        .execute()
    )


def _cleanup_student_by_nim(settings: Settings, nim: str) -> None:
    supabase = get_supabase_client(settings)
    mhs_repo = MahasiswaRepository(client=supabase, settings=settings)
    auth_repo = AuthRepository(client=supabase, settings=settings)
    foto_repo = FotoWajahRepository(client=supabase, settings=settings)
    kehadiran_repo = KehadiranRepository(client=supabase, settings=settings)

    row = mhs_repo.get_by_nim(nim)
    if not row:
        return
    foto_repo.delete_by_nim(nim)
    for k in kehadiran_repo.list_kehadiran_by_nim(nim):
        kehadiran_repo.delete_attendance_photo(k.get("face_photo_path"))
        kehadiran_repo.delete_kehadiran_by_id(str(k["id"]))
    mhs_repo.delete_by_nim(nim)
    if row.get("auth_user_id"):
        try:
            auth_repo.delete_auth_user(str(row["auth_user_id"]))
        except Exception:
            pass


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def seeded_auth_headers(client: TestClient) -> dict[str, str]:
    """Authenticate `24000001` against live Supabase Auth and return Bearer headers."""
    response = client.post(
        "/auth/login",
        json={"nim": "24000001", "password": "password123"},
    )
    assert response.status_code == 200, f"Demo login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def temp_student(client: TestClient, settings: Settings) -> Iterator[dict[str, str]]:
    """Create a real temporary student linked to Supabase Auth + TI-3A and delete on teardown."""
    unique_nim = f"2488{uuid4().hex[:6]}"
    password = "TempPassword123!"
    email = f"{unique_nim}@student.polinema.ac.id"

    reg_resp = client.post(
        "/auth/register",
        json={
            "nim": unique_nim,
            "name": "Temp Test Student",
            "password": password,
            "email": email,
            "kelas": "TI-3A",
            "no_hp": "081200000001",
        },
    )
    assert reg_resp.status_code == 201, reg_resp.text

    login_resp = client.post(
        "/auth/login",
        json={"nim": unique_nim, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]

    try:
        yield {
            "nim": unique_nim,
            "password": password,
            "email": email,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
        }
    finally:
        _cleanup_student_by_nim(settings, unique_nim)


@pytest.fixture
def temp_student_no_class(client: TestClient, settings: Settings) -> Iterator[dict[str, str]]:
    """Create a real temporary student without `kelas_id` and delete on teardown."""
    unique_nim = f"2477{uuid4().hex[:6]}"
    password = "TempPassword123!"
    email = f"{unique_nim}@student.polinema.ac.id"

    reg_resp = client.post(
        "/auth/register",
        json={
            "nim": unique_nim,
            "name": "No Class Student",
            "password": password,
            "email": email,
        },
    )
    assert reg_resp.status_code == 201, reg_resp.text
    login_resp = client.post(
        "/auth/login",
        json={"nim": unique_nim, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]

    try:
        yield {
            "nim": unique_nim,
            "headers": {"Authorization": f"Bearer {token}"},
        }
    finally:
        _cleanup_student_by_nim(settings, unique_nim)


@pytest.fixture
def dosen_login(client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch):
    """Enable lecturer login for tests and return a helper issuing lecturer JWT headers."""
    monkeypatch.setattr(settings, "dosen_default_password", DOSEN_TEST_PASSWORD)

    def login(email: str = DOSEN_TI3A_EMAIL) -> dict[str, str]:
        response = client.post(
            "/auth/dosen/login",
            json={"email": email, "password": DOSEN_TEST_PASSWORD},
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return login


@pytest.fixture
def dosen_headers(dosen_login) -> dict[str, str]:
    """Authenticated headers for TI-3A lecturer."""
    return dosen_login(DOSEN_TI3A_EMAIL)


@pytest.fixture
def session_clock(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    """Freeze server clock on sentinel date `2099-01-05` and clean up sentinel sessions."""
    clock = {"now": SENTINEL_NOW}
    monkeypatch.setattr(common, "now_wib", lambda: clock["now"])
    _delete_sentinel_sessions(settings)
    yield clock
    _delete_sentinel_sessions(settings)


@pytest.fixture
def open_session(client: TestClient, dosen_headers: dict[str, str], session_clock: dict):
    """Helper fixture opening an attendance session on the frozen sentinel date."""
    def open_for(
        jadwal_id: str = "33333333-0000-0000-0000-000000000001",
        headers: dict[str, str] | None = None,
    ) -> dict:
        response = client.post(
            f"/dosen/jadwal/{jadwal_id}/sesi-presensi",
            headers=headers or dosen_headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    return open_for
