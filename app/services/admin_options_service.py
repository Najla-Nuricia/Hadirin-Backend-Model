"""Read-only admin service supplying schedule-form option lists."""

from typing import Any

from app.db.repositories import (
    DosenRepository,
    ProgramStudiRepository,
    RuanganRepository,
    SesiKuliahRepository,
)
from app.schemas.admin_master_data import (
    AdminDosenItem,
    AdminDosenListResponse,
    AdminProgramStudiItem,
    AdminProgramStudiListResponse,
    AdminRuanganItem,
    AdminRuanganListResponse,
    AdminSesiKuliahItem,
    AdminSesiKuliahListResponse,
)


class AdminOptionsService:
    """Return live master data used by the admin schedule form pickers."""

    def __init__(
        self,
        dosen_repo: DosenRepository,
        program_studi_repo: ProgramStudiRepository,
        ruangan_repo: RuanganRepository,
        sesi_kuliah_repo: SesiKuliahRepository,
    ) -> None:
        self.dosen_repo = dosen_repo
        self.program_studi_repo = program_studi_repo
        self.ruangan_repo = ruangan_repo
        self.sesi_kuliah_repo = sesi_kuliah_repo

    def list_dosen(self, search: str | None = None) -> AdminDosenListResponse:
        rows = self.dosen_repo.list_all(search)
        return AdminDosenListResponse(
            data=[AdminDosenItem.model_validate(row) for row in rows], total=len(rows)
        )

    def list_program_studi(self, search: str | None = None) -> AdminProgramStudiListResponse:
        rows = self.program_studi_repo.list_all(search)
        return AdminProgramStudiListResponse(
            data=[AdminProgramStudiItem.model_validate(row) for row in rows], total=len(rows)
        )

    def list_ruangan(self, search: str | None = None) -> AdminRuanganListResponse:
        rows = self.ruangan_repo.list_all(search)
        return AdminRuanganListResponse(
            data=[AdminRuanganItem.model_validate(row) for row in rows], total=len(rows)
        )

    def list_sesi_kuliah(self) -> AdminSesiKuliahListResponse:
        rows = self.sesi_kuliah_repo.list_all()
        items = [
            AdminSesiKuliahItem(
                nomor=int(row["nomor"]),
                jam_mulai=self._hhmm(row.get("jam_mulai")),
                jam_selesai=self._hhmm(row.get("jam_selesai")),
            )
            for row in rows
        ]
        return AdminSesiKuliahListResponse(data=items, total=len(items))

    @staticmethod
    def _hhmm(value: Any) -> str | None:
        """Normalize a Supabase TIME value (`07:00:00`) to `HH:mm`."""
        text = str(value or "").strip()
        return text[:5] or None
