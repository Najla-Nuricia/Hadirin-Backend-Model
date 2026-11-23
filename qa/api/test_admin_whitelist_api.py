"""API tests for admin NIM whitelist endpoints (isolated in-memory DB)."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_whitelist_nim_service
from app.services.whitelist_nim_service import WhitelistNimService

from .conftest import FakeWhitelistRepo


@pytest.fixture
def whitelist_repo() -> FakeWhitelistRepo:
    return FakeWhitelistRepo(nims=["2341720001"])


@pytest.fixture
def whitelist_api(client: TestClient, override, whitelist_repo: FakeWhitelistRepo) -> TestClient:
    service = WhitelistNimService(whitelist_repo)
    override(get_whitelist_nim_service, lambda: service)
    return client


def test_create_nim_returns_201_with_belum_registrasi(
    whitelist_api: TestClient, admin_headers: dict[str, str]
) -> None:
    response = whitelist_api.post(
        "/admin/whitelist-nim", json={"nim": " 99887766 "}, headers=admin_headers
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["data"]["nim"] == "99887766"
    assert body["data"]["status"] == "Belum Registrasi"
    assert body["data"]["nama_mahasiswa"] == "-"


def test_create_duplicate_nim_returns_409(
    whitelist_api: TestClient, admin_headers: dict[str, str]
) -> None:
    response = whitelist_api.post(
        "/admin/whitelist-nim", json={"nim": "2341720001"}, headers=admin_headers
    )

    assert response.status_code == 409, response.text
    assert "sudah ada di whitelist" in response.json()["detail"]


def test_list_marks_registered_student_and_filters_by_search(
    client: TestClient,
    override,
    admin_headers: dict[str, str],
) -> None:
    repo = FakeWhitelistRepo(
        nims=["2341720001", "99887766"],
        students={
            "2341720001": {
                "nama_lengkap": "Najla Nuricia",
                "kelas": {"nama": "TI-3A"},
            }
        },
    )
    override(get_whitelist_nim_service, lambda: WhitelistNimService(repo))

    response = client.get(
        "/admin/whitelist-nim", params={"search": "2341"}, headers=admin_headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    item = body["data"][0]
    assert item["nim"] == "2341720001"
    assert item["status"] == "Sudah Registrasi"
    assert item["nama_mahasiswa"] == "Najla Nuricia"
    assert item["kelas"] == "TI-3A"


def test_delete_registered_nim_is_rejected_but_unregistered_succeeds(
    whitelist_api: TestClient,
    override,
    admin_headers: dict[str, str],
    whitelist_repo: FakeWhitelistRepo,
) -> None:
    whitelist_repo.students["2341720001"] = {
        "nama_lengkap": "Najla Nuricia",
        "kelas": {"nama": "TI-3A"},
    }

    rejected = whitelist_api.delete(
        "/admin/whitelist-nim/2341720001", headers=admin_headers
    )
    assert rejected.status_code == 409, rejected.text
    assert "tidak dapat dihapus" in rejected.json()["detail"]
    assert "2341720001" in whitelist_repo.rows

    whitelist_api.post(
        "/admin/whitelist-nim", json={"nim": "99887766"}, headers=admin_headers
    )
    deleted = whitelist_api.delete(
        "/admin/whitelist-nim/99887766", headers=admin_headers
    )
    assert deleted.status_code == 200, deleted.text
    assert "99887766" not in whitelist_repo.rows


def test_whitelist_endpoints_require_admin_role(
    client: TestClient,
    override,
    whitelist_repo: FakeWhitelistRepo,
    student_headers: dict[str, str],
    dosen_headers: dict[str, str],
) -> None:
    override(get_whitelist_nim_service, lambda: WhitelistNimService(whitelist_repo))

    assert client.get("/admin/whitelist-nim").status_code == 401
    assert (
        client.get("/admin/whitelist-nim", headers=student_headers).status_code == 403
    )
    assert (
        client.post(
            "/admin/whitelist-nim",
            json={"nim": "99887766"},
            headers=dosen_headers,
        ).status_code
        == 403
    )
