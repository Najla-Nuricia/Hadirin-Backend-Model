"""Isolated API-test fixtures.

The suites in ``qa/api`` never touch the development/production Supabase
project. They inject in-memory fake repositories through FastAPI dependency
overrides, which acts as a separate deterministic test database. Requests are
still exercised end-to-end through ``TestClient`` including routing, Pydantic
validation, JWT auth and role checks.
"""

from typing import Any, Callable
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_admin_master_data_service,
    get_admin_options_service,
    get_auth_repository,
    get_db_client,
    get_jadwal_repository,
    get_mahasiswa_repository,
    get_mata_kuliah_repository,
    get_tahun_ajaran_repository,
    get_whitelist_nim_repository,
)
from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, ExternalServiceError
from app.core.security import create_access_token
from app.main import app


# ── Generic in-memory query builder used by the fake Supabase client ──────


class FakeQuery:
    """Minimal chainable stand-in for a Supabase table query."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._filters: list[tuple[str, Any, str]] = []
        self._limit: int | None = None

    def select(self, *args: Any, **kwargs: Any) -> "FakeQuery":
        return self

    def eq(self, key: str, value: Any) -> "FakeQuery":
        self._filters.append((key, value, "eq"))
        return self

    def ilike(self, key: str, pattern: str) -> "FakeQuery":
        self._filters.append((key, pattern.strip("%"), "ilike"))
        return self

    def order(self, key: str, **kwargs: Any) -> "FakeQuery":
        return self

    def limit(self, value: int) -> "FakeQuery":
        self._limit = value
        return self

    def execute(self) -> SimpleNamespace:
        rows = self._rows
        for key, value, mode in self._filters:
            if mode == "eq":
                rows = [row for row in rows if str(row.get(key)) == str(value)]
            else:
                needle = str(value).lower()
                rows = [row for row in rows if needle in str(row.get(key) or "").lower()]
        if self._limit is not None:
            rows = rows[: self._limit]
        return SimpleNamespace(data=[dict(row) for row in rows])


class FakeSupabaseClient:
    """Fake client returning preloaded rows per table (read-only)."""

    def __init__(self, tables: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.tables = tables or {}

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self.tables.get(name, []))


# ── Repository fakes ───────────────────────────────────────────────────────


class FakeListRepo:
    """Read-only repo for dosen/prodi/ruangan/sesi option lists."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def list_all(self, search: str | None = None) -> list[dict[str, Any]]:
        if not search or not search.strip():
            return [dict(row) for row in self.rows]
        term = search.strip().lower()
        return [
            dict(row)
            for row in self.rows
            if any(term in str(value).lower() for value in row.values())
        ]


