"""API tests for the public /auth/check-nim/{nim} status endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_mahasiswa_repository, get_whitelist_nim_repository

from .conftest import FakeStudentRepo, FakeWhitelistRepo


def test_whitelisted_unregistered_nim_can_register(
    client: TestClient, override
) -> None:
    override(get_whitelist_nim_repository, lambda: FakeWhitelistRepo(nims=["99887766"]))
    override(get_mahasiswa_repository, lambda: FakeStudentRepo())

    response = client.get("/auth/check-nim/99887766")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "nim": "99887766",
        "whitelisted": True,
        "registered": False,
        "can_register": True,
        "status": "siap_registrasi",
    }


def test_whitelisted_registered_nim_is_reported_as_registered(
    client: TestClient, override
) -> None:
    override(get_whitelist_nim_repository, lambda: FakeWhitelistRepo(nims=["99887766"]))
    override(
        get_mahasiswa_repository,
        lambda: FakeStudentRepo({"99887766": {"nim": "99887766", "nama_lengkap": "Najla"}}),
    )

    response = client.get("/auth/check-nim/99887766")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["registered"] is True
    assert body["can_register"] is False
    assert body["status"] == "sudah_terdaftar"


def test_non_whitelisted_nim_reports_belum_whitelist(
    client: TestClient, override
) -> None:
    override(get_whitelist_nim_repository, lambda: FakeWhitelistRepo())
    override(
        get_mahasiswa_repository,
        lambda: FakeStudentRepo({"99887766": {"nim": "99887766"}}),
    )

    response = client.get("/auth/check-nim/99887766")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "belum_whitelist"
    assert response.json()["can_register"] is False
