"""Lecturer service: authentication, dashboard analytics, session roster, and QR control."""

from datetime import datetime, timedelta
import secrets
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from app.core.security import create_access_token
from app.db.repositories import AuthRepository, DosenRepository
from app.schemas.dosen import (
    AttendanceCountsSummary,
    DosenDashboardResponse,
    DosenJadwalSummaryItem,
    DosenKehadiranListResponse,
    DosenKelasSummaryItem,
    DosenLoginRequest,
    DosenLoginResponse,
    DosenProfileResponse,
    DosenStudentAttendanceItem,
    DosenStudentDocument,
    SesiPresensiQrResponse,
)
from app.services import common

STATUS_KEYS: tuple[str, ...] = ("hadir", "izin", "sakit", "alfa")


def build_dosen_profile(row: dict[str, Any]) -> DosenProfileResponse:
    """Build normalized lecturer profile response from a `dosen` table row."""
    nip = str(row["nip"])
    return DosenProfileResponse(
        nip=nip,
        staffId=nip,
        fullName=str(row.get("nama") or ""),
        email=str(row.get("email") or ""),
        phoneNumber=str(row.get("no_hp") or ""),
        role="Dosen",
    )


def _new_counts() -> dict[str, int]:
    return {status_name: 0 for status_name in STATUS_KEYS}


def _count_session_attendance(
    student_nims: list[str],
    status_by_nim: dict[str, str],
) -> dict[str, int]:
    """Count status across a class roster; students with no row count as `alfa`."""
    counts = _new_counts()
    for nim in student_nims:
        st = status_by_nim.get(nim, "alfa")
        counts[st if st in counts else "alfa"] += 1
    return counts


def _add_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for status_name in STATUS_KEYS:
        target[status_name] += source[status_name]


def _build_summary(counts: dict[str, int]) -> AttendanceCountsSummary:
    total = sum(counts.values())
    pct = round(counts["hadir"] / total * 100) if total else 0
    return AttendanceCountsSummary(**counts, total=total, persentase_kehadiran=pct)


def _normalize_jadwal_row(row: dict[str, Any]) -> dict[str, Any]:
    kelas = row.get("kelas") or {}
    mata_kuliah = row.get("mata_kuliah") or {}
    ruangan = row.get("ruangan") or {}
    hari = str(row.get("hari") or "").lower()
    return {
        "jadwal_id": str(row["id"]),
        "course_code": mata_kuliah.get("kode"),
        "course_name": mata_kuliah.get("nama"),
        "sks": mata_kuliah.get("sks"),
        "kelas_id": str(row["kelas_id"]),
        "kelas": kelas.get("nama"),
        "prodi": kelas.get("program_studi_kode"),
        "hari": hari,
        "day_of_week": common.HARI_TO_ISO_DAY.get(hari),
        "start_time": str(row.get("jam_mulai") or (row.get("mulai") or {}).get("jam_mulai") or "")[:5],
        "end_time": str(row.get("jam_selesai") or (row.get("selesai") or {}).get("jam_selesai") or "")[:5],
        "room": ruangan.get("nama") or ruangan.get("kode"),
        "semester": row.get("semester"),
    }


