"""API tests for admin schedule-form option endpoints and enriched /kelas."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_admin_master_data_service,
    get_admin_options_service,
    get_db_client,
)
from app.services.admin_master_data_service import AdminMasterDataService
from app.services.admin_options_service import AdminOptionsService

from .conftest import FakeListRepo, FakeSupabaseClient


@pytest.fixture
def options_api(client: TestClient, override) -> TestClient:
    service = AdminOptionsService(
        dosen_repo=FakeListRepo(
            [
                {
                    "nip": "198501012010121001",
                    "nama": "Budi Santoso",
                    "email": "budi@polinema.ac.id",
                },
                {
                    "nip": "999999999001",
                    "nama": "Dosen Testing",
                    "email": "dosentesting@hadirin.test",
                },
            ]
        ),
        program_studi_repo=FakeListRepo([{"kode": "D4-TI", "nama": "D4 Teknik Informatika"}]),
        ruangan_repo=FakeListRepo([{"kode": "J301", "nama": "Ruang J301"}]),
        sesi_kuliah_repo=FakeListRepo(
            [{"nomor": 1, "jam_mulai": "07:00:00", "jam_selesai": "07:50:00"}]
        ),
    )
    override(get_admin_options_service, lambda: service)

    master_service = AdminMasterDataService(
        tahun_ajaran_repo=FakeListRepo([{"id": "ta-1", "tahun": "2026/2027"}]),
        mata_kuliah_repo=FakeListRepo([]),
        dosen_repo=FakeListRepo(
            [
                {
                    "nip": "198501012010121001",
                    "nama": "Budi Santoso",
                    "email": "budi@polinema.ac.id",
                },
                {
                    "nip": "999999999001",
                    "nama": "Dosen Testing",
                    "email": "dosentesting@hadirin.test",
                },
            ]
        ),
        ruangan_repo=FakeListRepo([{"kode": "J301", "nama": "Ruang J301"}]),
    )
    override(get_admin_master_data_service, lambda: master_service)

    override(
        get_db_client,
        lambda: FakeSupabaseClient(
            {
                "tahun_ajaran": [{"id": "ta-1", "tahun": "2026/2027"}],
                "kelas": [
                    {
                        "id": "k-1",
                        "nama": "TI-1A",
                        "tingkat": 1,
                        "program_studi_kode": "D4-TI",
                        "tahun_ajaran_id": "ta-1",
                    },
                    {
                        "id": "k-2",
                        "nama": "PPLS-1A",
                        "tingkat": 1,
                        "program_studi_kode": "D2-PPLS",
                        "tahun_ajaran_id": "ta-1",
                    },
                ],
            }
        ),
    )
    return client


def test_dosen_options_include_testing_dosen_and_support_search(
    options_api: TestClient, admin_headers: dict[str, str]
) -> None:
    all_response = options_api.get("/admin/dosen", headers=admin_headers)
    assert all_response.status_code == 200, all_response.text
    assert all_response.json()["total"] == 2
    assert any(
        item["nip"] == "999999999001" and item["nama"] == "Dosen Testing"
        for item in all_response.json()["data"]
    )

    filtered = options_api.get(
        "/admin/dosen", params={"search": "dosentesting"}, headers=admin_headers
    )
    assert filtered.status_code == 200, filtered.text
    assert [item["nip"] for item in filtered.json()["data"]] == ["999999999001"]


def test_prodi_ruangan_and_sesi_options_are_exposed(
    options_api: TestClient, admin_headers: dict[str, str]
) -> None:
    prodi = options_api.get("/admin/program-studi", headers=admin_headers)
    ruangan = options_api.get("/admin/ruangan", headers=admin_headers)
    sesi = options_api.get("/admin/sesi-kuliah", headers=admin_headers)

    assert prodi.status_code == 200, prodi.text
    assert prodi.json()["data"] == [{"kode": "D4-TI", "nama": "D4 Teknik Informatika"}]
    assert ruangan.status_code == 200, ruangan.text
    assert ruangan.json()["data"] == [{"kode": "J301", "nama": "Ruang J301"}]
    assert sesi.status_code == 200, sesi.text
    assert sesi.json()["data"] == [
        {"nomor": 1, "jam_mulai": "07:00", "jam_selesai": "07:50"}
    ]


def test_kelas_endpoint_returns_metadata_and_applies_filters(
    options_api: TestClient,
) -> None:
    response = options_api.get(
        "/kelas", params={"tahun_ajaran": "2026/2027", "program_studi_kode": "d4-ti"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["data"][0] == {
        "id": "k-1",
        "nama": "TI-1A",
        "tingkat": 1,
        "program_studi_kode": "D4-TI",
        "tahun_ajaran_id": "ta-1",
    }

    unknown = options_api.get("/kelas", params={"tahun_ajaran": "2099/2100"})
    assert unknown.status_code == 200, unknown.text
    assert unknown.json() == {"data": [], "total": 0}


def test_admin_options_require_admin_role(
    options_api: TestClient,
    student_headers: dict[str, str],
    dosen_headers: dict[str, str],
) -> None:
    for path in ("/admin/dosen", "/admin/program-studi", "/admin/ruangan", "/admin/sesi-kuliah"):
        assert options_api.get(path).status_code == 401
        assert options_api.get(path, headers=student_headers).status_code == 403
        assert options_api.get(path, headers=dosen_headers).status_code == 403
