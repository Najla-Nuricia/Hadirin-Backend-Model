"""Integration tests for admin schedule management (create, list, update)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.session import get_supabase_client

BASE = "/admin/jadwal"


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tahun_ajaran": "2026/2027",
        "kelas": "TI-1A",
        "mata_kuliah_kode": "TI101",
        "dosen_nip": "197905052005011005",
        "ruangan_kode": "J302",
        "hari": "sabtu",
        "sesi_mulai": 1,
        "sesi_selesai": 2,
        "semester": "ganjil",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def admin_headers(client: TestClient, settings: Settings) -> dict[str, str]:
    """Login as the configured admin and return Bearer headers."""
    response = client.post(
        "/auth/admin/login",
        json={"username": settings.admin_username, "password": settings.admin_initial_password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def temp_jadwal(
    client: TestClient,
    admin_headers: dict[str, str],
    settings: Settings,
):
    """Create a real schedule on an unused slot and remove it on teardown."""
    response = client.post(BASE, json=_payload(), headers=admin_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    jadwal_id = body["data"]["id"]
    try:
        yield body
    finally:
        get_supabase_client(settings).table("jadwal_kuliah").delete().eq("id", jadwal_id).execute()


def test_create_jadwal_returns_201_with_normalized_data(
    client: TestClient,
    admin_headers: dict[str, str],
    temp_jadwal: dict[str, Any],
) -> None:
    data = temp_jadwal["data"]
    assert temp_jadwal["message"] == "Jadwal berhasil dibuat."
    assert data["hari"] == "sabtu"
    assert data["kelas_nama"] == "TI-1A"
    assert data["mata_kuliah_kode"] == "TI101"
    assert data["sesi_mulai"] == 1 and data["sesi_selesai"] == 2
    assert data["jam_mulai"] == "07:00"


def test_list_jadwal_filters_by_tahun_semester_tingkat_kelas(
    client: TestClient,
    admin_headers: dict[str, str],
    temp_jadwal: dict[str, Any],
) -> None:
    response = client.get(
        BASE,
        params={
            "tahun_ajaran": "2026/2027",
            "semester": "ganjil",
            "tingkat": 1,
            "kelas": "TI-1A",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == len(body["data"])
    assert body["filters"]["tahun_ajaran"] == "2026/2027"
    assert body["filters"]["semester"] == "ganjil"
    assert body["filters"]["tingkat"] == 1
    assert body["filters"]["kelas"] == "TI-1A"
    assert any(item["id"] == temp_jadwal["data"]["id"] for item in body["data"])
    assert all(item["kelas_nama"] == "TI-1A" for item in body["data"])


def test_update_jadwal_replaces_fields(
    client: TestClient,
    admin_headers: dict[str, str],
    temp_jadwal: dict[str, Any],
) -> None:
    jadwal_id = temp_jadwal["data"]["id"]
    response = client.put(
        f"{BASE}/{jadwal_id}",
        json=_payload(ruangan_kode="RT02", sesi_mulai=3, sesi_selesai=4),
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["message"] == "Jadwal berhasil diperbarui."
    assert body["data"]["ruangan_kode"] == "RT02"
    assert body["data"]["sesi_mulai"] == 3
    assert body["data"]["sesi_selesai"] == 4


def test_overlapping_class_schedule_is_rejected(
    client: TestClient,
    admin_headers: dict[str, str],
    temp_jadwal: dict[str, Any],
) -> None:
    response = client.post(
        BASE,
        json=_payload(
            dosen_nip="198703152012122002",
            ruangan_kode="J301",
            sesi_mulai=2,
            sesi_selesai=3,
        ),
        headers=admin_headers,
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "conflict"


def test_unknown_relation_is_rejected(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    response = client.post(
        BASE,
        json=_payload(dosen_nip="000000000000000000"),
        headers=admin_headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "bad_request"


def test_admin_jadwal_requires_admin_token(
    client: TestClient,
    seeded_auth_headers: dict[str, str],
) -> None:
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json=_payload()).status_code == 401
    assert client.get(BASE, headers=seeded_auth_headers).status_code == 403