class DosenService:
    """Domain service for lecturer login, dashboard stats, and live QR attendance sessions."""

    def __init__(
        self,
        dosen_repo: DosenRepository,
        auth_repo: AuthRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.dosen_repo = dosen_repo
        self.auth_repo = auth_repo
        self.settings = settings or get_settings()

    def login(self, payload: DosenLoginRequest) -> DosenLoginResponse:
        """Authenticate lecturer via Supabase Auth or configured password and issue JWT."""
        default_pw = (self.settings.dosen_default_password or "").strip()
        dosen = self.dosen_repo.get_by_email(payload.email)

        if not default_pw and (not dosen or not dosen.get("auth_user_id") or self.auth_repo is None):
            raise ServiceUnavailableError(
                "Login dosen belum dikonfigurasi. Isi DOSEN_DEFAULT_PASSWORD di file .env"
            )

        if not dosen:
            raise UnauthorizedError("Email atau password salah.")

        password_ok = False
        if dosen.get("auth_user_id") and self.auth_repo is not None:
            password_ok = bool(
                self.auth_repo.verify_credentials(
                    str(dosen.get("email") or payload.email),
                    payload.password,
                )
            )
        if not password_ok and default_pw:
            password_ok = secrets.compare_digest(
                payload.password.encode("utf-8"),
                default_pw.encode("utf-8"),
            )

        if not password_ok:
            raise UnauthorizedError("Email atau password salah.")

        token = create_access_token(
            subject=str(dosen["nip"]),
            role="dosen",
            extra_claims={"email": dosen.get("email") or ""},
            settings=self.settings,
        )
        profile = build_dosen_profile(dosen)
        return DosenLoginResponse(
            token=token,
            access_token=token,
            token_type="bearer",
            **profile.model_dump(),
        )

    def get_dashboard(self, current_dosen: dict[str, Any]) -> DosenDashboardResponse:
        """Return lecturer's active-term classes, schedules, open sessions, and attendance stats."""
        nip = str(current_dosen["nip"])
        jadwal_rows = self.dosen_repo.list_active_jadwal(nip)
        jadwal_ids = [str(row["id"]) for row in jadwal_rows]
        kelas_ids = sorted({str(row["kelas_id"]) for row in jadwal_rows})

        mahasiswa_rows = self.dosen_repo.list_students_by_kelas_ids(kelas_ids)
        sesi_rows = self.dosen_repo.list_sesi_by_jadwal_ids(jadwal_ids)
        kehadiran_rows = self.dosen_repo.list_rekap_by_jadwal_ids(jadwal_ids)

        nims_by_kelas: dict[str, list[str]] = {cid: [] for cid in kelas_ids}
        for m in mahasiswa_rows:
            nims_by_kelas.setdefault(str(m["kelas_id"]), []).append(str(m["nim"]))

        sesi_by_jadwal: dict[str, list[dict[str, Any]]] = {jid: [] for jid in jadwal_ids}
        for sesi in sesi_rows:
            sesi_by_jadwal.setdefault(str(sesi["jadwal_id"]), []).append(sesi)

        status_by_sesi: dict[str, dict[str, str]] = {}
        for k in kehadiran_rows:
            status_by_sesi.setdefault(str(k["sesi_presensi_id"]), {})[str(k["nim"])] = str(
                k.get("status") or "alfa"
            )

        now = common.now_wib()
        today = now.date().isoformat()
        hari_ini = common.ISO_DAY_TO_HARI.get(now.isoweekday())

        overall_counts = _new_counts()
        kelas_items: dict[str, dict[str, Any]] = {}
        kelas_counts: dict[str, dict[str, int]] = {}
        jadwal_items: list[DosenJadwalSummaryItem] = []

        for row in jadwal_rows:
            norm = _normalize_jadwal_row(row)
            jid = norm["jadwal_id"]
            cid = norm["kelas_id"]
            student_nims = nims_by_kelas.get(cid, [])
            sessions = sesi_by_jadwal.get(jid, [])

            counts = _new_counts()
            for sesi in sessions:
                _add_counts(
                    counts,
                    _count_session_attendance(student_nims, status_by_sesi.get(str(sesi["id"]), {})),
                )

            jadwal_items.append(
                DosenJadwalSummaryItem(
                    **norm,
                    hari_ini=(norm["hari"] == hari_ini),
                    jumlah_mahasiswa=len(student_nims),
                    jumlah_sesi=len(sessions),
                    sesi_terakhir=max((str(s["tanggal"]) for s in sessions), default=None),
                    sesi_aktif_id=next(
                        (
                            str(s["id"])
                            for s in sessions
                            if s.get("is_open") and str(s.get("tanggal")) == today
                        ),
                        None,
                    ),
                    ringkasan_kehadiran=_build_summary(counts),
                )
            )

            kelas_entry = kelas_items.setdefault(
                cid,
                {
                    "kelas_id": cid,
                    "kelas": norm["kelas"],
                    "prodi": norm["prodi"],
                    "jumlah_mahasiswa": len(student_nims),
                    "jumlah_jadwal": 0,
                    "jumlah_sesi": 0,
                },
            )
            kelas_entry["jumlah_jadwal"] += 1
            kelas_entry["jumlah_sesi"] += len(sessions)
            _add_counts(kelas_counts.setdefault(cid, _new_counts()), counts)
            _add_counts(overall_counts, counts)

        jadwal_items.sort(key=lambda item: (item.day_of_week or 0, item.start_time))
        kelas_list = sorted(
            (
                DosenKelasSummaryItem(
                    **entry,
                    ringkasan_kehadiran=_build_summary(kelas_counts[cid]),
                )
                for cid, entry in kelas_items.items()
            ),
            key=lambda item: item.kelas or "",
        )

        return DosenDashboardResponse(
            dosen=build_dosen_profile(current_dosen),
            tanggal=today,
            hari=hari_ini,
            total_kelas=len(kelas_list),
            total_jadwal=len(jadwal_items),
            total_mahasiswa=len(mahasiswa_rows),
            ringkasan_kehadiran=_build_summary(overall_counts),
            kelas=kelas_list,
            jadwal=jadwal_items,
        )

    def get_jadwal_kehadiran(
        self,
        jadwal_id: str,
        nip: str,
        tanggal_iso: str | None = None,
    ) -> DosenKehadiranListResponse:
        """Fetch class roster and session attendance statuses for a lecturer schedule."""
        jadwal = _normalize_jadwal_row(self._get_owned_jadwal_or_raise(jadwal_id, nip))
        sesi = self.dosen_repo.get_latest_sesi_for_jadwal(jadwal_id, tanggal_iso=tanggal_iso)
        if not sesi:
            raise NotFoundError("Belum ada sesi presensi untuk jadwal dan tanggal ini.")

        sesi_id = str(sesi["id"])
        mahasiswa_rows = self.dosen_repo.list_students_by_kelas_ids(
            [jadwal["kelas_id"]],
            columns="nim, nama_lengkap",
        )
        kehadiran_rows = self.dosen_repo.list_kehadiran_for_sesi(sesi_id)
        kehadiran_by_nim = {str(row["nim"]): row for row in kehadiran_rows}

        students: list[DosenStudentAttendanceItem] = []
        for mahasiswa in mahasiswa_rows:
            nim = str(mahasiswa["nim"])
            kehadiran = kehadiran_by_nim.get(nim) or {}
            pengajuan = kehadiran.get("pengajuan_ketidakhadiran") or {}
            if isinstance(pengajuan, list):
                pengajuan = pengajuan[0] if pengajuan else {}
            dokumen_path = pengajuan.get("dokumen_path")
            jam_masuk = kehadiran.get("jam_masuk")

            students.append(
                DosenStudentAttendanceItem(
                    nim=nim,
                    name=str(mahasiswa.get("nama_lengkap") or ""),
                    className=jadwal["kelas"],
                    status=str(kehadiran.get("status") or "alfa"),
                    checkInTime=str(jam_masuk)[:5] if jam_masuk else None,
                    note=pengajuan.get("alasan") or kehadiran.get("catatan"),
                    document=(
                        DosenStudentDocument(
                            fileName=str(dokumen_path).rsplit("/", 1)[-1],
                            path=str(dokumen_path),
                        )
                        if dokumen_path
                        else None
                    ),
                    pengajuan_status=pengajuan.get("status_pengajuan"),
                )
            )

        counts = _count_session_attendance(
            [s.nim for s in students],
            {s.nim: s.status for s in students},
        )
        return DosenKehadiranListResponse(
            jadwal_id=jadwal["jadwal_id"],
            sesi_presensi_id=sesi_id,
            courseName=jadwal["course_name"],
            className=jadwal["kelas"],
            date=str(sesi["tanggal"]),
            is_open=bool(sesi["is_open"]),
            summary=_build_summary(counts),
            students=students,
        )

    def open_sesi_presensi(self, jadwal_id: str, nip: str) -> SesiPresensiQrResponse:
        """Open today's attendance session for a schedule and issue a dynamic QR token."""
        jadwal = _normalize_jadwal_row(self._get_owned_jadwal_or_raise(jadwal_id, nip))
        now = common.now_wib()
        row = self.dosen_repo.upsert_open_sesi(
            {
                "jadwal_id": jadwal_id,
                "tanggal": now.date().isoformat(),
                "is_open": True,
                "dibuka_oleh": nip,
                **self._new_qr_fields(now),
            }
        )
        if not row:
            raise NotFoundError("Gagal membuka sesi presensi.")
        return self._build_sesi_response(
            row,
            course_name=jadwal["course_name"],
            class_name=jadwal["kelas"],
        )

    def refresh_qr_sesensi(self, sesi_id: str, nip: str) -> SesiPresensiQrResponse:
        """Rotate dynamic QR token on an active today session, invalidating the prior code."""
        sesi = self._get_owned_sesi_or_raise(sesi_id, nip)
        now = common.now_wib()
        closed_detail = "Sesi presensi sudah ditutup. Buka sesi baru untuk membuat QR."
        if not sesi.get("is_open") or str(sesi.get("tanggal")) != now.date().isoformat():
            raise ConflictError(closed_detail)

        updated = self.dosen_repo.update_sesi_qr(sesi_id, self._new_qr_fields(now))
        if not updated:
            raise ConflictError(closed_detail)

        jadwal = sesi.get("jadwal_kuliah") or {}
        return self._build_sesi_response(
            updated,
            course_name=(jadwal.get("mata_kuliah") or {}).get("nama"),
            class_name=(jadwal.get("kelas") or {}).get("nama"),
        )

    def close_sesi_presensi(self, sesi_id: str, nip: str) -> SesiPresensiQrResponse:
        """Close an active attendance session and clear its dynamic QR token."""
        sesi = self._get_owned_sesi_or_raise(sesi_id, nip)
        closed = self.dosen_repo.close_sesi(sesi_id)
        if not closed:
            raise NotFoundError("Sesi presensi tidak ditemukan.")
        jadwal = sesi.get("jadwal_kuliah") or {}
        return self._build_sesi_response(
            closed,
            course_name=(jadwal.get("mata_kuliah") or {}).get("nama"),
            class_name=(jadwal.get("kelas") or {}).get("nama"),
        )

    def _get_owned_jadwal_or_raise(self, jadwal_id: str, nip: str) -> dict[str, Any]:
        jadwal = self.dosen_repo.get_jadwal_by_id(jadwal_id)
        if not jadwal:
            raise NotFoundError("Jadwal tidak ditemukan.")
        if str(jadwal.get("dosen_nip")) != nip:
            raise ForbiddenError("Jadwal ini bukan jadwal Anda.")
        return jadwal

    def _get_owned_sesi_or_raise(self, sesi_id: str, nip: str) -> dict[str, Any]:
        sesi = self.dosen_repo.get_sesi_with_jadwal(sesi_id)
        if not sesi:
            raise NotFoundError("Sesi presensi tidak ditemukan.")
        owner_nip = (sesi.get("jadwal_kuliah") or {}).get("dosen_nip")
        if str(owner_nip) != nip:
            raise ForbiddenError("Sesi presensi ini bukan milik Anda.")
        return sesi

    def _new_qr_fields(self, now: datetime) -> dict[str, str]:
        return {
            "qr_token": secrets.token_urlsafe(24),
            "qr_expires_at": (
                now + timedelta(seconds=self.settings.qr_token_ttl_seconds)
            ).isoformat(),
        }

    def _build_sesi_response(
        self,
        sesi: dict[str, Any],
        *,
        course_name: str | None,
        class_name: str | None,
    ) -> SesiPresensiQrResponse:
        return SesiPresensiQrResponse(
            sesi_presensi_id=str(sesi["id"]),
            jadwal_id=str(sesi["jadwal_id"]),
            tanggal=str(sesi["tanggal"]),
            course_name=course_name,
            kelas=class_name,
            is_open=bool(sesi["is_open"]),
            qr_code=sesi.get("qr_token"),
            qr_expires_at=sesi.get("qr_expires_at"),
            qr_ttl_seconds=self.settings.qr_token_ttl_seconds,
        )
