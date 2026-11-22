"""Service for student course schedules (`v_jadwal_lengkap`) and dynamic reminders."""

from typing import Any

from app.core.exceptions import NotFoundError
from app.db.repositories import JadwalRepository, KehadiranRepository, MahasiswaRepository
from app.schemas.jadwal import (
    JadwalItem,
    JadwalListResponse,
    PengingatItem,
    PengingatResponse,
)
from app.services.common import (
    HARI_ORDER,
    WEEKDAY_TO_HARI,
    format_hhmm,
    format_time_range,
    now_wib,
)


class JadwalService:
    """Reads class schedules and calculates upcoming/active lecture reminders dynamically."""

    def __init__(
        self,
        mahasiswa_repo: MahasiswaRepository,
        jadwal_repo: JadwalRepository,
        kehadiran_repo: KehadiranRepository,
    ) -> None:
        self.mahasiswa_repo = mahasiswa_repo
        self.jadwal_repo = jadwal_repo
        self.kehadiran_repo = kehadiran_repo

    def get_student_jadwal(
        self,
        nim: str,
        hari: str | None = None,
        day_of_week: int | None = None,
    ) -> JadwalListResponse:
        """Return class schedules from `v_jadwal_lengkap` matching the student's class."""
        kelas_nama = self._resolve_student_kelas_nama(nim)
        if not kelas_nama:
            return JadwalListResponse(data=[], total=0, kelas=None)

        effective_hari = hari
        if not effective_hari and day_of_week is not None:
            effective_hari = WEEKDAY_TO_HARI.get(day_of_week - 1)

        rows = self.jadwal_repo.list_by_kelas_nama(kelas_nama, hari=effective_hari)
        if not rows:
            return JadwalListResponse(data=[], total=0, kelas=kelas_nama)

        now = now_wib()
        today_hari = WEEKDAY_TO_HARI.get(now.weekday(), "")
        today_iso = now.date().isoformat()
        open_map = self._map_open_sessions(rows, today_iso)

        items = [self._to_jadwal_item(row, today_hari, open_map) for row in rows]
        items.sort(key=lambda item: (HARI_ORDER.get(item.hari.lower(), 99), item.jam_mulai))
        return JadwalListResponse(data=items, total=len(items), kelas=kelas_nama)

    def get_student_pengingat(self, nim: str) -> PengingatResponse:
        """Select the most relevant ongoing or upcoming class from DB schedules."""
        jadwal_resp = self.get_student_jadwal(nim)
        items = jadwal_resp.data
        if not items:
            return PengingatResponse(
                data=None,
                message="Belum ada jadwal perkuliahan untuk kelas Anda.",
            )

        now = now_wib()
        today_idx = now.weekday()
        current_hhmm = now.strftime("%H:%M")

        # 1. Prioritize any session currently opened by the lecturer today.
        for item in items:
            if item.is_session_open:
                return PengingatResponse(
                    data=self._to_pengingat_item(item, is_today=True, status_label="Sesi Presensi Dibuka"),
                )

        # 2. Next, check today's remaining or ongoing schedules in chronological order.
        today_hari = WEEKDAY_TO_HARI.get(today_idx, "")
        today_items = sorted(
            [item for item in items if item.hari.lower() == today_hari],
            key=lambda x: x.jam_mulai,
        )
        for item in today_items:
            if item.jam_mulai <= current_hhmm <= item.jam_selesai:
                return PengingatResponse(
                    data=self._to_pengingat_item(item, is_today=True, status_label="Sedang Berlangsung"),
                )
            if item.jam_mulai > current_hhmm:
                return PengingatResponse(
                    data=self._to_pengingat_item(item, is_today=True, status_label="Jadwal Hari Ini"),
                )

        # 3. Otherwise choose the nearest upcoming class across upcoming days.
        def _days_until(item: JadwalItem) -> tuple[int, str]:
            day_idx = HARI_ORDER.get(item.hari.lower(), 0)
            delta = (day_idx - today_idx) % 7
            if delta == 0:
                delta = 7
            return (delta, item.jam_mulai)

        nearest = min(items, key=_days_until)
        return PengingatResponse(
            data=self._to_pengingat_item(nearest, is_today=False, status_label="Jadwal Berikutnya"),
        )

    def _resolve_student_kelas_nama(self, nim: str) -> str | None:
        student = self.mahasiswa_repo.get_by_nim(nim)
        if not student:
            raise NotFoundError(f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.")
        kelas = student.get("kelas") or {}
        if isinstance(kelas, list):
            kelas = kelas[0] if kelas else {}
        return kelas.get("nama")

    def _map_open_sessions(self, rows: list[dict[str, Any]], today_iso: str) -> dict[str, dict[str, Any]]:
        jadwal_ids = [row["id"] for row in rows if row.get("id")]
        open_sessions = self.kehadiran_repo.list_open_sesi_by_jadwal_ids(
            jadwal_ids=jadwal_ids,
            tanggal_iso=today_iso,
        )
        return {sesi["jadwal_id"]: sesi for sesi in open_sessions if sesi.get("jadwal_id")}

    @staticmethod
    def _to_jadwal_item(
        row: dict[str, Any],
        today_hari: str,
        open_map: dict[str, dict[str, Any]],
    ) -> JadwalItem:
        jam_mulai = format_hhmm(row.get("jam_mulai"))
        jam_selesai = format_hhmm(row.get("jam_selesai"))
        hari = (row.get("hari") or "").lower()
        day_of_week = HARI_ORDER.get(hari, 0) + 1
        matkul = str(row.get("matkul_nama") or "")
        room = row.get("ruangan_nama") or row.get("ruangan_kode")
        lecturer = row.get("dosen_nama")
        open_sesi = open_map.get(row["id"])
        is_open = open_sesi is not None
        return JadwalItem(
            id=str(row["id"]),
            hari=hari,
            day_of_week=day_of_week,
            semester=str(row.get("semester") or ""),
            tahun_ajaran=str(row.get("tahun_ajaran") or ""),
            matkul_kode=str(row.get("matkul_kode") or ""),
            matkul_nama=matkul,
            courseName=matkul,
            course_name=matkul,
            sks=int(row.get("sks") or 0),
            dosen_nip=row.get("dosen_nip"),
            dosen_nama=lecturer,
            lecturer_name=lecturer,
            prodi_kode=row.get("prodi_kode"),
            prodi_nama=row.get("prodi_nama"),
            kelas_nama=str(row.get("kelas_nama") or ""),
            kelas_tingkat=row.get("kelas_tingkat"),
            ruangan_kode=row.get("ruangan_kode"),
            ruangan_nama=row.get("ruangan_nama"),
            room=room,
            jam_mulai=jam_mulai,
            jam_selesai=jam_selesai,
            start_time=jam_mulai,
            end_time=jam_selesai,
            time=format_time_range(row.get("jam_mulai"), row.get("jam_selesai")),
            sesi_mulai=row.get("sesi_mulai"),
            sesi_selesai=row.get("sesi_selesai"),
            has_alarm=(hari == today_hari) or is_open,
            is_session_open=is_open,
            active_sesi_id=str(open_sesi["id"]) if open_sesi else None,
        )

    @staticmethod
    def _to_pengingat_item(
        jadwal: JadwalItem,
        is_today: bool,
        status_label: str,
    ) -> PengingatItem:
        room = jadwal.ruangan_nama or jadwal.ruangan_kode or "-"
        return PengingatItem(
            jadwal_id=jadwal.id,
            matkul_kode=jadwal.matkul_kode,
            matkul_nama=jadwal.matkul_nama,
            courseName=jadwal.courseName,
            hari=jadwal.hari,
            day_of_week=jadwal.day_of_week,
            jam_mulai=jadwal.jam_mulai,
            jam_selesai=jadwal.jam_selesai,
            time=jadwal.time,
            ruangan_kode=jadwal.ruangan_kode,
            ruangan_nama=jadwal.ruangan_nama,
            room=room,
            dosen_nama=jadwal.dosen_nama,
            kelas_nama=jadwal.kelas_nama,
            is_today=is_today,
            is_session_open=jadwal.is_session_open,
            sesi_presensi_id=jadwal.active_sesi_id,
            status_label=status_label,
            message=f"{status_label} — {jadwal.hari.title()} {jadwal.jam_mulai}",
        )

