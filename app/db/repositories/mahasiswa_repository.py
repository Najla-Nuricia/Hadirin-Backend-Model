"""Repository for `mahasiswa` and `kelas` PostgreSQL tables."""

from typing import Any

from app.core.exceptions import ConflictError, ExternalServiceError
from app.db.repositories.base import BaseRepository

_MAHASISWA_SELECT = "*, kelas(id, nama, tingkat, program_studi_kode, program_studi(kode, nama))"


class MahasiswaRepository(BaseRepository):
    """CRUD and lookup queries for `mahasiswa` and `kelas`."""

    def get_by_nim(self, nim: str) -> dict[str, Any] | None:
        """Fetch a single student record joined with `kelas` and `program_studi`."""
        res = (
            self.client.table("mahasiswa")
            .select(_MAHASISWA_SELECT)
            .eq("nim", nim)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Fetch a student record matching an email address (case-insensitive)."""
        res = (
            self.client.table("mahasiswa")
            .select(_MAHASISWA_SELECT)
            .ilike("email", email.strip())
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def list_all(
        self,
        kelas_id: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return students ordered by NIM, optionally filtered by `kelas_id` or `search`."""
        query = self.client.table("mahasiswa").select(_MAHASISWA_SELECT)
        if kelas_id:
            query = query.eq("kelas_id", kelas_id)
        if search and search.strip():
            term = search.strip()
            query = query.or_(f"nim.ilike.%{term}%,nama_lengkap.ilike.%{term}%")
        res = query.order("nim").execute()
        return res.data or []

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert a new student row and return the enriched record."""
        try:
            self.client.table("mahasiswa").insert(payload).execute()
        except Exception as exc:
            msg = str(exc).lower()
            if "duplicate" in msg or "23505" in msg or "unique" in msg:
                raise ConflictError("NIM atau email sudah terdaftar.") from exc
            raise ExternalServiceError(f"Gagal menyimpan data mahasiswa: {exc}") from exc

        created = self.get_by_nim(payload["nim"])
        if not created:
            raise ExternalServiceError("Data mahasiswa gagal dimuat setelah dibuat.")
        return created

    def update_by_nim(self, nim: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Update specific fields of a student record identified by NIM."""
        if not fields:
            return self.get_by_nim(nim)
        try:
            self.client.table("mahasiswa").update(fields).eq("nim", nim).execute()
        except Exception as exc:
            msg = str(exc).lower()
            if "duplicate" in msg or "23505" in msg or "unique" in msg:
                raise ConflictError("Email sudah digunakan oleh mahasiswa lain.") from exc
            raise ExternalServiceError(f"Gagal memperbarui data mahasiswa: {exc}") from exc
        return self.get_by_nim(nim)

    def delete_by_nim(self, nim: str) -> bool:
        """Delete a student record by NIM; return True if a row was deleted."""
        res = self.client.table("mahasiswa").delete().eq("nim", nim).execute()
        return bool(res.data)

    def get_kelas_by_id(self, kelas_id: str) -> dict[str, Any] | None:
        """Fetch a single `kelas` record by UUID."""
        res = (
            self.client.table("kelas")
            .select("*, program_studi(kode, nama)")
            .eq("id", kelas_id)
            .limit(1)
            .execute()
        )
        return self.first_or_none(res.data)

    def get_kelas_by_name(self, kelas_nama: str) -> dict[str, Any] | None:
        """Resolve a `kelas` record by name (case-insensitive), preferring active classes."""
        res = (
            self.client.table("kelas")
            .select("*, program_studi(kode, nama)")
            .ilike("nama", kelas_nama.strip())
            .order("created_at", desc=True)
            .execute()
        )
        rows = res.data or []
        for row in rows:
            if row.get("status") == "aktif":
                return row
        return self.first_or_none(rows)

    def list_kelas(self) -> list[dict[str, Any]]:
        """List all classes ordered by name."""
        res = (
            self.client.table("kelas")
            .select("*, program_studi(kode, nama)")
            .order("nama")
            .execute()
        )
        return res.data or []