class FakeWhitelistRepo:
    """In-memory whitelist with a separate in-memory mahasiswa relation."""

    def __init__(
        self,
        nims: list[str] | None = None,
        students: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.rows = {nim: {"nim": nim} for nim in (nims or [])}
        self.students = students or {}

    def _enrich(self, nim: str, row: dict[str, Any]) -> dict[str, Any]:
        return {**row, "mahasiswa": self.students.get(nim)}

    def list_all(self, search: str | None = None) -> list[dict[str, Any]]:
        rows = [self._enrich(nim, row) for nim, row in self.rows.items()]
        if search and search.strip():
            rows = [row for row in rows if search.strip() in row["nim"]]
        return rows

    def get_by_nim(self, nim: str) -> dict[str, Any] | None:
        row = self.rows.get(nim)
        return self._enrich(nim, row) if row else None

    def create(self, nim: str) -> dict[str, Any]:
        if nim in self.rows:
            raise ConflictError("duplicate")
        self.rows[nim] = {"nim": nim}
        return self.get_by_nim(nim) or {}

    def update(self, old_nim: str, new_nim: str) -> dict[str, Any] | None:
        row = self.rows.pop(old_nim, None)
        if row is None:
            return None
        self.rows[new_nim] = row
        return self.get_by_nim(new_nim)

    def has_student(self, nim: str) -> bool:
        return nim in self.students

    def delete(self, nim: str) -> None:
        self.rows.pop(nim, None)


class FakeStudentRepo:
    """Student lookup used by ``/auth/check-nim``."""

    def __init__(self, students: dict[str, dict[str, Any]] | None = None) -> None:
        self.students = students or {}

    def get_by_nim(self, nim: str) -> dict[str, Any] | None:
        return self.students.get(nim)


class FakeTahunAjaranRepo:
    def __init__(self, rows: list[dict[str, Any]] | None = None, referenced: bool = False) -> None:
        self.rows = [dict(row) for row in (rows or [])]
        self.referenced = referenced

    def list_all(self, search: str | None = None) -> list[dict[str, Any]]:
        rows = self.rows
        if search and search.strip():
            rows = [row for row in rows if search.strip() in row["tahun"]]
        return [dict(row) for row in rows]

    def get_by_id(self, item_id: str) -> dict[str, Any] | None:
        return next((row for row in self.rows if row["id"] == item_id), None)

    def get_by_tahun(self, tahun: str) -> dict[str, Any] | None:
        return next((row for row in self.rows if row["tahun"] == tahun), None)

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        row = {"id": f"generated-{len(self.rows) + 1}", **fields}
        self.rows.append(row)
        return row

    def update(self, item_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        row = self.get_by_id(item_id)
        if row:
            row.update(fields)
        return row

    def has_references(self, item_id: str) -> bool:
        return self.referenced

    def delete(self, item_id: str) -> None:
        self.rows = [row for row in self.rows if row["id"] != item_id]


class FakeMataKuliahRepo:
    def __init__(self, rows: list[dict[str, Any]] | None = None, referenced: bool = False) -> None:
        self.rows = [dict(row) for row in (rows or [])]
        self.referenced = referenced

    def list_all(self, search: str | None = None) -> list[dict[str, Any]]:
        rows = self.rows
        if search and search.strip():
            term = search.strip().lower()
            rows = [
                row
                for row in rows
                if term in row["kode"].lower() or term in row["nama"].lower()
            ]
        return [dict(row) for row in rows]

    def get_by_kode(self, kode: str) -> dict[str, Any] | None:
        return next((row for row in self.rows if row["kode"] == kode), None)

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        self.rows.append(dict(fields))
        return dict(fields)

    def update(self, kode: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        row = self.get_by_kode(kode)
        if row:
            row.update(fields)
        return row

    def has_references(self, kode: str) -> bool:
        return self.referenced

    def delete(self, kode: str) -> None:
        self.rows = [row for row in self.rows if row["kode"] != kode]


class FakeJadwalRepo:
    """Read side of ``JadwalRepository`` used by admin business validation."""

    def __init__(
        self,
        *,
        tahun: dict[str, Any] | None = None,
        matkul: list[dict[str, Any]] | None = None,
        ruangan: list[dict[str, Any]] | None = None,
        sesi: list[dict[str, Any]] | None = None,
        conflicts: list[dict[str, Any]] | None = None,
    ) -> None:
        self.tahun = tahun or {
            "id": "ta-1",
            "tahun": "2026/2027",
            "status": "aktif",
            "semester_ganjil": True,
            "semester_genap": True,
        }
        self.matkul = matkul or [
            {"kode": "TI101", "nama": "Matematika Dasar", "semester": 1, "sks": 2},
            {"kode": "TI201", "nama": "Struktur Data", "semester": 2, "sks": 3},
        ]
        self.ruangan = ruangan or [
            {"kode": "J301", "nama": "Ruang J301"},
            {"kode": "J302", "nama": "Ruang J302"},
        ]
        self.sesi = sesi if sesi is not None else [
            {
                "nomor": nomor,
                "jam_mulai": f"{6 + nomor:02d}:00:00",
                "jam_selesai": f"{7 + nomor:02d}:00:00",
            }
            for nomor in range(1, 13)
        ]
        self.conflicts = conflicts or []

    def get_tahun_ajaran(self, value: str) -> dict[str, Any] | None:
        if value.strip() in (self.tahun["id"], self.tahun["tahun"]):
            return self.tahun
        return None

    def get_mata_kuliah(self, kode: str) -> dict[str, Any] | None:
        return next((row for row in self.matkul if row["kode"].lower() == kode.strip().lower()), None)

    def get_ruangan(self, kode: str) -> dict[str, Any] | None:
        return next((row for row in self.ruangan if row["kode"].lower() == kode.strip().lower()), None)

    def get_sesi(self, nomor: int) -> dict[str, Any] | None:
        return next((row for row in self.sesi if row["nomor"] == nomor), None)

    def list_sesi(self) -> list[dict[str, Any]]:
        return self.sesi

    def find_potential_conflicts(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.conflicts

    def admin_list(self, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    def admin_get_by_id(self, jadwal_id: str) -> dict[str, Any] | None:
        return None

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def update(self, jadwal_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        return None


class FakeMahasiswaRepo:
    """Class lookup side of ``MahasiswaRepository`` for admin schedule checks."""

    def get_kelas_by_name(self, nama: str) -> dict[str, Any] | None:
        if nama.strip().upper() != "TI-1A":
            return None
        return {
            "id": "kelas-1",
            "nama": "TI-1A",
            "tingkat": 1,
            "program_studi_kode": "D4-TI",
            "tahun_ajaran_id": "ta-1",
        }

    def get_kelas_by_id(self, kelas_id: str) -> dict[str, Any] | None:
        return self.get_kelas_by_name("TI-1A") if kelas_id == "kelas-1" else None

    def get_by_nim(self, nim: str) -> dict[str, Any] | None:
        return None


class FakeDosenRepo:
    def get_by_nip(self, nip: str) -> dict[str, Any] | None:
        if nip.strip() != "999999999001":
            return None
        return {"nip": "999999999001", "nama": "Dosen Testing", "email": "dosentesting@hadirin.test"}


class FakeRuanganRepo:
    """In-memory ``RuanganRepository`` covering the full CRUD surface."""

    def __init__(
        self, rows: list[dict[str, Any]] | None = None, referenced: bool = False
    ) -> None:
        self.rows = [dict(row) for row in (rows or [])]
        self.referenced = referenced

    def list_all(self, search: str | None = None) -> list[dict[str, Any]]:
        rows = self.rows
        if search and search.strip():
            term = search.strip().lower()
            rows = [
                row
                for row in rows
                if term in row["kode"].lower() or term in row["nama"].lower()
            ]
        return [dict(row) for row in rows]

    def get_by_kode(self, kode: str) -> dict[str, Any] | None:
        return next((row for row in self.rows if row["kode"] == kode), None)

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        self.rows.append(dict(fields))
        return dict(fields)

    def update(self, kode: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        row = self.get_by_kode(kode)
        if row is None:
            return None
        row.update(fields)
        return dict(row)

    def has_references(self, kode: str) -> bool:
        return self.referenced

    def delete(self, kode: str) -> None:
        self.rows = [row for row in self.rows if row["kode"] != kode]


class FakeDosenWriteRepo:
    """In-memory ``DosenRepository`` covering the full CRUD surface."""

    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        referenced: bool = False,
        fail_on_create: bool = False,
    ) -> None:
        self.rows = [dict(row) for row in (rows or [])]
        self.referenced = referenced
        self.fail_on_create = fail_on_create

    def list_all(self, search: str | None = None) -> list[dict[str, Any]]:
        rows = self.rows
        if search and search.strip():
            term = search.strip().lower()
            rows = [
                row
                for row in rows
                if term in str(row.get("nama") or "").lower()
                or term in str(row.get("nip") or "").lower()
                or term in str(row.get("email") or "").lower()
            ]
        return [dict(row) for row in rows]

    def get_by_nip(self, nip: str) -> dict[str, Any] | None:
        return next((row for row in self.rows if row["nip"] == nip.strip()), None)

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        target = email.strip().lower()
        return next(
            (
                row
                for row in self.rows
                if str(row.get("email") or "").lower() == target
            ),
            None,
        )

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        if self.fail_on_create:
            raise ExternalServiceError("simulasi kegagalan insert dosen")
        row = {
            "email": None,
            "no_hp": None,
            "auth_user_id": None,
            **fields,
        }
        self.rows.append(row)
        return dict(row)

    def update(self, nip: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        row = self.get_by_nip(nip)
        if row is None:
            return None
        row.update(fields)
        return dict(row)

    def has_references(self, nip: str) -> bool:
        return self.referenced

    def delete(self, nip: str) -> None:
        self.rows = [row for row in self.rows if row["nip"] != nip.strip()]


class FakeProgramStudiRepo:
    """In-memory ``ProgramStudiRepository`` with lookup by kode."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = [dict(row) for row in (rows or [])]

    def list_all(self, search: str | None = None) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows]

    def get_by_kode(self, kode: str) -> dict[str, Any] | None:
        return next((row for row in self.rows if row["kode"] == kode.strip().upper()), None)


class FakeKelasRepo:
    """In-memory ``KelasRepository`` covering the full CRUD surface."""

    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        referenced: bool = False,
        program_studi: dict[str, str] | None = None,
        tahun_ajaran: dict[str, str] | None = None,
    ) -> None:
        self.rows = [dict(row) for row in (rows or [])]
        self.referenced = referenced
        self.program_studi = program_studi or {}
        self.tahun_ajaran = tahun_ajaran or {}

    def _enrich(self, row: dict[str, Any]) -> dict[str, Any]:
        kode = str(row.get("program_studi_kode") or "")
        tahun_id = str(row.get("tahun_ajaran_id") or "")
        enriched = dict(row)
        if kode in self.program_studi:
            enriched["program_studi"] = {"nama": self.program_studi[kode]}
        if tahun_id in self.tahun_ajaran:
            enriched["tahun_ajaran"] = {"tahun": self.tahun_ajaran[tahun_id]}
        return enriched

    def list_all(
        self,
        search: str | None = None,
        program_studi_kode: str | None = None,
        tahun_ajaran_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.rows
        if search and search.strip():
            term = search.strip().lower()
            rows = [row for row in rows if term in str(row.get("nama") or "").lower()]
        if program_studi_kode and program_studi_kode.strip():
            target = program_studi_kode.strip().upper()
            rows = [row for row in rows if row.get("program_studi_kode") == target]
        if tahun_ajaran_id and tahun_ajaran_id.strip():
            target = tahun_ajaran_id.strip()
            rows = [row for row in rows if str(row.get("tahun_ajaran_id")) == target]
        if status and status.strip():
            target = status.strip().lower()
            rows = [row for row in rows if row.get("status") == target]
        return [self._enrich(row) for row in rows]

    def get_by_id(self, kelas_id: str) -> dict[str, Any] | None:
        row = next((row for row in self.rows if str(row.get("id")) == kelas_id), None)
        return self._enrich(row) if row else None

    def get_by_nama_dan_tahun(self, nama: str, tahun_ajaran_id: str) -> dict[str, Any] | None:
        row = next(
            (
                row
                for row in self.rows
                if row.get("nama") == nama
                and str(row.get("tahun_ajaran_id")) == tahun_ajaran_id
            ),
            None,
        )
        return self._enrich(row) if row else None

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        row = {"id": str(uuid4()), "status": "aktif", **fields}
        self.rows.append(row)
        return self._enrich(row)

    def update(self, kelas_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        row = next((row for row in self.rows if str(row.get("id")) == kelas_id), None)
        if row is None:
            return None
        row.update(fields)
        return self._enrich(row)

    def has_references(self, kelas_id: str) -> bool:
        return self.referenced

    def delete(self, kelas_id: str) -> None:
        self.rows = [row for row in self.rows if str(row.get("id")) != kelas_id]


class FakeAuthRepo:
    """Records Supabase Auth side effects performed while creating lecturers."""

    def __init__(self, fail_create: bool = False) -> None:
        self.fail_create = fail_create
        self.created: list[dict[str, Any]] = []
        self.linked: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.updated_emails: list[tuple[str, str]] = []

    def create_auth_user(
        self,
        email: str,
        password: str,
        user_metadata: dict[str, Any] | None = None,
    ) -> str:
        if self.fail_create:
            raise ConflictError("Akun autentikasi untuk email/NIM tersebut sudah ada.")
        auth_user_id = f"auth-{len(self.created) + 1}"
        self.created.append(
            {
                "auth_user_id": auth_user_id,
                "email": email,
                "password": password,
                "user_metadata": user_metadata or {},
            }
        )
        return auth_user_id

    def link_dosen_auth_user(self, auth_user_id: str, nip: str) -> None:
        self.linked.append((auth_user_id, nip))

    def update_auth_email(self, auth_user_id: str, new_email: str) -> None:
        self.updated_emails.append((auth_user_id, new_email))

    def delete_auth_user(self, auth_user_id: str) -> None:
        self.deleted.append(auth_user_id)


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_dependency_overrides():
    """Guarantee no override leaks between API tests."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override() -> Callable[[Any, Any], None]:
    def _override(dependency: Any, provider: Any) -> None:
        app.dependency_overrides[dependency] = provider

    return _override


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def admin_headers(settings: Settings) -> dict[str, str]:
    token = create_access_token(
        subject=settings.admin_username, role="admin", settings=settings
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_headers(settings: Settings) -> dict[str, str]:
    token = create_access_token(subject="99999999", role="mahasiswa", settings=settings)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def dosen_headers(settings: Settings) -> dict[str, str]:
    token = create_access_token(
        subject="999999999001", role="dosen", settings=settings
    )
    return {"Authorization": f"Bearer {token}"}


# Named dependency aliases used by several suites.
API_DEPS = {
    "db": get_db_client,
    "whitelist_repo": get_whitelist_nim_repository,
    "mahasiswa_repo": get_mahasiswa_repository,
    "tahun_repo": get_tahun_ajaran_repository,
    "matkul_repo": get_mata_kuliah_repository,
    "jadwal_repo": get_jadwal_repository,
    "master_service": get_admin_master_data_service,
    "options_service": get_admin_options_service,
    "auth_repo": get_auth_repository,
}
