"""Service for student absence permissions (`surat izin`/`sakit`) and Storage uploads."""

from datetime import date
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.db.repositories import (
    JadwalRepository,
    KehadiranRepository,
    MahasiswaRepository,
    PengajuanRepository,
)
from app.schemas.auth import MessageResponse
from app.schemas.pengajuan import (
    DocumentUploadResponse,
    PengajuanItem,
    PengajuanListResponse,
    PengajuanMutationResponse,
    PengajuanUpdateRequest,
)
from app.services.common import now_wib

ALLOWED_DOC_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

ALLOWED_DOC_MIMES: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
}

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
KOMPENSASI_TAG = "[Kompensasi]"


def _normalize_jenis_for_db(raw_jenis: str, alasan: str) -> tuple[str, str, str]:
    """Map API `jenis` (`izin`/`sakit`/`kompensasi`) to DB `status_kehadiran` and tagged reason."""
    normalized = (raw_jenis or "").strip().lower()
    if normalized not in ("izin", "sakit", "kompensasi"):
        raise BadRequestError("Jenis pengajuan harus bernilai 'izin', 'sakit', atau 'kompensasi'.")
    cleaned_alasan = (alasan or "").strip()
    if normalized == "kompensasi":
        if not cleaned_alasan.startswith(KOMPENSASI_TAG):
            cleaned_alasan = f"{KOMPENSASI_TAG} {cleaned_alasan}".strip()
        return "izin", "kompensasi", cleaned_alasan
    return normalized, normalized, cleaned_alasan


