"""Service for attendance summary, history, QR check-in, and face check-in."""

from datetime import datetime
from typing import Any
from uuid import uuid4

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
    QrAttendanceRequest,
)
from app.services import common
from app.services.common import STATUS_LABELS, format_hhmm, haversine_meters
from app.services.face_recognition.face_service import FaceService


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
        """Fetch attendance history from `v_rekap_kehadiran` enriched with photo paths."""
        self._get_student_or_404(nim)
        rows = self.kehadiran_repo.list_rekap_by_nim(
            nim=nim,
            status_filter=status_filter,
            limit=limit,
        )
        raw_rows = self.kehadiran_repo.list_kehadiran_by_nim(nim)
        photo_map = {
            str(r["id"]): r.get("face_photo_path")
            for r in raw_rows
            if r.get("id")
        }

        items: list[PresensiHistoryItem] = []
        for row in rows:
            st = (row.get("status") or "hadir").lower()
            jam_masuk = format_hhmm(row.get("jam_masuk")) if row.get("jam_masuk") else "-"
            kehadiran_id = str(row["kehadiran_id"])
            tanggal = str(row.get("tanggal") or "")
            matkul = str(row.get("matkul_nama") or "-")
            face_path = photo_map.get(kehadiran_id)
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
                    face_photo_path=face_path,
                    face_photo_url=(
                        self.kehadiran_repo.create_signed_url(
                            self.settings.storage_bucket_presensi,
                            face_path,
                        )
                        if face_path
                        else None
                    ),
                )
            )
        return PresensiHistoryResponse(data=items, total=len(items))

    def list_active_sessions(self, nim: str) -> ActiveSessionListResponse:
        """List currently open attendance sessions for the student's class."""
        kelas_nama = self._get_student_kelas_nama(nim)
        if not kelas_nama:
            return ActiveSessionListResponse(data=[], total=0)

        jadwals = self.jadwal_repo.list_by_kelas_nama(kelas_nama)
        jadwal_map = {str(j["id"]): j for j in jadwals if j.get("id")}

        open_sessions = self.kehadiran_repo.list_open_sesi_by_jadwal_ids(list(jadwal_map.keys()))

        if self.settings.testing_bypass_session and not open_sessions and jadwals:
            today_iso = common.now_wib().date().isoformat()
            target_j = jadwals[0]
            if target_j.get("id"):
                existing = self.kehadiran_repo.get_sesi_by_jadwal_and_date(str(target_j["id"]), today_iso)
                if existing:
                    if not existing.get("is_open"):
                        self.kehadiran_repo.client.table("sesi_presensi").update({"is_open": True}).eq("id", existing["id"]).execute()
                else:
                    self.kehadiran_repo.create_sesi_presensi({
                        "jadwal_id": str(target_j["id"]),
                        "tanggal": today_iso,
                        "is_open": True,
                        "qr_token": f"TEST_{uuid4().hex[:12]}",
                    })
                open_sessions = self.kehadiran_repo.list_open_sesi_by_jadwal_ids(list(jadwal_map.keys()))

        items: list[ActiveSessionItem] = []
        for sesi in open_sessions:
            jadwal = jadwal_map.get(str(sesi["jadwal_id"]), {})
            items.append(
                ActiveSessionItem(
                    sesi_presensi_id=str(sesi["id"]),
                    jadwal_id=str(sesi["jadwal_id"]),
                    tanggal=str(sesi["tanggal"]),
                    matkul_nama=str(jadwal.get("matkul_nama") or "-"),
                    kelas_nama=str(jadwal.get("kelas_nama") or kelas_nama),
                    ruangan_nama=jadwal.get("ruangan_nama"),
                    jam_mulai=format_hhmm(jadwal.get("jam_mulai")) if jadwal.get("jam_mulai") else None,
                    jam_selesai=format_hhmm(jadwal.get("jam_selesai")) if jadwal.get("jam_selesai") else None,
                    is_open=bool(sesi.get("is_open")),
                    qr_expires_at=sesi.get("qr_expires_at"),
                )
            )
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

        sesi: dict[str, Any] | None = None
        jadwal: dict[str, Any] | None = None
        if payload.sesi_presensi_id:
            sesi = self._resolve_target_session(student, payload.sesi_presensi_id, None)
            jadwal = self._validate_open_session(sesi, student)
        else:
            kelas_nama = self._extract_student_kelas_nama(student)
            if kelas_nama:
                jadwals = self.jadwal_repo.list_by_kelas_nama(kelas_nama)
                open_sessions = self.kehadiran_repo.list_open_sesi_by_jadwal_ids(
                    jadwal_ids=[str(j["id"]) for j in jadwals if j.get("id")],
                    tanggal_iso=now.date().isoformat(),
                )
                if len(open_sessions) == 1:
                    sesi = open_sessions[0]
                    jadwal = self._validate_open_session(sesi, student)

        saved_id: str | None = None
        if sesi is not None:
            saved = self.kehadiran_repo.upsert_kehadiran(
                sesi_presensi_id=str(sesi["id"]),
                nim=nim,
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
            sesi_presensi_id=str(sesi["id"]) if sesi else None,
            jadwal_id=str(sesi["jadwal_id"]) if sesi else None,
            tanggal=str(sesi["tanggal"]) if sesi else now.date().isoformat(),
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

    def submit_qr_attendance(
        self,
        nim: str,
        payload: QrAttendanceRequest,
    ) -> AttendanceRecordResponse:
        """Validate live `sesi_presensi` QR token + optional GPS radius and record `kehadiran`."""
        student = self._get_student_or_404(nim)
        distance: float | None = None
        if payload.latitude is not None and payload.longitude is not None:
            distance = self._validate_gps_radius(
                payload.latitude,
                payload.longitude,
                accuracy=payload.accuracy,
            )

        sesi = self.kehadiran_repo.get_sesi_by_qr_token(payload.qr_token)
        if not sesi:
            raise ForbiddenError("QR Code tidak valid atau sudah diganti. Pindai QR terbaru.")
        jadwal = self._validate_open_session(sesi, student)

        existing = self.kehadiran_repo.get_kehadiran_by_sesi_and_nim(str(sesi["id"]), nim)
        if existing and existing.get("status") == "hadir":
            jam_masuk = str(existing.get("jam_masuk") or "")
            course_name = jadwal.get("matkul_nama") if jadwal else None
            return AttendanceRecordResponse(
                method="qr",
                nim=nim,
                status="hadir",
                message="Presensi QR untuk sesi ini sudah tercatat.",
                kehadiran_id=str(existing["id"]),
                sesi_presensi_id=str(sesi["id"]),
                jadwal_id=str(sesi["jadwal_id"]),
                tanggal=str(sesi["tanggal"]),
                date=str(sesi["tanggal"]).split("-")[-1],
                time=format_hhmm(jam_masuk) if jam_masuk else common.now_wib().strftime("%H:%M"),
                jam_masuk=jam_masuk or None,
                matkul_nama=course_name,
                courseName=course_name,
                kelas=jadwal.get("kelas_nama") if jadwal else None,
                distance_meters=round(distance, 2) if distance is not None else None,
            )

        now = common.now_wib()
        jam_masuk = now.strftime("%H:%M:%S")
        note_suffix = f" (jarak {distance:.1f} m)" if distance is not None else ""
        saved = self.kehadiran_repo.upsert_kehadiran(
            sesi_presensi_id=str(sesi["id"]),
            nim=nim,
            fields={
                "status": "hadir",
                "jam_masuk": jam_masuk,
                "catatan": payload.catatan or f"Presensi QR{note_suffix}",
            },
        )
        course_name = jadwal.get("matkul_nama") if jadwal else None
        return AttendanceRecordResponse(
            method="qr",
            nim=nim,
            status="hadir",
            message="Presensi QR berhasil dicatat.",
            kehadiran_id=str(saved["id"]),
            sesi_presensi_id=str(sesi["id"]),
            jadwal_id=str(sesi["jadwal_id"]),
            tanggal=str(sesi["tanggal"]),
            date=str(sesi["tanggal"]).split("-")[-1],
            time=now.strftime("%H:%M"),
            jam_masuk=jam_masuk,
            matkul_nama=course_name,
            courseName=course_name,
            kelas=jadwal.get("kelas_nama") if jadwal else None,
            distance_meters=round(distance, 2) if distance is not None else None,
        )

    def submit_face_attendance(
        self,
        nim: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
        sesi_presensi_id: str | None = None,
        qr_token: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        accuracy: float | None = None,
        catatan: str | None = None,
    ) -> AttendanceRecordResponse:
        """Verify student's face with ML engine, validate open session/GPS, and record `kehadiran`."""
        student = self._get_student_or_404(nim)
        distance: float | None = None
        if latitude is not None and longitude is not None:
            distance = self._validate_gps_radius(latitude, longitude, accuracy=accuracy)

        sesi = self._resolve_target_session(student, sesi_presensi_id, qr_token)
        jadwal = self._validate_open_session(sesi, student, bypass_time_checks=self.settings.testing_bypass_session)

        result, _ = self.face_service.verify_for_attendance(nim=nim, image_bytes=image_bytes)
        if not result.matched:
            raise ForbiddenError(
                f"Verifikasi wajah ditolak: {result.label} "
                f"(kemiripan={result.similarity:.4f}, batas minimum={result.threshold:.2f})."
            )

        ext, mime = self.face_service.normalize_uploaded_metadata("probe.jpg", content_type, 1)
        storage_path = f"{nim}/{sesi['id']}_{uuid4().hex[:10]}.{ext}"
        self.kehadiran_repo.upload_attendance_photo(
            storage_path=storage_path,
            content=image_bytes,
            content_type=mime,
        )

        now = common.now_wib()
        jam_masuk = now.strftime("%H:%M:%S")
        note = catatan or f"Presensi wajah terverifikasi (similarity={result.similarity:.4f})"
        try:
            saved = self.kehadiran_repo.upsert_kehadiran(
                sesi_presensi_id=str(sesi["id"]),
                nim=nim,
                fields={
                    "status": "hadir",
                    "jam_masuk": jam_masuk,
                    "catatan": note,
                    "face_photo_path": storage_path,
                },
            )
        except Exception:
            self.kehadiran_repo.delete_attendance_photo(storage_path)
            raise

        course_name = jadwal.get("matkul_nama") if jadwal else None
        signed_photo_url = self.kehadiran_repo.create_signed_url(
            self.settings.storage_bucket_presensi,
            storage_path,
        )
        return AttendanceRecordResponse(
            method="face",
            nim=nim,
            status="hadir",
            message="Presensi pengenalan wajah berhasil dicatat.",
            kehadiran_id=str(saved["id"]),
            sesi_presensi_id=str(sesi["id"]),
            jadwal_id=str(sesi["jadwal_id"]),
            tanggal=str(sesi["tanggal"]),
            date=str(sesi["tanggal"]).split("-")[-1],
            time=now.strftime("%H:%M"),
            jam_masuk=jam_masuk,
            matkul_nama=course_name,
            courseName=course_name,
            kelas=jadwal.get("kelas_nama") if jadwal else None,
            distance_meters=distance,
            similarity=result.similarity,
            threshold=result.threshold,
            face_photo_path=storage_path,
            face_photo_url=signed_photo_url,
        )

    def _validate_gps_radius(
        self,
        latitude: float,
        longitude: float,
        accuracy: float | None = None,
    ) -> float:
        if accuracy is not None and accuracy > self.settings.geofence_max_accuracy_meters:
            raise UnprocessableError(
                f"Akurasi GPS terlalu rendah (±{accuracy:.0f} m). "
                "Aktifkan lokasi akurasi tinggi lalu coba lagi."
            )
        distance = haversine_meters(
            latitude,
            longitude,
            self.settings.campus_latitude,
            self.settings.campus_longitude,
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
        if sesi_presensi_id:
            sesi = self.kehadiran_repo.get_sesi_by_id(sesi_presensi_id)
            if not sesi:
                raise NotFoundError("Sesi presensi tidak ditemukan.")
            return sesi

        if qr_token:
            sesi = self.kehadiran_repo.get_sesi_by_qr_token(qr_token)
            if not sesi:
                raise ForbiddenError("Token QR sesi presensi tidak valid.")
            return sesi

        kelas_nama = self._extract_student_kelas_nama(student)
        if not kelas_nama:
            raise ForbiddenError("Akun Anda belum terdaftar di kelas.")

        jadwals = self.jadwal_repo.list_by_kelas_nama(kelas_nama)
        if not jadwals:
            raise NotFoundError("Tidak ada jadwal ditemukan untuk kelas Anda.")

        # Testing mode: auto-pick or create a session for today using the first schedule
        if self.settings.testing_bypass_session:
            today_iso = common.now_wib().date().isoformat()
            # Try to find any existing open session today (regardless of is_open flag)
            all_sessions = self.kehadiran_repo.list_open_sesi_by_jadwal_ids(
                jadwal_ids=[str(j["id"]) for j in jadwals if j.get("id")],
            )
            today_sessions = [s for s in all_sessions if str(s.get("tanggal", "")).startswith(today_iso)]
            if today_sessions:
                return today_sessions[0]
            # Auto-create a testing session using the first schedule of the class
            jadwal = jadwals[0]
            existing = self.kehadiran_repo.get_sesi_by_jadwal_and_date(str(jadwal["id"]), today_iso)
            if existing:
                if not existing.get("is_open"):
                    self.kehadiran_repo.client.table("sesi_presensi").update({"is_open": True}).eq("id", existing["id"]).execute()
                    existing = {**existing, "is_open": True}
                return existing
            return self.kehadiran_repo.create_sesi_presensi(
                {
                    "jadwal_id": str(jadwal["id"]),
                    "tanggal": today_iso,
                    "is_open": True,
                    "qr_token": f"TEST_{uuid4().hex[:12]}",
                }
            )

        open_sessions = self.kehadiran_repo.list_open_sesi_by_jadwal_ids(
            jadwal_ids=[str(j["id"]) for j in jadwals if j.get("id")],
            tanggal_iso=common.now_wib().date().isoformat(),
        )
        if not open_sessions:
            raise NotFoundError("Tidak ada sesi presensi yang sedang dibuka untuk kelas Anda hari ini.")
        if len(open_sessions) > 1:
            raise BadRequestError(
                "Terdapat lebih dari satu sesi presensi aktif hari ini; sertakan `sesi_presensi_id`."
            )
        return open_sessions[0]

    def _validate_open_session(
        self,
        sesi: dict[str, Any],
        student: dict[str, Any],
        bypass_time_checks: bool = False,
    ) -> dict[str, Any] | None:
        if not bypass_time_checks:
            if not sesi.get("is_open"):
                raise ForbiddenError("Sesi presensi sudah ditutup.")

            expires_raw = sesi.get("qr_expires_at")
            if expires_raw:
                parsed = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=common.WIB)
                if common.now_wib() >= parsed:
                    raise ForbiddenError("QR Code sudah kedaluwarsa. Pindai QR terbaru.")

        student_kelas_id = student.get("kelas_id")
        student_kelas_nama = self._extract_student_kelas_nama(student)
        if not student_kelas_id and not student_kelas_nama:
            raise ForbiddenError("Akun Anda belum terdaftar di kelas.")

        jadwal = self.jadwal_repo.get_by_id(str(sesi["jadwal_id"]))
        if jadwal:
            jadwal_kelas_id = jadwal.get("kelas_id")
            if student_kelas_id and jadwal_kelas_id:
                if str(student_kelas_id) != str(jadwal_kelas_id):
                    raise ForbiddenError("QR Code ini bukan untuk kelas Anda.")
            elif (
                student_kelas_nama
                and jadwal.get("kelas_nama")
                and str(jadwal["kelas_nama"]).lower() != str(student_kelas_nama).lower()
            ):
                raise ForbiddenError("QR Code ini bukan untuk kelas Anda.")

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

