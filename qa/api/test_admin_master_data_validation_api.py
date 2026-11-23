"""New negative/business scenarios for admin tahun ajaran & mata kuliah APIs."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_admin_master_data_service
from app.services.admin_master_data_service import AdminMasterDataService

from .conftest import FakeMataKuliahRepo, FakeTahunAjaranRepo


@pytest.fixture
def tahun_repo() -> FakeTahunAjaranRepo:
    return FakeTahunAjaranRepo(
        [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "tahun": "2026/2027",
                "status": "aktif",
                "semester_ganjil": True,
                "semester_genap": True,
            }
        ]
    )


@pytest.fixture
def matkul_repo() -> FakeMataKuliahRepo:
    return FakeMataKuliahRepo(
        [{"kode": "TI101", "nama": "Matematika Dasar", "semester": 1, "sks": 2}]
    )


@pytest.fixture
def master_api(
    client: TestClient,
    override,
    tahun_repo: FakeTahunAjaranRepo,
    matkul_repo: FakeMataKuliahRepo,
) -> TestClient:
    service = AdminMasterDataService(
        tahun_ajaran_repo=tahun_repo, mata_kuliah_repo=matkul_repo
    )
    override(get_admin_master_data_service, lambda: service)
    return client


def test_duplicate_tahun_ajaran_returns_409(
    master_api: TestClient, admin_headers: dict[str, str]
) -> None:
    response = master_api.post(
        "/admin/tahun-ajaran",
        json={"tahun": "2026/2027", "semester_ganjil": True, "semester_genap": True},
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text
    assert "sudah terdaftar" in response.json()["detail"]


def test_invalid_tahun_ajaran_payload_returns_422(
    master_api: TestClient, admin_headers: dict[str, str]
) -> None:
    response = master_api.post(
        "/admin/tahun-ajaran",
        json={"tahun": "2026-2027", "semester_ganjil": True, "semester_genap": True},
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text


def test_delete_referenced_tahun_ajaran_returns_409(
    master_api: TestClient,
    override,
    admin_headers: dict[str, str],
    tahun_repo: FakeTahunAjaranRepo,
    matkul_repo: FakeMataKuliahRepo,
) -> None:
    tahun_repo.referenced = True
    override(
        get_admin_master_data_service,
        lambda: AdminMasterDataService(tahun_repo, matkul_repo),
    )

    response = master_api.delete(
        "/admin/tahun-ajaran/11111111-1111-1111-1111-111111111111",
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text
    assert "masih digunakan" in response.json()["detail"]


def test_mata_kuliah_duplicate_and_invalid_payload(
    master_api: TestClient, admin_headers: dict[str, str]
) -> None:
    duplicate = master_api.post(
        "/admin/mata-kuliah",
        json={"kode": "TI101", "nama": "Matematika Dasar", "semester": 1, "sks": 2},
        headers=admin_headers,
    )
    assert duplicate.status_code == 409, duplicate.text

    invalid = master_api.post(
        "/admin/mata-kuliah",
        json={"kode": "TI999", "nama": "Mata Kuliah Invalid", "semester": 0, "sks": 3},
        headers=admin_headers,
    )
    assert invalid.status_code == 422, invalid.text


def test_delete_referenced_mata_kuliah_returns_409(
    master_api: TestClient,
    override,
    admin_headers: dict[str, str],
    tahun_repo: FakeTahunAjaranRepo,
    matkul_repo: FakeMataKuliahRepo,
) -> None:
    matkul_repo.referenced = True
    override(
        get_admin_master_data_service,
        lambda: AdminMasterDataService(tahun_repo, matkul_repo),
    )

    response = master_api.delete("/admin/mata-kuliah/TI101", headers=admin_headers)

    assert response.status_code == 409, response.text
    assert "masih digunakan oleh jadwal" in response.json()["detail"]
