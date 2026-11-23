"""New business-rule scenarios for admin schedule creation (isolated DB)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_admin_jadwal_service
from app.services.admin_jadwal_service import AdminJadwalService

from .conftest import FakeDosenRepo, FakeJadwalRepo, FakeMahasiswaRepo


BASE_PAYLOAD: dict[str, Any] = {
    "tahun_ajaran": "2026/2027",
    "kelas": "TI-1A",
    "mata_kuliah_kode": "TI101",
    "dosen_nip": "999999999001",
    "ruangan_kode": "J301",
    "hari": "senin",
    "sesi_mulai": 1,
    "sesi_selesai": 2,
    "semester": "ganjil",
}


@pytest.fixture
def jadwal_repo() -> FakeJadwalRepo:
    return FakeJadwalRepo()


@pytest.fixture
def jadwal_api(
    client: TestClient,
    override,
    jadwal_repo: FakeJadwalRepo,
) -> TestClient:
    service = AdminJadwalService(
        jadwal_repo=jadwal_repo,
        mahasiswa_repo=FakeMahasiswaRepo(),
        dosen_repo=FakeDosenRepo(),
    )
    override(get_admin_jadwal_service, lambda: service)
    return client


def test_mata_kuliah_semester_mismatch_returns_400(
    jadwal_api: TestClient, admin_headers: dict[str, str]
) -> None:
    response = jadwal_api.post(
        "/admin/jadwal",
        json={**BASE_PAYLOAD, "mata_kuliah_kode": "TI201"},
        headers=admin_headers,
    )

    assert response.status_code == 400, response.text
    assert "tidak sesuai dengan periode" in response.json()["detail"]


def test_ruangan_conflict_returns_409(
    client: TestClient,
    override,
    admin_headers: dict[str, str],
) -> None:
    conflict = {
        "id": "existing-1",
        "kelas_id": "kelas-lain",
        "dosen_nip": "198501012010121001",
        "ruangan_kode": "J302",
        "hari": "senin",
        "sesi_mulai": 1,
        "sesi_selesai": 2,
    }
    service = AdminJadwalService(
        jadwal_repo=FakeJadwalRepo(conflicts=[conflict]),
        mahasiswa_repo=FakeMahasiswaRepo(),
        dosen_repo=FakeDosenRepo(),
    )
    override(get_admin_jadwal_service, lambda: service)

    response = client.post(
        "/admin/jadwal",
        json={**BASE_PAYLOAD, "ruangan_kode": "J302"},
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text
    assert "Ruangan Ruang J302 sudah digunakan" in response.json()["detail"]


def test_missing_sesi_returns_400(
    client: TestClient,
    override,
    admin_headers: dict[str, str],
) -> None:
    service = AdminJadwalService(
        jadwal_repo=FakeJadwalRepo(sesi=[{"nomor": 1, "jam_mulai": "07:00:00", "jam_selesai": "07:50:00"}]),
        mahasiswa_repo=FakeMahasiswaRepo(),
        dosen_repo=FakeDosenRepo(),
    )
    override(get_admin_jadwal_service, lambda: service)

    response = client.post(
        "/admin/jadwal",
        json={**BASE_PAYLOAD, "sesi_mulai": 12, "sesi_selesai": 12},
        headers=admin_headers,
    )

    assert response.status_code == 400, response.text
    assert "Sesi ke-12 tidak ditemukan" in response.json()["detail"]


def test_invalid_payload_and_non_admin_role_are_rejected(
    jadwal_api: TestClient,
    admin_headers: dict[str, str],
    dosen_headers: dict[str, str],
) -> None:
    invalid = jadwal_api.post(
        "/admin/jadwal",
        json={**BASE_PAYLOAD, "hari": "minggu"},
        headers=admin_headers,
    )
    assert invalid.status_code == 422, invalid.text

    forbidden = jadwal_api.post(
        "/admin/jadwal", json=BASE_PAYLOAD, headers=dosen_headers
    )
    assert forbidden.status_code == 403, forbidden.text