class PengajuanService:
    """Manages absence permission records in `pengajuan_ketidakhadiran` and `dokumen-pengajuan`."""

    def __init__(
        self,
        mahasiswa_repo: MahasiswaRepository,
        jadwal_repo: JadwalRepository,
        kehadiran_repo: KehadiranRepository,
        pengajuan_repo: PengajuanRepository,
    ) -> None:
        self.mahasiswa_repo = mahasiswa_repo
        self.jadwal_repo = jadwal_repo
        self.kehadiran_repo = kehadiran_repo
        self.pengajuan_repo = pengajuan_repo

    def upload_document(
        self,
        nim: str,
        filename: str | None,
        content: bytes,
        content_type: str | None = None,
    ) -> DocumentUploadResponse:
        """Validate and upload a supporting letter file (`PDF/JPG/PNG`, max 5 MB) to Storage."""
        self._get_student_or_404(nim)
        safe_name, mime = self._validate_document(filename, content, content_type)
        storage_path = f"{nim}/{uuid4().hex[:12]}_{safe_name}"

        self.pengajuan_repo.upload_document(
            storage_path=storage_path,
            content=content,
            content_type=mime,
        )
        signed_url = self.pengajuan_repo.get_document_signed_url(storage_path)

        return DocumentUploadResponse(
            message="Dokumen surat izin berhasil diunggah.",
            dokumen_path=storage_path,
            dokumen_url=signed_url,
            content_type=mime,
            size_bytes=len(content),
        )

    def list_pengajuan(self, nim: str) -> PengajuanListResponse:
        """List all absence requests submitted by the student with course names and signed URLs."""
        self._get_student_or_404(nim)
        rows = self.pengajuan_repo.list_by_nim(nim)
        jadwal_cache: dict[str, dict[str, Any]] = {}
        items = [self._to_pengajuan_item(row, nim, jadwal_cache) for row in rows]
        return PengajuanListResponse(data=items, total=len(items))

    def create_pengajuan(
        self,
        nim: str,
        jenis: str,
        alasan: str,
        matakuliah: str | None = None,
        tanggal: str | None = None,
        sesi_presensi_id: str | None = None,
        jadwal_id: str | None = None,
        dokumen_path: str | None = None,
        file_bytes: bytes | None = None,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> PengajuanMutationResponse:
        """Create a real `pengajuan_ketidakhadiran` entry with optional Storage document upload."""
        student = self._get_student_or_404(nim)
        if len((alasan or "").strip()) < 3:
            raise BadRequestError("Alasan ketidakhadiran minimal 3 karakter.")

        db_jenis, _, cleaned_alasan = _normalize_jenis_for_db(jenis, alasan)

        tanggal_iso = self._parse_date_iso(tanggal)
        sesi, resolved_jadwal = self._resolve_or_create_sesi(
            student=student,
            sesi_presensi_id=sesi_presensi_id,
            jadwal_id=jadwal_id,
            matakuliah=matakuliah,
            tanggal_iso=tanggal_iso,
        )

        uploaded_path: str | None = None
        if file_bytes is not None:
            safe_name, mime = self._validate_document(filename, file_bytes, content_type)
            uploaded_path = f"{nim}/{uuid4().hex[:12]}_{safe_name}"
            self.pengajuan_repo.upload_document(uploaded_path, file_bytes, mime)

        final_doc_path = uploaded_path or (dokumen_path.strip() if dokumen_path else None)

        created_kehadiran_here = False
        existing_kehadiran = self.kehadiran_repo.get_kehadiran_by_sesi_and_nim(
            str(sesi["id"]),
            nim,
        )
        if existing_kehadiran and self.pengajuan_repo.get_by_kehadiran_id(str(existing_kehadiran["id"])):
            if uploaded_path:
                self.pengajuan_repo.delete_document(uploaded_path)
            raise ConflictError("Pengajuan untuk mata kuliah dan tanggal tersebut sudah ada.")

        try:
            if existing_kehadiran:
                kehadiran_row = existing_kehadiran
            else:
                kehadiran_row = self.kehadiran_repo.upsert_kehadiran(
                    sesi_presensi_id=str(sesi["id"]),
                    nim=nim,
                    fields={"status": db_jenis},
                )
                created_kehadiran_here = True

            created = self.pengajuan_repo.create(
                {
                    "kehadiran_id": kehadiran_row["id"],
                    "jenis": db_jenis,
                    "alasan": cleaned_alasan,
                    "dokumen_path": final_doc_path,
                    "status_pengajuan": "pending",
                }
            )
        except Exception:
            if uploaded_path:
                self.pengajuan_repo.delete_document(uploaded_path)
            if created_kehadiran_here and "kehadiran_row" in locals():
                try:
                    self.kehadiran_repo.delete_kehadiran_by_id(str(kehadiran_row["id"]))
                except Exception:
                    pass
            raise

        jadwal_cache: dict[str, dict[str, Any]] = {}
        if resolved_jadwal and resolved_jadwal.get("id"):
            jadwal_cache[str(resolved_jadwal["id"])] = resolved_jadwal

        return PengajuanMutationResponse(
            message="Pengajuan ketidakhadiran berhasil dikirim.",
            data=self._to_pengajuan_item(created, nim, jadwal_cache),
        )

    def update_pengajuan(
        self,
        nim: str,
        pengajuan_id: str,
        payload: PengajuanUpdateRequest,
    ) -> PengajuanMutationResponse:
        """Update an existing pending absence request belonging to the student."""
        existing = self._get_owned_pengajuan_or_404(nim, pengajuan_id)
        if existing.get("status_pengajuan") != "pending":
            raise BadRequestError("Pengajuan yang sudah diproses tidak dapat diubah.")

        fields: dict[str, Any] = {}
        next_db_jenis: str | None = None
        if payload.jenis is not None:
            base_alasan = payload.alasan or str(existing.get("alasan") or "")
            db_jenis, _, updated_alasan = _normalize_jenis_for_db(payload.jenis, base_alasan)
            fields["jenis"] = db_jenis
            next_db_jenis = db_jenis
            if payload.jenis == "kompensasi" or payload.alasan is not None:
                fields["alasan"] = updated_alasan
        elif payload.alasan is not None:
            fields["alasan"] = payload.alasan.strip()
        if payload.dokumen_path is not None:
            fields["dokumen_path"] = payload.dokumen_path.strip() or None

        updated = self.pengajuan_repo.update_by_id(pengajuan_id, fields)
        if not updated:
            raise NotFoundError("Pengajuan tidak ditemukan.")

        if next_db_jenis is not None and existing.get("kehadiran_id"):
            sesi_id = (existing.get("kehadiran") or {}).get("sesi_presensi_id")
            if sesi_id:
                self.kehadiran_repo.upsert_kehadiran(
                    sesi_presensi_id=str(sesi_id),
                    nim=nim,
                    fields={"status": next_db_jenis},
                )

        return PengajuanMutationResponse(
            message="Pengajuan berhasil diperbarui.",
            data=self._to_pengajuan_item(updated, nim, {}),
        )

    def delete_pengajuan(self, nim: str, pengajuan_id: str) -> MessageResponse:
        """Cancel/delete a pending absence request and remove any uploaded document."""
        existing = self._get_owned_pengajuan_or_404(nim, pengajuan_id)
        if existing.get("status_pengajuan") != "pending":
            raise BadRequestError("Pengajuan yang sudah diproses tidak dapat dihapus.")

        self.pengajuan_repo.delete_by_id(pengajuan_id)
        self.pengajuan_repo.delete_document(existing.get("dokumen_path"))

        kehadiran = existing.get("kehadiran") or {}
        kehadiran_id = existing.get("kehadiran_id")
        if (
            kehadiran_id
            and kehadiran.get("status") in ("izin", "sakit")
        ):
            raw_list = self.kehadiran_repo.list_kehadiran_by_nim(nim)
            target = next((r for r in raw_list if str(r.get("id")) == str(kehadiran_id)), None)
            if target and not target.get("jam_masuk") and not target.get("face_photo_path") and not target.get("catatan"):
                self.kehadiran_repo.delete_kehadiran_by_id(str(kehadiran_id))

        return MessageResponse(message="Pengajuan berhasil dihapus.")

    def _resolve_or_create_sesi(
        self,
        student: dict[str, Any],
        sesi_presensi_id: str | None,
        jadwal_id: str | None,
        matakuliah: str | None,
        tanggal_iso: str,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        if sesi_presensi_id:
            sesi = self.kehadiran_repo.get_sesi_by_id(sesi_presensi_id)
            if not sesi:
                raise NotFoundError("Sesi presensi tidak ditemukan.")
            jadwal = self.jadwal_repo.get_by_id(str(sesi["jadwal_id"]))
            return sesi, jadwal

        if jadwal_id:
            jadwal = self.jadwal_repo.get_by_id(jadwal_id)
            if not jadwal:
                raise NotFoundError("Jadwal perkuliahan tidak ditemukan.")
        else:
            kelas = student.get("kelas") or {}
            if isinstance(kelas, list):
                kelas = kelas[0] if kelas else {}
            jadwal = self.jadwal_repo.find_matching_jadwal(
                kelas_nama=kelas.get("nama"),
                matakuliah_query=matakuliah,
            )
            if not jadwal:
                raise NotFoundError(
                    "Jadwal perkuliahan tidak ditemukan di database untuk pengajuan ini."
                )

        sesi = self.kehadiran_repo.get_or_create_sesi_presensi(
            jadwal_id=str(jadwal["id"]),
            tanggal_iso=tanggal_iso,
            defaults={"dibuka_oleh": jadwal.get("dosen_nip"), "is_open": False},
        )
        return sesi, jadwal

    def _to_pengajuan_item(
        self,
        row: dict[str, Any],
        nim: str,
        jadwal_cache: dict[str, dict[str, Any]],
    ) -> PengajuanItem:
        kehadiran = row.get("kehadiran") or {}
        sesi = kehadiran.get("sesi_presensi") or {}
        jadwal_id = str(sesi["jadwal_id"]) if sesi.get("jadwal_id") else None

        matakuliah: str | None = None
        if jadwal_id:
            if jadwal_id not in jadwal_cache:
                jadwal = self.jadwal_repo.get_by_id(jadwal_id)
                if jadwal:
                    jadwal_cache[jadwal_id] = jadwal
            matakuliah = (jadwal_cache.get(jadwal_id) or {}).get("matkul_nama")

        doc_path = row.get("dokumen_path")
        raw_alasan = str(row.get("alasan") or "")
        stored_jenis = str(row.get("jenis") or "")
        if stored_jenis == "izin" and raw_alasan.startswith(KOMPENSASI_TAG):
            public_jenis = "kompensasi"
        else:
            public_jenis = stored_jenis
        return PengajuanItem(
            id=str(row["id"]),
            kehadiran_id=str(row["kehadiran_id"]),
            sesi_presensi_id=str(sesi["id"]) if sesi.get("id") else None,
            jadwal_id=jadwal_id,
            nim=str(kehadiran.get("nim") or nim),
            jenis=public_jenis,
            alasan=raw_alasan,
            matakuliah=matakuliah,
            tanggal=str(sesi["tanggal"]) if sesi.get("tanggal") else None,
            dokumen_path=doc_path,
            dokumen_url=self.pengajuan_repo.get_document_signed_url(doc_path),
            status_pengajuan=str(row.get("status_pengajuan") or "pending"),
            catatan_dosen=row.get("catatan_dosen"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def _get_owned_pengajuan_or_404(self, nim: str, pengajuan_id: str) -> dict[str, Any]:
        row = self.pengajuan_repo.get_by_id(pengajuan_id)
        if not row:
            raise NotFoundError("Pengajuan tidak ditemukan.")
        owner_nim = (row.get("kehadiran") or {}).get("nim")
        if owner_nim != nim:
            raise ForbiddenError("Anda tidak memiliki akses ke pengajuan ini.")
        return row

    def _get_student_or_404(self, nim: str) -> dict[str, Any]:
        student = self.mahasiswa_repo.get_by_nim(nim)
        if not student:
            raise NotFoundError(f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.")
        return student

    @staticmethod
    def _parse_date_iso(raw_date: str | None) -> str:
        if not raw_date or not raw_date.strip():
            return now_wib().date().isoformat()
        cleaned = raw_date.strip()
        try:
            return date.fromisoformat(cleaned).isoformat()
        except ValueError as exc:
            raise BadRequestError("Format tanggal harus YYYY-MM-DD.") from exc

    @staticmethod
    def _detect_doc_extension_from_bytes(content: bytes) -> str | None:
        if content.startswith(b"%PDF"):
            return ".pdf"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if content.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        return None

    @classmethod
    def _validate_document(
        cls,
        filename: str | None,
        content: bytes,
        content_type: str | None,
    ) -> tuple[str, str]:
        if not content:
            raise BadRequestError("File dokumen yang diunggah kosong.")
        if len(content) > MAX_DOCUMENT_BYTES:
            raise BadRequestError("Ukuran file dokumen maksimal 5 MB.")

        original_name = Path(filename or "surat_izin.pdf").name
        suffix = Path(original_name).suffix.lower()
        mime = (content_type or "").split(";")[0].strip().lower()

        if suffix not in ALLOWED_DOC_EXTENSIONS:
            if mime in ALLOWED_DOC_MIMES:
                suffix = ALLOWED_DOC_MIMES[mime]
            else:
                detected = cls._detect_doc_extension_from_bytes(content)
                if detected:
                    suffix = detected
                else:
                    raise BadRequestError(
                        "Format dokumen harus PDF, JPG, JPEG, atau PNG."
                    )

        resolved_mime = ALLOWED_DOC_EXTENSIONS[suffix]
        stem = Path(original_name).stem or "dokumen"
        safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem)[:48].strip("_") or "dokumen"
        return f"{safe_stem}{suffix}", resolved_mime

