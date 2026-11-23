"""Integration tests for admin academic master-data CRUD."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings


def _admin_login(client: TestClient, settings: Settings) -> dict[str, str]:
    response = client.post(
        "/auth/admin/login",
        json={
            "username": settings.admin_username,
            "password": settings.admin_initial_password,
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _unused_year(client: TestClient, headers: dict[str, str]) -> str:
    response = client.get("/admin/tahun-ajaran", headers=headers)
    assert response.status_code == 200, response.text
    existing = {item["tahun"] for item in response.json()["data"]}
    for year in range(2090, 2100):
        candidate = f"{year}/{year + 1}"
        if candidate not in existing:
            return candidate
    pytest.fail("Tidak tersedia tahun ajaran test yang belum digunakan.")


@pytest.fixture
def admin_headers(client: TestClient, settings: Settings) -> dict[str, str]:
    return _admin_login(client, settings)


def test_admin_tahun_ajaran_crud(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    tahun = _unused_year(client, admin_headers)
    payload: dict[str, Any] = {
        "tahun": tahun,
        "status": "non_aktif",
        "semester_ganjil": True,
        "semester_genap": True,
        "tanggal_mulai": "2090-09-01",
        "tanggal_selesai": "2091-08-31",
    }
    created_id: str | None = None
    try:
        created = client.post("/admin/tahun-ajaran", json=payload, headers=admin_headers)
        assert created.status_code == 201, created.text
        body = created.json()
        created_id = body["data"]["id"]
        assert body["data"]["tahun"] == tahun

        fetched = client.get(f"/admin/tahun-ajaran/{created_id}", headers=admin_headers)
        assert fetched.status_code == 200, fetched.text

        updated = client.put(
            f"/admin/tahun-ajaran/{created_id}",
            json={**payload, "tanggal_selesai": "2091-09-01"},
            headers=admin_headers,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["data"]["tanggal_selesai"] == "2091-09-01"
    finally:
        if created_id:
            deleted = client.delete(
                f"/admin/tahun-ajaran/{created_id}", headers=admin_headers
            )
            assert deleted.status_code == 200, deleted.text


def test_admin_mata_kuliah_crud(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    kode = f"ZZ{uuid4().hex[:10].upper()}"
    payload = {"kode": kode, "nama": "Mata Kuliah Test", "semester": 5, "sks": 3}
    try:
        created = client.post("/admin/mata-kuliah", json=payload, headers=admin_headers)
        assert created.status_code == 201, created.text
        assert created.json()["data"]["kode"] == kode

        fetched = client.get(f"/admin/mata-kuliah/{kode.lower()}", headers=admin_headers)
        assert fetched.status_code == 200, fetched.text

        updated = client.put(
            f"/admin/mata-kuliah/{kode}",
            json={**payload, "nama": "Mata Kuliah Test Updated", "sks": 4},
            headers=admin_headers,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["data"]["sks"] == 4
    finally:
        deleted = client.delete(f"/admin/mata-kuliah/{kode}", headers=admin_headers)
        assert deleted.status_code == 200, deleted.text


def test_admin_master_data_requires_admin_token(client: TestClient) -> None:
    assert client.get("/admin/tahun-ajaran").status_code == 401
    assert client.get("/admin/mata-kuliah").status_code == 401
