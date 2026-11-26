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

DOSEN_TEST_PASSWORD = "dosen123"
DOSEN_TI3A_EMAIL = "budi.santoso@polinema.ac.id"
SENTINEL_NOW = datetime(2099, 1, 5, 8, 0, tzinfo=common.WIB)


def _delete_sentinel_kehadiran(settings: Settings) -> None:
    """Sesi persisten tidak dihapus; hanya baris kehadiran pada tanggal sentinel."""
    supabase = get_supabase_client(settings)
    (
        supabase.table("kehadiran")
        .delete()
        .eq("tanggal", SENTINEL_NOW.date().isoformat())
        .execute()
    )


def _cleanup_student_by_nim(settings: Settings, nim: str) -> None:
    supabase = get_supabase_client(settings)
    mhs_repo = MahasiswaRepository(client=supabase, settings=settings)
    auth_repo = AuthRepository(client=supabase, settings=settings)
    foto_repo = FotoWajahRepository(client=supabase, settings=settings)

    row = mhs_repo.get_by_nim(nim)
    if not row:
        return
    foto_repo.delete_by_nim(nim)
    supabase.table("kehadiran").delete().eq("nim", nim).execute()
    mhs_repo.delete_by_nim(nim)
    try:
        supabase.table("whitelist_nim").delete().eq("nim", nim).execute()
    except Exception:
        pass
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
    unique_nim = f"2488{uuid4().int % 1_000_000:06d}"
    password = "TempPassword123!"
    email = f"{unique_nim}@student.polinema.ac.id"
    get_supabase_client(settings).table("whitelist_nim").upsert({"nim": unique_nim}).execute()

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
    unique_nim = f"2477{uuid4().int % 1_000_000:06d}"
    password = "TempPassword123!"
    email = f"{unique_nim}@student.polinema.ac.id"
    get_supabase_client(settings).table("whitelist_nim").upsert({"nim": unique_nim}).execute()

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
def dosen_login(client: TestClient):
    """Return a helper issuing lecturer JWT headers via Supabase Auth credentials."""

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
    """Freeze server clock on sentinel date `2099-01-05` and clean up sentinel attendance rows."""
    clock = {"now": SENTINEL_NOW}
    monkeypatch.setattr(common, "now_wib", lambda: clock["now"])
    _delete_sentinel_kehadiran(settings)
    yield clock
    _delete_sentinel_kehadiran(settings)


@pytest.fixture
def ensure_sesi(settings: Settings, session_clock: dict):
    """Return the persistent session auto-created for a jadwal."""
    repo = KehadiranRepository(client=get_supabase_client(settings), settings=settings)

    def get_for(jadwal_id: str = "33333333-0000-0000-0000-000000000001") -> dict:
        sesi = repo.get_sesi_by_jadwal_id(jadwal_id)
        assert sesi is not None, f"Tidak ada sesi persisten untuk jadwal {jadwal_id}"
        return {"sesi_presensi_id": str(sesi["id"]), "jadwal_id": str(sesi["jadwal_id"])}

    return get_for
