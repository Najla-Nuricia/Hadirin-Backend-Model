"""Service for attendance summary, history, static room QR, GPS, and face check-in."""

from datetime import datetime, timedelta
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    UnprocessableError,
)
from app.db.repositories import (
    JadwalRepository,
    KehadiranRepository,
    MahasiswaRepository,
)
from app.schemas.presensi import (
    ActiveSessionItem,
    ActiveSessionListResponse,
    AttendanceRecordResponse,
    GpsAttendanceRequest,
    PresensiHistoryItem,
    PresensiHistoryResponse,
    PresensiSummaryResponse,
    ValidateRoomQrRequest,
    ValidateRoomQrResponse,
)
from app.services import common
from app.services.common import (
    STATUS_LABELS,
    WEEKDAY_TO_HARI,
    format_hhmm,
    haversine_meters,
)
from app.services.face_recognition.face_service import FaceService

WINDOW_TOLERANCE = timedelta(hours=1)


class PresensiService:
    """Reads attendance statistics/history and validates real DB check-ins."""

    def __init__(
        self,
        mahasiswa_repo: MahasiswaRepository,
        jadwal_repo: JadwalRepository,
        kehadiran_repo: KehadiranRepository,
        face_service: FaceService,
        settings: Settings | None = None,
    ) -> None:
        self.mahasiswa_repo = mahasiswa_repo
        self.jadwal_repo = jadwal_repo
        self.kehadiran_repo = kehadiran_repo
        self.face_service = face_service
        self.settings = settings or get_settings()

    def get_summary(self, nim: str) -> PresensiSummaryResponse:
        """Compute attendance counts dynamically from `v_rekap_kehadiran`."""
        student = self._get_student_or_404(nim)
        rows = self.kehadiran_repo.list_rekap_by_nim(nim)

        counts = {"hadir": 0, "izin": 0, "sakit": 0, "alfa": 0}
        for row in rows:
            st = (row.get("status") or "").lower()
            if st in counts:
                counts[st] += 1

        total = len(rows)
        persentase = round((counts["hadir"] / total) * 100.0, 1) if total > 0 else 0.0
        return PresensiSummaryResponse(
            nim=nim,
            nama_lengkap=student.get("nama_lengkap"),
            total_pertemuan=total,
            hadir=counts["hadir"],
            izin=counts["izin"],
            sakit=counts["sakit"],
            alfa=counts["alfa"],
            persentase_kehadiran=persentase,
        )

    def get_history(
        self,
        nim: str,
        status_filter: str | None = None,
        limit: int | None = None,
    ) -> PresensiHistoryResponse:
        """Fetch attendance history from `v_rekap_kehadiran`."""
        self._get_student_or_404(nim)
        rows = self.kehadiran_repo.list_rekap_by_nim(
            nim=nim,
            status_filter=status_filter,
            limit=limit,
        )

        items: list[PresensiHistoryItem] = []
        for row in rows:
            st = (row.get("status") or "hadir").lower()
            jam_masuk = format_hhmm(row.get("jam_masuk")) if row.get("jam_masuk") else "-"
            kehadiran_id = str(row["kehadiran_id"])
            tanggal = str(row.get("tanggal") or "")
            matkul = str(row.get("matkul_nama") or "-")
            items.append(
                PresensiHistoryItem(
                    kehadiran_id=kehadiran_id,
                    sesi_presensi_id=str(row["sesi_presensi_id"]),
                    jadwal_id=str(row["jadwal_id"]) if row.get("jadwal_id") else None,
                    tanggal=tanggal,
                    date=tanggal,
                    matkul_nama=matkul,
                    courseName=matkul,
                    kelas_nama=row.get("kelas_nama"),
                    dosen_nama=row.get("dosen_nama"),
                    nim=nim,
                    nama_mahasiswa=row.get("nama_mahasiswa"),
                    status=st,
                    status_label=STATUS_LABELS.get(st, st.title()),
                    jam_masuk=row.get("jam_masuk"),
                    time=jam_masuk,
                    catatan=row.get("catatan"),
                    status_pengajuan=row.get("status_pengajuan"),
                    jenis_pengajuan=row.get("jenis_pengajuan"),
                )
            )
        return PresensiHistoryResponse(data=items, total=len(items))

    def list_active_sessions(self, nim: str) -> ActiveSessionListResponse:
        """List persistent attendance sessions for the student's class."""
        kelas_nama = self._get_student_kelas_nama(nim)
        if not kelas_nama:
            return ActiveSessionListResponse(data=[], total=0)

        jadwals = self.jadwal_repo.list_by_kelas_nama(kelas_nama)
        jadwal_map = {str(j["id"]): j for j in jadwals if j.get("id")}
        sessions = self.kehadiran_repo.list_sesi_by_jadwal_ids(list(jadwal_map.keys()))

        items = [
            ActiveSessionItem(
                sesi_presensi_id=str(sesi["id"]),
                jadwal_id=str(sesi["jadwal_id"]),
                matkul_nama=str(jadwal_map.get(str(sesi["jadwal_id"]), {}).get("matkul_nama") or "-"),
                kelas_nama=str(
                    jadwal_map.get(str(sesi["jadwal_id"]), {}).get("kelas_nama") or kelas_nama
                ),
                ruangan_nama=jadwal_map.get(str(sesi["jadwal_id"]), {}).get("ruangan_nama"),
                jam_mulai=format_hhmm(jadwal_map.get(str(sesi["jadwal_id"]), {}).get("jam_mulai"))
                if jadwal_map.get(str(sesi["jadwal_id"]), {}).get("jam_mulai")
                else None,
                jam_selesai=format_hhmm(jadwal_map.get(str(sesi["jadwal_id"]), {}).get("jam_selesai"))
                if jadwal_map.get(str(sesi["jadwal_id"]), {}).get("jam_selesai")
                else None,
            )
            for sesi in sessions
        ]
        return ActiveSessionListResponse(data=items, total=len(items))

    def submit_gps_attendance(
        self,
        nim: str,
        payload: GpsAttendanceRequest,
    ) -> AttendanceRecordResponse:
        """Validate GPS accuracy & campus geofence and record DB attendance if session is active."""
        student = self._get_student_or_404(nim)
        distance = self._validate_gps_radius(
            payload.latitude,
            payload.longitude,
            accuracy=payload.accuracy,
        )

        now = common.now_wib()
        jam_masuk = now.strftime("%H:%M:%S")
        hhmm = now.strftime("%H:%M")

        tanggal_iso = now.date().isoformat()
        sesi = self._resolve_target_session(student, payload.sesi_presensi_id, None)
        jadwal = self._validate_jadwal(sesi, student)

        saved = self.kehadiran_repo.upsert_kehadiran(
            sesi_presensi_id=str(sesi["id"]),
            nim=nim,
            tanggal_iso=tanggal_iso,
            fields={
                "status": "hadir",
                "jam_masuk": jam_masuk,
                "catatan": payload.catatan or f"Presensi GPS (jarak {distance:.1f} m)",
            },
        )
        saved_id = str(saved["id"])

        course_name = jadwal.get("matkul_nama") if jadwal else None
        return AttendanceRecordResponse(
            method="gps",
            nim=nim,
            status="hadir",
            message="Absen GPS berhasil ✅",
            kehadiran_id=saved_id,
            sesi_presensi_id=str(sesi["id"]),
            jadwal_id=str(sesi["jadwal_id"]),
            tanggal=tanggal_iso,
            date=now.strftime("%d"),
            time=hhmm,
            jam_masuk=jam_masuk,
            matkul_nama=course_name,
            courseName=course_name or "Presensi Kampus",
            kelas=jadwal.get("kelas_nama") if jadwal else self._extract_student_kelas_nama(student),
            distance_meters=int(round(distance)),
            jarak_meter=round(distance, 2),
            area=self.settings.geofence_name,
            radius_meters=self.settings.max_gps_distance_meters,
        )

    def validate_room_qr(
        self,
        nim: str,
        payload: ValidateRoomQrRequest,
    ) -> ValidateRoomQrResponse:
        """Validate static door QR scanned by student before unlocking live camera face scan."""
        student = self._get_student_or_404(nim)
        if payload.latitude is not None and payload.longitude is not None:
            self._validate_gps_radius(
                payload.latitude,
                payload.longitude,
                accuracy=payload.accuracy,
            )

        sesi = self._resolve_target_session(student, sesi_presensi_id=None, qr_token=payload.qr_token)
        jadwal = self._validate_jadwal(sesi, student)

        ruangan_kode = str(jadwal.get("ruangan_kode") if jadwal else "").strip()
        ruangan_nama = str((jadwal.get("ruangan_nama") if jadwal else "") or ruangan_kode or "Ruangan Kelas").strip()
        matkul_nama = str((jadwal.get("matkul_nama") if jadwal else "") or "Perkuliahan").strip()
        jam_mulai = format_hhmm(jadwal.get("jam_mulai")) if (jadwal and jadwal.get("jam_mulai")) else None
        jam_selesai = format_hhmm(jadwal.get("jam_selesai")) if (jadwal and jadwal.get("jam_selesai")) else None
        kelas_nama = (jadwal.get("kelas_nama") if jadwal else None) or self._extract_student_kelas_nama(student)

        return ValidateRoomQrResponse(
            valid=True,
            ruangan_kode=ruangan_kode,
            ruangan_nama=ruangan_nama,
            sesi_presensi_id=str(sesi["id"]),
            jadwal_id=str(sesi["jadwal_id"]),
            matkul_nama=matkul_nama,
            jam_mulai=jam_mulai,
            jam_selesai=jam_selesai,
            kelas_nama=kelas_nama,
            qr_token=payload.qr_token,
            message=f"Pintu ruangan {ruangan_nama} terverifikasi untuk {matkul_nama}. Lanjutkan ke verifikasi wajah.",
        )

    def submit_face_attendance(
        self,
        nim: str,
        image_bytes: bytes,
        sesi_presensi_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        accuracy: float | None = None,
        catatan: str | None = None,
    ) -> AttendanceRecordResponse:
        """Verify face with ML engine, validate session/GPS, and record `kehadiran` without storing the photo."""
        student = self._get_student_or_404(nim)
        distance: float | None = None
        if latitude is not None and longitude is not None:
            distance = self._validate_gps_radius(latitude, longitude, accuracy=accuracy)

        now = common.now_wib()
        tanggal_iso = now.date().isoformat()
        sesi = self._resolve_target_session(student, sesi_presensi_id, None)
        jadwal = self._validate_jadwal(sesi, student)

        result, _ = self.face_service.verify_for_attendance(nim=nim, image_bytes=image_bytes)
        if not result.matched:
            if not (self.settings.testing_bypass_session and result.similarity > 0.10):
                raise ForbiddenError(
                    f"Verifikasi wajah ditolak: {result.label} "
                    f"(kemiripan={result.similarity:.4f}, batas minimum={result.threshold:.2f})."
                )

        jam_masuk = now.strftime("%H:%M:%S")
        note = catatan or f"Presensi wajah terverifikasi (similarity={result.similarity:.4f})"
        saved = self.kehadiran_repo.upsert_kehadiran(
            sesi_presensi_id=str(sesi["id"]),
            nim=nim,
            tanggal_iso=tanggal_iso,
            fields={
                "status": "hadir",
                "jam_masuk": jam_masuk,
                "catatan": note,
            },
        )

        course_name = jadwal.get("matkul_nama") if jadwal else None
        return AttendanceRecordResponse(
            method="face",
            nim=nim,
            status="hadir",
            message="Presensi pengenalan wajah berhasil dicatat.",
            kehadiran_id=str(saved["id"]),
            sesi_presensi_id=str(sesi["id"]),
            jadwal_id=str(sesi["jadwal_id"]),
            tanggal=tanggal_iso,
            date=now.strftime("%d"),
            time=now.strftime("%H:%M"),
            jam_masuk=jam_masuk,
            matkul_nama=course_name,
            courseName=course_name,
            kelas=jadwal.get("kelas_nama") if jadwal else None,
            distance_meters=distance,
            similarity=result.similarity,
            threshold=result.threshold,
        )

    def _validate_gps_radius(
        self,
        latitude: float,
        longitude: float,
        accuracy: float | None = None,
    ) -> float:
        distance = haversine_meters(
            latitude,
            longitude,
            self.settings.campus_latitude,
            self.settings.campus_longitude,
        )
        if self.settings.testing_bypass_location:
            return distance
        if accuracy is not None and accuracy > self.settings.geofence_max_accuracy_meters:
            raise UnprocessableError(
                f"Akurasi GPS terlalu rendah (±{accuracy:.0f} m). "
                "Aktifkan lokasi akurasi tinggi lalu coba lagi."
            )
        if distance > self.settings.max_gps_distance_meters:
            raise ForbiddenError(
                f"Lokasi di luar area {self.settings.geofence_name}: {distance:.0f} m dari titik presensi, "
                f"batas {self.settings.max_gps_distance_meters:.0f} m."
            )
        return distance

    def _resolve_target_session(
        self,
        student: dict[str, Any],
        sesi_presensi_id: str | None,
        qr_token: str | None,
    ) -> dict[str, Any]:
        """Resolve the persistent session for a student via ID, static room QR, or current jadwal."""
        if sesi_presensi_id:
            sesi = self.kehadiran_repo.get_sesi_by_id(sesi_presensi_id)
            if not sesi:
                raise NotFoundError("Sesi presensi tidak ditemukan.")
            return sesi

        kelas_nama = self._extract_student_kelas_nama(student)
        if not kelas_nama:
            raise ForbiddenError("Akun Anda belum terdaftar di kelas.")

        jadwals = self.jadwal_repo.list_by_kelas_nama(kelas_nama)
        if not jadwals:
            raise NotFoundError(f"Tidak ada jadwal ditemukan untuk kelas {kelas_nama}.")

        now = common.now_wib()
        if qr_token:
            cleaned = qr_token.strip()
            prefix = "HADIRIN:ROOM:"
            room_code = (
                cleaned[len(prefix):].strip().upper()
                if cleaned.upper().startswith(prefix)
                else cleaned.upper()
            )
            matched = [
                j for j in jadwals
                if str(j.get("ruangan_kode") or "").strip().upper() == room_code
                or str(j.get("ruangan_nama") or "").strip().upper() == room_code
            ]
            if not matched:
                raise ForbiddenError(
                    f"QR Ruangan '{room_code}' tidak cocok dengan jadwal kelas '{kelas_nama}'."
                )
            in_window = [j for j in matched if self._within_jadwal_window(j, now)]
            if not in_window:
                raise ForbiddenError(
                    f"QR Ruangan '{room_code}' hanya dapat dipakai saat jadwal kelas '{kelas_nama}' berlangsung "
                    "(toleransi 1 jam)."
                )
            if len(in_window) > 1:
                raise BadRequestError(
                    "Beberapa jadwal kelas cocok dengan ruangan dan waktu ini; sertakan `sesi_presensi_id`."
                )
            target = in_window[0]
        else:
            in_window = [j for j in jadwals if self._within_jadwal_window(j, now)]
            if not in_window:
                raise NotFoundError(
                    "Tidak ada jadwal kelas yang berlangsung sekarang (toleransi 1 jam); "
                    "sertakan `sesi_presensi_id`."
                )
            if len(in_window) > 1:
                raise BadRequestError(
                    "Lebih dari satu jadwal kelas berlangsung sekarang; sertakan `sesi_presensi_id`."
                )
            target = in_window[0]

        sesi = self.kehadiran_repo.get_sesi_by_jadwal_id(str(target["id"]))
        if not sesi:
            raise NotFoundError("Sesi presensi untuk jadwal ini tidak ditemukan.")
        return sesi

    @staticmethod
    def _within_jadwal_window(jadwal: dict[str, Any], now: datetime) -> bool:
        """Return True when `now` matches the weekday and time window of a jadwal (±1 hour)."""
        hari = str(jadwal.get("hari") or "").lower()
        if hari != WEEKDAY_TO_HARI.get(now.weekday()):
            return False
        mulai = format_hhmm(jadwal.get("jam_mulai"))
        selesai = format_hhmm(jadwal.get("jam_selesai"))
        if not mulai or not selesai:
            return False
        start = datetime.combine(
            now.date(), datetime.strptime(mulai, "%H:%M").time(), tzinfo=common.WIB
        )
        end = datetime.combine(
            now.date(), datetime.strptime(selesai, "%H:%M").time(), tzinfo=common.WIB
        )
        return start - WINDOW_TOLERANCE <= now <= end + WINDOW_TOLERANCE

    def _validate_jadwal(
        self,
        sesi: dict[str, Any],
        student: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Validate that the session belongs to the student's class and is active now."""
        student_kelas_id = student.get("kelas_id")
        student_kelas_nama = self._extract_student_kelas_nama(student)
        if not student_kelas_id and not student_kelas_nama:
            raise ForbiddenError("Akun Anda belum terdaftar di kelas.")

        jadwal_id = str(sesi["jadwal_id"])
        jadwal = self.jadwal_repo.get_by_id(jadwal_id)
        if not jadwal:
            raise NotFoundError("Jadwal untuk sesi ini tidak ditemukan.")

        jadwal_kelas_id = self.jadwal_repo.get_kelas_id(jadwal_id)
        if student_kelas_id and jadwal_kelas_id:
            if str(student_kelas_id) != str(jadwal_kelas_id):
                raise ForbiddenError("QR Code ini bukan untuk kelas Anda.")
        elif (
            student_kelas_nama
            and jadwal.get("kelas_nama")
            and str(jadwal["kelas_nama"]).lower() != str(student_kelas_nama).lower()
        ):
            raise ForbiddenError("QR Code ini bukan untuk kelas Anda.")

        if not self._within_jadwal_window(jadwal, common.now_wib()):
            raise ForbiddenError("Presensi hanya dapat dilakukan saat jadwal kelas berlangsung (toleransi 1 jam).")
        return jadwal

    def _extract_student_kelas_nama(self, student: dict[str, Any]) -> str | None:
        kelas = student.get("kelas") or {}
        if isinstance(kelas, list):
            kelas = kelas[0] if kelas else {}
        return kelas.get("nama")

    def _get_student_or_404(self, nim: str) -> dict[str, Any]:
        student = self.mahasiswa_repo.get_by_nim(nim)
        if not student:
            raise NotFoundError(f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.")
        return student

    def _get_student_kelas_nama(self, nim: str) -> str | None:
        return self._extract_student_kelas_nama(self._get_student_or_404(nim))

