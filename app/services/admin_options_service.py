"""Read-only admin service supplying schedule-form option lists."""

from typing import Any

from app.core.exceptions import NotFoundError
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
    AdminRuanganQrItem,
    AdminRuanganQrListResponse,
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

    def list_ruangan_qr(self, search: str | None = None) -> AdminRuanganQrListResponse:
        """Return static door QR cards for all rooms (deterministic and permanent)."""
        rows = self.ruangan_repo.list_all(search)
        items: list[AdminRuanganQrItem] = []
        for row in rows:
            kode = str(row.get("kode") or "").strip().upper()
            nama = str(row.get("nama") or "").strip() or f"Ruangan {kode}"
            qr_token = f"HADIRIN:ROOM:{kode}"
            items.append(
                AdminRuanganQrItem(
                    kode=kode,
                    nama=nama,
                    qr_token=qr_token,
                    qr_data=qr_token,
                    format="statis",
                    title=f"KARTU PRESENSI PINTU: {nama} ({kode})",
                    instruksi=(
                        "Pindai QR ini pada pintu ruangan sebelum masuk kelas "
                        "untuk membuka verifikasi presensi wajah Hadirin."
                    ),
                )
            )
        return AdminRuanganQrListResponse(data=items, total=len(items))

    def get_ruangan_qr(self, kode: str) -> AdminRuanganQrItem:
        """Return the static door QR card for a single room."""
        clean_kode = kode.strip().upper()
        rows = self.ruangan_repo.list_all(clean_kode)
        matched = [r for r in rows if str(r.get("kode") or "").strip().upper() == clean_kode]
        if not matched:
            raise NotFoundError(f"Ruangan dengan kode '{kode}' tidak ditemukan.")
        row = matched[0]
        nama = str(row.get("nama") or "").strip() or f"Ruangan {clean_kode}"
        qr_token = f"HADIRIN:ROOM:{clean_kode}"
        return AdminRuanganQrItem(
            kode=clean_kode,
            nama=nama,
            qr_token=qr_token,
            qr_data=qr_token,
            format="statis",
            title=f"KARTU PRESENSI PINTU: {nama} ({clean_kode})",
            instruksi=(
                "Pindai QR ini pada pintu ruangan sebelum masuk kelas "
                "untuk membuka verifikasi presensi wajah Hadirin."
            ),
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
