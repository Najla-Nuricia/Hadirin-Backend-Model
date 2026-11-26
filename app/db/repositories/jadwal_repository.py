"""Repository for `v_jadwal_lengkap` and `jadwal_kuliah` queries."""

from typing import Any
from uuid import UUID

from app.core.exceptions import BadRequestError, ConflictError, ExternalServiceError
from app.db.repositories.base import BaseRepository


JADWAL_ADMIN_COLUMNS = (
    "id, tahun_ajaran_id, mata_kuliah_kode, dosen_nip, program_studi_kode, "
    "kelas_id, ruangan_kode, hari, sesi_mulai, sesi_selesai, semester, "
    "created_at, updated_at, "
    "tahun_ajaran!inner(id,tahun), mata_kuliah!inner(kode,nama,sks), "
    "dosen!inner(nip,nama), program_studi!inner(kode,nama), "
    "kelas!inner(id,nama,tingkat), ruangan!inner(kode,nama)"
)


def is_uuid_value(value: str) -> bool:
    """Return True when a string looks like a UUID (DB id) rather than a name."""
    try:
        UUID(value.strip())
        return True
    except (ValueError, AttributeError, TypeError):
        return False


class JadwalRepository(BaseRepository):
    """Read and lookup queries for class course schedules."""

    def list_by_kelas_nama(
        self,
        kelas_nama: str,
        hari: str | None = None,
        tahun_ajaran: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch schedule rows from `v_jadwal_lengkap` filtered by class name."""
        query = self.client.table("v_jadwal_lengkap").select("*").ilike("kelas_nama", kelas_nama.strip())
        if hari:
            query = query.eq("hari", hari.strip().lower())
        if tahun_ajaran:
            query = query.eq("tahun_ajaran", tahun_ajaran.strip())
        res = query.order("hari").order("jam_mulai").execute()
        return res.data or []

    def get_by_id(self, jadwal_id: str) -> dict[str, Any] | None:
        """Fetch a single schedule entry from `v_jadwal_lengkap` by UUID."""
        res = self.client.table("v_jadwal_lengkap").select("*").eq("id", jadwal_id).limit(1).execute()
        return self.first_or_none(res.data)

    def get_kelas_id(self, jadwal_id: str) -> str | None:
        """Fetch the class ID of a schedule (not exposed by `v_jadwal_lengkap`)."""
        res = (
            self.client.table("jadwal_kuliah")
            .select("kelas_id")
            .eq("id", jadwal_id)
            .limit(1)
            .execute()
        )
        row = self.first_or_none(res.data)
        return str(row["kelas_id"]) if row and row.get("kelas_id") else None

    def find_matching_jadwal(
        self,
        kelas_nama: str | None = None,
        matakuliah_query: str | None = None,
    ) -> dict[str, Any] | None:
        """Find a schedule matching student's class and optional course name fragment."""
        if kelas_nama and matakuliah_query:
            res = (
                self.client.table("v_jadwal_lengkap")
                .select("*")
                .ilike("kelas_nama", kelas_nama.strip())
                .ilike("matkul_nama", f"%{matakuliah_query.strip()}%")
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]

        if kelas_nama:
            res = (
                self.client.table("v_jadwal_lengkap")
                .select("*")
                .ilike("kelas_nama", kelas_nama.strip())
                .order("hari")
                .order("jam_mulai")
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]

        if matakuliah_query:
            res = (
                self.client.table("v_jadwal_lengkap")
                .select("*")
                .ilike("matkul_nama", f"%{matakuliah_query.strip()}%")
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]

        res = self.client.table("v_jadwal_lengkap").select("*").limit(1).execute()
        return self.first_or_none(res.data)

    def list_all(self, hari: str | None = None) -> list[dict[str, Any]]:
        """List schedules across all classes."""
        query = self.client.table("v_jadwal_lengkap").select("*")
        if hari:
            query = query.eq("hari", hari.strip().lower())
        res = query.order("kelas_nama").order("hari").order("jam_mulai").execute()
        return res.data or []

    # ── Admin schedule management ─────────────────────────────────────────

    def admin_list(
        self,
        *,
        tahun_ajaran: str | None = None,
        semester: str | None = None,
        tingkat: int | None = None,
        kelas: str | None = None,
    ) -> list[dict[str, Any]]:
        """List `jadwal_kuliah` rows with joined metadata and admin filters."""
        query = self.client.table("jadwal_kuliah").select(JADWAL_ADMIN_COLUMNS)
        if tahun_ajaran:
            if is_uuid_value(tahun_ajaran):
                query = query.eq("tahun_ajaran_id", tahun_ajaran.strip())
            else:
                query = query.ilike("tahun_ajaran.tahun", tahun_ajaran.strip())
        if semester:
            query = query.eq("semester", semester.strip().lower())
        if tingkat is not None:
            query = query.eq("kelas.tingkat", tingkat)
        if kelas:
            if is_uuid_value(kelas):
                query = query.eq("kelas_id", kelas.strip())
            else:
                query = query.ilike("kelas.nama", kelas.strip().upper())
        res = query.execute()
        return res.data or []

    def admin_get_by_id(self, jadwal_id: str) -> dict[str, Any] | None:
        """Fetch one `jadwal_kuliah` row with all joined metadata."""
        res = (
            self.client.table("jadwal_kuliah")
            .select(JADWAL_ADMIN_COLUMNS)
            .eq("id", jadwal_id)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def get_tahun_ajaran(self, value: str) -> dict[str, Any] | None:
        """Resolve a tahun ajaran by UUID or by year string ('2026/2027')."""
        cleaned = value.strip()
        query = self.client.table("tahun_ajaran").select("id,tahun,status,semester_ganjil,semester_genap")
        if is_uuid_value(cleaned):
            query = query.eq("id", cleaned)
        else:
            query = query.ilike("tahun", cleaned)
        return self.first_or_none(query.limit(1).execute().data)

    def get_mata_kuliah(self, kode: str) -> dict[str, Any] | None:
        """Resolve a mata kuliah by its code (case-insensitive)."""
        res = (
            self.client.table("mata_kuliah")
            .select("kode,nama,semester,sks")
            .ilike("kode", kode.strip())
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def get_ruangan(self, kode: str) -> dict[str, Any] | None:
        """Resolve a ruangan by its code (case-insensitive)."""
        res = (
            self.client.table("ruangan")
            .select("kode,nama")
            .ilike("kode", kode.strip())
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def get_sesi(self, nomor: int) -> dict[str, Any] | None:
        """Resolve a lecture session number."""
        res = (
            self.client.table("sesi_kuliah")
            .select("nomor,jam_mulai,jam_selesai")
            .eq("nomor", nomor)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def list_sesi(self) -> list[dict[str, Any]]:
        """List all lecture session slots for time-label enrichment."""
        res = self.client.table("sesi_kuliah").select("nomor,jam_mulai,jam_selesai").order("nomor").execute()
        return res.data or []

    def find_potential_conflicts(
        self,
        *,
        tahun_ajaran_id: str,
        semester: str,
        hari: str,
        exclude_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch schedules in the same term/day; overlap is checked by the service."""
        query = (
            self.client.table("jadwal_kuliah")
            .select("id,kelas_id,dosen_nip,ruangan_kode,hari,sesi_mulai,sesi_selesai,mata_kuliah_kode")
            .eq("tahun_ajaran_id", tahun_ajaran_id)
            .eq("semester", semester)
            .eq("hari", hari)
        )
        if exclude_id:
            query = query.neq("id", exclude_id)
        res = query.execute()
        return res.data or []

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert a new schedule row and return it with joined metadata."""
        try:
            res = self.client.table("jadwal_kuliah").insert(payload).execute()
        except Exception as exc:
            self._raise_write_error(exc, "menyimpan jadwal")
        created = self.first_or_none(res.data) or {}
        if not created.get("id"):
            raise ExternalServiceError("Jadwal gagal dimuat setelah dibuat.")
        row = self.admin_get_by_id(str(created["id"]))
        if not row:
            raise ExternalServiceError("Jadwal gagal dimuat setelah dibuat.")
        return row

    def update(self, jadwal_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Update a schedule row and return it with joined metadata."""
        if not fields:
            return self.admin_get_by_id(jadwal_id)
        try:
            self.client.table("jadwal_kuliah").update(fields).eq("id", jadwal_id).execute()
        except Exception as exc:
            self._raise_write_error(exc, "memperbarui jadwal")
        return self.admin_get_by_id(jadwal_id)

    @staticmethod
    def _raise_write_error(exc: Exception, action: str) -> None:
        """Translate common Supabase write failures into domain exceptions."""
        msg = str(exc).lower()
        if "foreign key" in msg or "23503" in msg:
            raise BadRequestError("Relasi data jadwal tidak valid.") from exc
        if "duplicate" in msg or "23505" in msg or "unique" in msg:
            raise ConflictError("Jadwal dengan data tersebut sudah ada.") from exc
        raise ExternalServiceError(f"Gagal {action}: {exc}") from exc

