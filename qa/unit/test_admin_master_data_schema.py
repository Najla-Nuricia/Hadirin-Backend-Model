"""Unit tests for admin master-data request validation."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.admin_master_data import (
    AdminMataKuliahWriteRequest,
    AdminTahunAjaranWriteRequest,
)


def test_tahun_ajaran_normalizes_year_and_status() -> None:
    payload = AdminTahunAjaranWriteRequest(
        tahun=" 2026/2027 ",
        status="non-aktif",
        tanggal_mulai=date(2026, 9, 1),
        tanggal_selesai=date(2027, 8, 31),
    )

    assert payload.tahun == "2026/2027"
    assert payload.status == "non_aktif"


@pytest.mark.parametrize(
    "overrides",
    [
        {"tahun": "2026-2027"},
        {"tahun": "2026/2028"},
        {"semester_ganjil": False, "semester_genap": False},
        {"tanggal_mulai": date(2027, 1, 1), "tanggal_selesai": date(2026, 1, 1)},
    ],
)
def test_tahun_ajaran_rejects_invalid_values(overrides: dict[str, object]) -> None:
    base: dict[str, object] = {"tahun": "2026/2027"}
    base.update(overrides)

    with pytest.raises(ValidationError):
        AdminTahunAjaranWriteRequest(**base)


def test_mata_kuliah_normalizes_code_and_name() -> None:
    payload = AdminMataKuliahWriteRequest(
        kode=" ti101 ", nama="  Basis   Data ", semester=3, sks=3
    )

    assert payload.kode == "TI101"
    assert payload.nama == "Basis Data"


@pytest.mark.parametrize(
    "overrides",
    [{"semester": 0}, {"semester": 9}, {"sks": 0}, {"kode": ""}],
)
def test_mata_kuliah_rejects_invalid_values(overrides: dict[str, object]) -> None:
    base: dict[str, object] = {"kode": "TI101", "nama": "Basis Data", "semester": 3, "sks": 3}
    base.update(overrides)

    with pytest.raises(ValidationError):
        AdminMataKuliahWriteRequest(**base)
