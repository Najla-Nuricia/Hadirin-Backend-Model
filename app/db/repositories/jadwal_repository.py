"""Repository for `v_jadwal_lengkap` and `jadwal_kuliah` queries."""

from typing import Any

from app.db.repositories.base import BaseRepository


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

