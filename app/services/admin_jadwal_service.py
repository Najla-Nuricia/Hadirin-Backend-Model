"""Admin service for creating, listing, and updating course schedules."""

from typing import Any

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.db.repositories import DosenRepository, JadwalRepository, MahasiswaRepository
from app.db.repositories.jadwal_repository import is_uuid_value
from app.schemas.admin_jadwal import (
    AdminJadwalFilter,
    AdminJadwalItem,
    AdminJadwalListResponse,
    AdminJadwalMutationResponse,
    AdminJadwalWriteRequest,
)
from app.services.common import HARI_ORDER


class AdminJadwalService:
    """Validates relations and conflicts before writing `jadwal_kuliah` rows."""

    def __init__(
        self,
        jadwal_repo: JadwalRepository,
        mahasiswa_repo: MahasiswaRepository,
        dosen_repo: DosenRepository,
    ) -> None:
        self.jadwal_repo = jadwal_repo
        self.mahasiswa_repo = mahasiswa_repo
        self.dosen_repo = dosen_repo

    def list_jadwal(
        self,
        *,
        tahun_ajaran: str | None = None,
        semester: str | None = None,
        tingkat: int | None = None,
        kelas: str | None = None,
    ) -> AdminJadwalListResponse:
        """Return schedules filtered by academic year, semester, class level, or class."""
        filters = AdminJadwalFilter(
            tahun_ajaran=tahun_ajaran.strip() if tahun_ajaran else None,
            semester=semester.strip().lower() if semester else None,
            tingkat=tingkat,
            kelas=kelas.strip().upper() if kelas and not is_uuid_value(kelas) else kelas,
        )
        rows = self.jadwal_repo.admin_list(
            tahun_ajaran=filters.tahun_ajaran,
            semester=filters.semester,
            tingkat=filters.tingkat,
            kelas=filters.kelas,
        )
        sesi_map = self._sesi_time_map()
        items = [self._to_item(row, sesi_map) for row in rows]
        items.sort(
            key=lambda item: (
                item.kelas_nama,
                HARI_ORDER.get(item.hari, 99),
                item.sesi_mulai,
                item.dosen_nip,
            )
        )
        return AdminJadwalListResponse(data=items, total=len(items), filters=filters)

    def create_jadwal(self, payload: AdminJadwalWriteRequest) -> AdminJadwalMutationResponse:
        """Validate relations and conflicts, then create a new schedule."""
        relations = self._resolve_relations(payload)
        fields = self._build_fields(payload, relations)
        self._ensure_no_conflict(payload, relations, exclude_id=None)

        created = self.jadwal_repo.create(fields)
        return AdminJadwalMutationResponse(
            message="Jadwal berhasil dibuat.",
            data=self._to_item(created, self._sesi_time_map()),
        )

    def update_jadwal(
        self,
        jadwal_id: str,
        payload: AdminJadwalWriteRequest,
    ) -> AdminJadwalMutationResponse:
        """Validate relations and conflicts, then replace an existing schedule."""
        existing = self.jadwal_repo.admin_get_by_id(jadwal_id)
        if not existing:
            raise NotFoundError("Jadwal tidak ditemukan.")

        relations = self._resolve_relations(payload)
        fields = self._build_fields(payload, relations)
        self._ensure_no_conflict(payload, relations, exclude_id=jadwal_id)

        updated = self.jadwal_repo.update(jadwal_id, fields)
        if not updated:
            raise NotFoundError("Jadwal tidak ditemukan.")
        return AdminJadwalMutationResponse(
            message="Jadwal berhasil diperbarui.",
            data=self._to_item(updated, self._sesi_time_map()),
        )

    def _resolve_relations(self, payload: AdminJadwalWriteRequest) -> dict[str, Any]:
        """Resolve every foreign key and enforce cross-field consistency."""
        tahun = self.jadwal_repo.get_tahun_ajaran(payload.tahun_ajaran)
        if not tahun:
            raise BadRequestError("Tahun ajaran tidak ditemukan.")

        if is_uuid_value(payload.kelas):
            kelas = self.mahasiswa_repo.get_kelas_by_id(payload.kelas.strip())
        else:
            kelas = self.mahasiswa_repo.get_kelas_by_name(payload.kelas)
        if not kelas:
            raise BadRequestError("Kelas tidak ditemukan.")
        if str(kelas.get("tahun_ajaran_id")) != str(tahun["id"]):
            raise BadRequestError("Kelas tidak sesuai dengan tahun ajaran yang dipilih.")

        matkul = self.jadwal_repo.get_mata_kuliah(payload.mata_kuliah_kode)
        if not matkul:
            raise BadRequestError("Mata kuliah tidak ditemukan.")
        matkul_period = "ganjil" if int(matkul["semester"]) % 2 == 1 else "genap"
        if matkul_period != payload.semester:
            raise BadRequestError(
                f"Mata kuliah {matkul['kode']} (semester {matkul['semester']}) "
                f"tidak sesuai dengan periode {payload.semester}."
            )

        dosen = self.dosen_repo.get_by_nip(payload.dosen_nip)
        if not dosen:
            raise BadRequestError("Dosen tidak ditemukan.")

        ruangan = self.jadwal_repo.get_ruangan(payload.ruangan_kode)
        if not ruangan:
            raise BadRequestError("Ruangan tidak ditemukan.")

        for nomor in (payload.sesi_mulai, payload.sesi_selesai):
            if not self.jadwal_repo.get_sesi(nomor):
                raise BadRequestError(f"Sesi ke-{nomor} tidak ditemukan.")

        return {
            "tahun": tahun,
            "kelas": kelas,
            "matkul": matkul,
            "dosen": dosen,
            "ruangan": ruangan,
        }

    @staticmethod
    def _build_fields(
        payload: AdminJadwalWriteRequest,
        relations: dict[str, Any],
    ) -> dict[str, Any]:
        """Build canonical `jadwal_kuliah` columns from resolved relations."""
        tahun = relations["tahun"]
        kelas = relations["kelas"]
        return {
            "tahun_ajaran_id": str(tahun["id"]),
            "mata_kuliah_kode": str(relations["matkul"]["kode"]),
            "dosen_nip": str(relations["dosen"]["nip"]),
            "program_studi_kode": str(kelas["program_studi_kode"]),
            "kelas_id": str(kelas["id"]),
            "ruangan_kode": str(relations["ruangan"]["kode"]),
            "hari": payload.hari,
            "sesi_mulai": payload.sesi_mulai,
            "sesi_selesai": payload.sesi_selesai,
            "semester": payload.semester,
        }

    def _ensure_no_conflict(
        self,
        payload: AdminJadwalWriteRequest,
        relations: dict[str, Any],
        *,
        exclude_id: str | None,
    ) -> None:
        """Reject overlapping sessions for the same class, lecturer, or room."""
        rows = self.jadwal_repo.find_potential_conflicts(
            tahun_ajaran_id=str(relations["tahun"]["id"]),
            semester=payload.semester,
            hari=payload.hari,
            exclude_id=exclude_id,
        )
        for row in rows:
            if not self._overlaps(payload, row):
                continue
            if str(row.get("kelas_id")) == str(relations["kelas"]["id"]):
                raise ConflictError(
                    f"Kelas {relations['kelas']['nama']} sudah memiliki jadwal pada "
                    f"hari {payload.hari} sesi {row['sesi_mulai']}-{row['sesi_selesai']}."
                )
            if str(row.get("dosen_nip")) == str(relations["dosen"]["nip"]):
                raise ConflictError(
                    f"Dosen {relations['dosen']['nama']} sudah mengajar pada "
                    f"hari {payload.hari} sesi {row['sesi_mulai']}-{row['sesi_selesai']}."
                )
            if str(row.get("ruangan_kode")) == str(relations["ruangan"]["kode"]):
                raise ConflictError(
                    f"Ruangan {relations['ruangan']['nama']} sudah digunakan pada "
                    f"hari {payload.hari} sesi {row['sesi_mulai']}-{row['sesi_selesai']}."
                )

    @staticmethod
    def _overlaps(payload: AdminJadwalWriteRequest, row: dict[str, Any]) -> bool:
        """Inclusive interval overlap: adjacent sessions are allowed, shared ones are not."""
        return (
            payload.sesi_mulai <= int(row["sesi_selesai"])
            and int(row["sesi_mulai"]) <= payload.sesi_selesai
        )

    def _sesi_time_map(self) -> dict[int, tuple[str | None, str | None]]:
        """Map session numbers to their `(jam_mulai, jam_selesai)` display times."""
        result: dict[int, tuple[str | None, str | None]] = {}
        for row in self.jadwal_repo.list_sesi():
            try:
                nomor = int(row["nomor"])
            except (KeyError, TypeError, ValueError):
                continue
            mulai = str(row.get("jam_mulai") or "")[:5] or None
            selesai = str(row.get("jam_selesai") or "")[:5] or None
            result[nomor] = (mulai, selesai)
        return result

    @staticmethod
    def _relation(row: dict[str, Any], name: str, key: str) -> Any:
        """Read a field from a Supabase embedded relation (dict or single-item list)."""
        value = row.get(name)
        if isinstance(value, list):
            value = value[0] if value else {}
        return value.get(key) if isinstance(value, dict) else None

    def _to_item(
        self,
        row: dict[str, Any],
        sesi_map: dict[int, tuple[str | None, str | None]],
    ) -> AdminJadwalItem:
        """Flatten a joined schedule row into the API response model."""
        mulai = int(row["sesi_mulai"])
        selesai = int(row["sesi_selesai"])
        jam_mulai, jam_selesai = sesi_map.get(mulai, (None, None))
        return AdminJadwalItem(
            id=str(row["id"]),
            tahun_ajaran_id=str(row["tahun_ajaran_id"]),
            tahun_ajaran=str(self._relation(row, "tahun_ajaran", "tahun") or ""),
            semester=str(row["semester"]),
            hari=str(row["hari"]),
            sesi_mulai=mulai,
            sesi_selesai=selesai,
            jam_mulai=jam_mulai,
            jam_selesai=sesi_map.get(selesai, (None, None))[1],
            mata_kuliah_kode=str(row["mata_kuliah_kode"]),
            matkul_nama=str(self._relation(row, "mata_kuliah", "nama") or ""),
            sks=int(self._relation(row, "mata_kuliah", "sks") or 0),
            dosen_nip=str(row["dosen_nip"]),
            dosen_nama=str(self._relation(row, "dosen", "nama") or ""),
            program_studi_kode=str(row["program_studi_kode"]),
            prodi_nama=str(self._relation(row, "program_studi", "nama") or ""),
            kelas_id=str(row["kelas_id"]),
            kelas_nama=str(self._relation(row, "kelas", "nama") or ""),
            kelas_tingkat=int(self._relation(row, "kelas", "tingkat") or 0),
            ruangan_kode=str(row["ruangan_kode"]),
            ruangan_nama=str(self._relation(row, "ruangan", "nama") or ""),
        )
