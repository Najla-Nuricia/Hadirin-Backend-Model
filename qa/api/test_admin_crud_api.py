"""API tests for admin CRUD of ruangan, dosen, and kelas."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_admin_master_data_service
from app.core.config import get_settings
from app.services.admin_master_data_service import AdminMasterDataService

from .conftest import (
    FakeAuthRepo,
    FakeDosenWriteRepo,
    FakeKelasRepo,
    FakeListRepo,
    FakeProgramStudiRepo,
    FakeRuanganRepo,
    FakeTahunAjaranRepo,
)

TAHUN_ID = "11111111-1111-1111-1111-111111111111"
KELAS_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def ruangan_repo() -> FakeRuanganRepo:
    return FakeRuanganRepo([{"kode": "J301", "nama": "Ruang J301"}])


@pytest.fixture
def dosen_repo() -> FakeDosenWriteRepo:
    return FakeDosenWriteRepo(
        [
            {
                "nip": "198501012010121001",
                "nama": "Budi Santoso",
                "email": "budi@polinema.ac.id",
                "no_hp": "081200000001",
                "auth_user_id": "auth-existing",
            }
        ]
    )


@pytest.fixture
def auth_repo() -> FakeAuthRepo:
    return FakeAuthRepo()


@pytest.fixture
def kelas_repo() -> FakeKelasRepo:
    return FakeKelasRepo(
        [
            {
                "id": KELAS_ID,
                "nama": "TI-1A",
                "tingkat": 1,
                "program_studi_kode": "D4-TI",
                "tahun_ajaran_id": TAHUN_ID,
                "kapasitas": 30,
                "status": "aktif",
            }
        ],
        program_studi={"D4-TI": "D4 Teknik Informatika"},
        tahun_ajaran={TAHUN_ID: "2026/2027"},
    )


@pytest.fixture
def program_studi_repo() -> FakeProgramStudiRepo:
    return FakeProgramStudiRepo([{"kode": "D4-TI", "nama": "D4 Teknik Informatika"}])


@pytest.fixture
def tahun_repo() -> FakeTahunAjaranRepo:
    return FakeTahunAjaranRepo([{"id": TAHUN_ID, "tahun": "2026/2027", "status": "aktif"}])


@pytest.fixture
def crud_api(
    client: TestClient,
    override,
    ruangan_repo: FakeRuanganRepo,
    dosen_repo: FakeDosenWriteRepo,
    auth_repo: FakeAuthRepo,
    kelas_repo: FakeKelasRepo,
    program_studi_repo: FakeProgramStudiRepo,
    tahun_repo: FakeTahunAjaranRepo,
) -> TestClient:
    service = AdminMasterDataService(
        tahun_ajaran_repo=tahun_repo,
        mata_kuliah_repo=FakeListRepo([]),
        ruangan_repo=ruangan_repo,
        dosen_repo=dosen_repo,
        kelas_repo=kelas_repo,
        program_studi_repo=program_studi_repo,
        auth_repo=auth_repo,
    )
    override(get_admin_master_data_service, lambda: service)
    return client


# ── Ruangan ────────────────────────────────────────────────────────────────


def test_ruangan_crud_roundtrip(crud_api: TestClient, admin_headers: dict[str, str]) -> None:
    listed = crud_api.get("/admin/ruangan", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    assert listed.json() == {
        "data": [{"kode": "J301", "nama": "Ruang J301"}],
        "total": 1,
    }

    created = crud_api.post(
        "/admin/ruangan", json={"kode": "j302", "nama": "  Ruang   J302 "}, headers=admin_headers
    )
    assert created.status_code == 201, created.text
    assert created.json() == {
        "message": "Ruangan berhasil dibuat.",
        "data": {"kode": "J302", "nama": "Ruang J302"},
    }

    detail = crud_api.get("/admin/ruangan/J302", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["nama"] == "Ruang J302"

    updated = crud_api.put(
        "/admin/ruangan/J302", json={"kode": "J302", "nama": "Lab J302"}, headers=admin_headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"] == {"kode": "J302", "nama": "Lab J302"}

    deleted = crud_api.delete("/admin/ruangan/J302", headers=admin_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"message": "Ruangan berhasil dihapus."}

    assert crud_api.get("/admin/ruangan/J302", headers=admin_headers).status_code == 404


def test_ruangan_duplicate_and_missing_return_409_and_404(
    crud_api: TestClient, admin_headers: dict[str, str]
) -> None:
    duplicate = crud_api.post(
        "/admin/ruangan", json={"kode": "J301", "nama": "Duplikat"}, headers=admin_headers
    )
    assert duplicate.status_code == 409, duplicate.text
    assert "sudah terdaftar" in duplicate.json()["detail"]

    missing = crud_api.put(
        "/admin/ruangan/ZZZ", json={"kode": "ZZZ", "nama": "Tidak Ada"}, headers=admin_headers
    )
    assert missing.status_code == 404, missing.text


def test_ruangan_in_use_cannot_be_deleted(
    client: TestClient, override, admin_headers: dict[str, str]
) -> None:
    service = AdminMasterDataService(
        tahun_ajaran_repo=FakeTahunAjaranRepo([]),
        mata_kuliah_repo=FakeListRepo([]),
        ruangan_repo=FakeRuanganRepo([{"kode": "J301", "nama": "Ruang J301"}], referenced=True),
    )
    override(get_admin_master_data_service, lambda: service)

    response = client.delete("/admin/ruangan/J301", headers=admin_headers)
    assert response.status_code == 409, response.text
    assert "jadwal kuliah" in response.json()["detail"]


def test_ruangan_payload_validation(crud_api: TestClient, admin_headers: dict[str, str]) -> None:
    blank = crud_api.post(
        "/admin/ruangan", json={"kode": "   ", "nama": "Ruang"}, headers=admin_headers
    )
    assert blank.status_code == 422, blank.text

    short_name = crud_api.post(
        "/admin/ruangan", json={"kode": "J999", "nama": "X"}, headers=admin_headers
    )
    assert short_name.status_code == 422, short_name.text


# ── Dosen ──────────────────────────────────────────────────────────────────


def test_create_dosen_uses_default_password_and_links_auth_user(
    crud_api: TestClient,
    admin_headers: dict[str, str],
    auth_repo: FakeAuthRepo,
    dosen_repo: FakeDosenWriteRepo,
) -> None:
    response = crud_api.post(
        "/admin/dosen",
        json={
            "nip": "199001012015011002",
            "nama": "Siti Aminah",
            "email": "siti@polinema.ac.id",
            "no_hp": "081200000002",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["message"] == "Dosen berhasil dibuat."
    assert body["initial_password"] == get_settings().dosen_initial_password
    assert body["initial_password"] == "dosen123"
    assert body["data"]["nip"] == "199001012015011002"
    assert body["data"]["auth_user_id"] == "auth-1"

    assert auth_repo.created == [
        {
            "auth_user_id": "auth-1",
            "email": "siti@polinema.ac.id",
            "password": "dosen123",
            "user_metadata": {
                "nip": "199001012015011002",
                "nama": "Siti Aminah",
                "peran": "dosen",
            },
        }
    ]
    assert auth_repo.linked == [("auth-1", "199001012015011002")]
    assert dosen_repo.get_by_nip("199001012015011002") is not None


def test_create_dosen_without_email_uses_synthetic_address(
    crud_api: TestClient, admin_headers: dict[str, str], auth_repo: FakeAuthRepo
) -> None:
    response = crud_api.post(
        "/admin/dosen",
        json={"nip": "199001012015011003", "nama": "Tanpa Email"},
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text
    assert auth_repo.created[0]["email"] == "199001012015011003@hadirin.local"
    assert response.json()["data"].get("email") is None


def test_create_dosen_rolls_back_auth_user_when_insert_fails(
    client: TestClient,
    override,
    admin_headers: dict[str, str],
    auth_repo: FakeAuthRepo,
) -> None:
    service = AdminMasterDataService(
        tahun_ajaran_repo=FakeTahunAjaranRepo([]),
        mata_kuliah_repo=FakeListRepo([]),
        dosen_repo=FakeDosenWriteRepo(fail_on_create=True),
        auth_repo=auth_repo,
    )
    override(get_admin_master_data_service, lambda: service)

    response = client.post(
        "/admin/dosen",
        json={"nip": "199001012015011004", "nama": "Gagal Simpan"},
        headers=admin_headers,
    )

    assert response.status_code == 502, response.text
    assert len(auth_repo.created) == 1
    assert auth_repo.deleted == ["auth-1"]
    assert auth_repo.linked == []


def test_dosen_crud_roundtrip(crud_api: TestClient, admin_headers: dict[str, str]) -> None:
    listed = crud_api.get("/admin/dosen", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1

    filtered = crud_api.get(
        "/admin/dosen", params={"search": "budi"}, headers=admin_headers
    )
    assert filtered.status_code == 200, filtered.text
    assert [item["nip"] for item in filtered.json()["data"]] == ["198501012010121001"]

    updated = crud_api.put(
        "/admin/dosen/198501012010121001",
        json={
            "nip": "198501012010121001",
            "nama": "Budi Santoso, M.Kom.",
            "email": "budi.santoso@polinema.ac.id",
            "no_hp": "081200000009",
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["nama"] == "Budi Santoso, M.Kom."
    assert updated.json().get("initial_password") is None

    deleted = crud_api.delete("/admin/dosen/198501012010121001", headers=admin_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"message": "Dosen berhasil dihapus."}
    assert crud_api.get("/admin/dosen/198501012010121001", headers=admin_headers).status_code == 404


def test_dosen_update_syncs_auth_email(
    crud_api: TestClient, admin_headers: dict[str, str], auth_repo: FakeAuthRepo
) -> None:
    response = crud_api.put(
        "/admin/dosen/198501012010121001",
        json={
            "nip": "198501012010121001",
            "nama": "Budi Santoso",
            "email": "budi.baru@polinema.ac.id",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert auth_repo.updated_emails == [("auth-existing", "budi.baru@polinema.ac.id")]


def test_dosen_duplicate_nip_and_email_conflict(
    crud_api: TestClient, admin_headers: dict[str, str]
) -> None:
    duplicate_nip = crud_api.post(
        "/admin/dosen",
        json={"nip": "198501012010121001", "nama": "Duplikat"},
        headers=admin_headers,
    )
    assert duplicate_nip.status_code == 409, duplicate_nip.text

    duplicate_email = crud_api.post(
        "/admin/dosen",
        json={"nip": "199001012015011005", "nama": "Email Sama", "email": "budi@polinema.ac.id"},
        headers=admin_headers,
    )
    assert duplicate_email.status_code == 409, duplicate_email.text
    assert "sudah digunakan" in duplicate_email.json()["detail"]


def test_dosen_in_use_cannot_be_deleted(
    client: TestClient, override, admin_headers: dict[str, str], auth_repo: FakeAuthRepo
) -> None:
    service = AdminMasterDataService(
        tahun_ajaran_repo=FakeTahunAjaranRepo([]),
        mata_kuliah_repo=FakeListRepo([]),
        dosen_repo=FakeDosenWriteRepo(
            [
                {
                    "nip": "198501012010121001",
                    "nama": "Budi Santoso",
                    "email": "budi@polinema.ac.id",
                    "auth_user_id": "auth-existing",
                }
            ],
            referenced=True,
        ),
        auth_repo=auth_repo,
    )
    override(get_admin_master_data_service, lambda: service)

    response = client.delete("/admin/dosen/198501012010121001", headers=admin_headers)
    assert response.status_code == 409, response.text
    assert auth_repo.deleted == []


def test_dosen_invalid_email_returns_422(
    crud_api: TestClient, admin_headers: dict[str, str]
) -> None:
    response = crud_api.post(
        "/admin/dosen",
        json={"nip": "199001012015011006", "nama": "Email Salah", "email": "bukan-email"},
        headers=admin_headers,
    )
    assert response.status_code == 422, response.text


# ── Kelas ──────────────────────────────────────────────────────────────────


def test_kelas_crud_roundtrip(crud_api: TestClient, admin_headers: dict[str, str]) -> None:
    listed = crud_api.get("/admin/kelas", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 1
    assert body["data"][0] == {
        "id": KELAS_ID,
        "nama": "TI-1A",
        "tingkat": 1,
        "program_studi_kode": "D4-TI",
        "tahun_ajaran_id": TAHUN_ID,
        "kapasitas": 30,
        "status": "aktif",
        "program_studi_nama": "D4 Teknik Informatika",
        "tahun_ajaran_tahun": "2026/2027",
    }

    created = crud_api.post(
        "/admin/kelas",
        json={
            "nama": "ti-1b",
            "tingkat": 1,
            "program_studi_kode": "d4-ti",
            "tahun_ajaran_id": TAHUN_ID,
            "kapasitas": 32,
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["message"] == "Kelas berhasil dibuat."
    assert created_body["data"]["nama"] == "TI-1B"
    assert created_body["data"]["status"] == "aktif"
    new_id = created_body["data"]["id"]

    detail = crud_api.get(f"/admin/kelas/{new_id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["program_studi_nama"] == "D4 Teknik Informatika"

    updated = crud_api.put(
        f"/admin/kelas/{new_id}",
        json={
            "nama": "TI-1B",
            "tingkat": 1,
            "program_studi_kode": "D4-TI",
            "tahun_ajaran_id": TAHUN_ID,
            "kapasitas": 40,
            "status": "non_aktif",
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["kapasitas"] == 40
    assert updated.json()["data"]["status"] == "non_aktif"

    deleted = crud_api.delete(f"/admin/kelas/{new_id}", headers=admin_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"message": "Kelas berhasil dihapus."}


def test_kelas_filters_by_prodi_tahun_and_status(
    crud_api: TestClient, admin_headers: dict[str, str]
) -> None:
    matching = crud_api.get(
        "/admin/kelas",
        params={"program_studi_kode": "d4-ti", "tahun_ajaran_id": TAHUN_ID, "status": "aktif"},
        headers=admin_headers,
    )
    assert matching.status_code == 200, matching.text
    assert matching.json()["total"] == 1

    empty = crud_api.get(
        "/admin/kelas", params={"status": "non_aktif"}, headers=admin_headers
    )
    assert empty.status_code == 200, empty.text
    assert empty.json() == {"data": [], "total": 0}


def test_kelas_duplicate_name_in_same_year_conflicts(
    crud_api: TestClient, admin_headers: dict[str, str]
) -> None:
    response = crud_api.post(
        "/admin/kelas",
        json={
            "nama": "TI-1A",
            "tingkat": 1,
            "program_studi_kode": "D4-TI",
            "tahun_ajaran_id": TAHUN_ID,
        },
        headers=admin_headers,
    )
    assert response.status_code == 409, response.text
    assert "sudah terdaftar" in response.json()["detail"]


def test_kelas_unknown_foreign_keys_return_404(
    crud_api: TestClient, admin_headers: dict[str, str]
) -> None:
    unknown_tahun = crud_api.post(
        "/admin/kelas",
        json={
            "nama": "TI-2A",
            "tingkat": 2,
            "program_studi_kode": "D4-TI",
            "tahun_ajaran_id": "33333333-3333-3333-3333-333333333333",
        },
        headers=admin_headers,
    )
    assert unknown_tahun.status_code == 404, unknown_tahun.text
    assert "Tahun ajaran" in unknown_tahun.json()["detail"]

    unknown_prodi = crud_api.post(
        "/admin/kelas",
        json={
            "nama": "TI-2A",
            "tingkat": 2,
            "program_studi_kode": "D4-SI",
            "tahun_ajaran_id": TAHUN_ID,
        },
        headers=admin_headers,
    )
    assert unknown_prodi.status_code == 404, unknown_prodi.text
    assert "Program studi" in unknown_prodi.json()["detail"]


def test_kelas_in_use_cannot_be_deleted(
    client: TestClient, override, admin_headers: dict[str, str]
) -> None:
    service = AdminMasterDataService(
        tahun_ajaran_repo=FakeTahunAjaranRepo([{"id": TAHUN_ID, "tahun": "2026/2027"}]),
        mata_kuliah_repo=FakeListRepo([]),
        kelas_repo=FakeKelasRepo(
            [
                {
                    "id": KELAS_ID,
                    "nama": "TI-1A",
                    "tingkat": 1,
                    "program_studi_kode": "D4-TI",
                    "tahun_ajaran_id": TAHUN_ID,
                    "kapasitas": 30,
                    "status": "aktif",
                }
            ],
            referenced=True,
        ),
        program_studi_repo=FakeProgramStudiRepo([{"kode": "D4-TI", "nama": "D4 TI"}]),
    )
    override(get_admin_master_data_service, lambda: service)

    response = client.delete(f"/admin/kelas/{KELAS_ID}", headers=admin_headers)
    assert response.status_code == 409, response.text
    assert "jadwal kuliah atau mahasiswa" in response.json()["detail"]


def test_kelas_payload_validation(crud_api: TestClient, admin_headers: dict[str, str]) -> None:
    bad_tingkat = crud_api.post(
        "/admin/kelas",
        json={
            "nama": "TI-9A",
            "tingkat": 9,
            "program_studi_kode": "D4-TI",
            "tahun_ajaran_id": TAHUN_ID,
        },
        headers=admin_headers,
    )
    assert bad_tingkat.status_code == 422, bad_tingkat.text

    bad_status = crud_api.post(
        "/admin/kelas",
        json={
            "nama": "TI-3A",
            "tingkat": 3,
            "program_studi_kode": "D4-TI",
            "tahun_ajaran_id": TAHUN_ID,
            "status": "libur",
        },
        headers=admin_headers,
    )
    assert bad_status.status_code == 422, bad_status.text


# ── Authorization ──────────────────────────────────────────────────────────


def test_crud_endpoints_require_admin_role(
    crud_api: TestClient,
    student_headers: dict[str, str],
    dosen_headers: dict[str, str],
) -> None:
    paths = (
        "/admin/ruangan",
        "/admin/ruangan/J301",
        "/admin/dosen",
        "/admin/dosen/198501012010121001",
        "/admin/kelas",
        f"/admin/kelas/{KELAS_ID}",
    )
    for path in paths:
        assert crud_api.get(path).status_code == 401
        assert crud_api.get(path, headers=student_headers).status_code == 403
        assert crud_api.get(path, headers=dosen_headers).status_code == 403

    assert (
        crud_api.post(
            "/admin/kelas", json={"nama": "X"}, headers=student_headers
        ).status_code
        == 403
    )
    assert (
        crud_api.delete("/admin/ruangan/J301", headers=dosen_headers).status_code == 403
    )
