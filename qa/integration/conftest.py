import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import create_app

DOSEN_TEST_PASSWORD = "dosen-test-password"
DOSEN_TI3A_EMAIL = "budi.santoso@polinema.ac.id"


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
