from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import create_app

DOSEN_TEST_PASSWORD = "dosen-test-password"
DOSEN_TI3A_EMAIL = "budi.santoso@polinema.ac.id"
JADWAL_TI3A = "33333333-0000-0000-0000-000000000001"

# Database dipakai bersama. Sesi presensi tes dibuat pada tanggal yang tidak mungkin
# dipakai sesi sungguhan, sehingga pembersihan tidak menyentuh data orang lain.
SENTINEL_NOW = datetime(2099, 1, 5, 8, 0, tzinfo=main.WIB)


def delete_sentinel_sessions() -> None:
    (
        main.get_supabase()
        .table("sesi_presensi")
        .delete()
        .eq("tanggal", SENTINEL_NOW.date().isoformat())
        .execute()
    )


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"nim": "24000001", "password": "password123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_headers(client: TestClient) -> dict[str, str]:
    """Mahasiswa kelas TI-3A yang profilnya dibaca dari database."""
    response = client.post(
        "/auth/login",
        json={"nim": "2341720001", "password": "mahasiswa123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def dosen_login(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "DOSEN_DEFAULT_PASSWORD", DOSEN_TEST_PASSWORD)

    def login(email: str) -> dict[str, str]:
        response = client.post(
            "/auth/dosen/login",
            json={"email": email, "password": DOSEN_TEST_PASSWORD},
        )
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return login


@pytest.fixture
def dosen_headers(dosen_login) -> dict[str, str]:
    """Dosen pengampu jadwal TI-3A."""
    return dosen_login(DOSEN_TI3A_EMAIL)


@pytest.fixture
def session_clock(monkeypatch: pytest.MonkeyPatch):
    """Bekukan waktu server pada tanggal sentinel; ubah clock["now"] untuk memajukannya."""
    clock = {"now": SENTINEL_NOW}
    monkeypatch.setattr(main, "now_wib", lambda: clock["now"])
    delete_sentinel_sessions()
    yield clock
    delete_sentinel_sessions()


@pytest.fixture
def open_session(client: TestClient, dosen_headers: dict, session_clock: dict):
    def open_for(jadwal_id: str = JADWAL_TI3A, headers: dict | None = None) -> dict:
        response = client.post(
            f"/dosen/jadwal/{jadwal_id}/sesi-presensi",
            headers=headers or dosen_headers,
        )
        assert response.status_code == 200
        return response.json()

    return open_for
