"""Unit tests for whitelist NIM validation and business rules."""

import pytest
from pydantic import ValidationError

from app.core.exceptions import ConflictError
from app.schemas.whitelist_nim import WhitelistNimWriteRequest
from app.services.whitelist_nim_service import WhitelistNimService


class FakeWhitelistRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.students: set[str] = set()

    def list_all(self, search=None):
        return list(self.rows.values())

    def get_by_nim(self, nim):
        return self.rows.get(nim)

    def create(self, nim):
        if nim in self.rows:
            raise ConflictError("duplicate")
        row = {"nim": nim, "mahasiswa": None}
        self.rows[nim] = row
        return row

    def update(self, old_nim, new_nim):
        row = self.rows.pop(old_nim)
        row["nim"] = new_nim
        self.rows[new_nim] = row
        return row

    def has_student(self, nim):
        return nim in self.students

    def delete(self, nim):
        del self.rows[nim]


def test_whitelist_nim_normalizes_and_rejects_non_digits() -> None:
    assert WhitelistNimWriteRequest(nim=" 2341720001 ").nim == "2341720001"
    with pytest.raises(ValidationError):
        WhitelistNimWriteRequest(nim="TI-2341720001")


def test_whitelist_service_create_and_status() -> None:
    repository = FakeWhitelistRepository()
    service = WhitelistNimService(repository)
    created = service.create(WhitelistNimWriteRequest(nim="2341720001"))

    assert created.data.status == "Belum Registrasi"
    repository.students.add("2341720001")
    repository.rows["2341720001"]["mahasiswa"] = {
        "nama_lengkap": "Budi",
        "kelas": {"nama": "TI-3A"},
    }
    assert service.list().data[0].status == "Sudah Registrasi"


def test_registered_nim_cannot_be_updated_or_deleted() -> None:
    repository = FakeWhitelistRepository()
    repository.rows["2341720001"] = {"nim": "2341720001", "mahasiswa": None}
    repository.students.add("2341720001")
    service = WhitelistNimService(repository)

    with pytest.raises(ConflictError):
        service.update("2341720001", WhitelistNimWriteRequest(nim="2341720002"))
    with pytest.raises(ConflictError):
        service.delete("2341720001")
