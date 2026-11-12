"""Service integrating the MTCNN + MobileFaceNet pipeline with `foto_wajah` and Storage."""

import base64
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from app.db.repositories import FotoWajahRepository, MahasiswaRepository
from app.schemas.auth import MessageResponse
from app.schemas.wajah import (
    FaceRegistrationResponse,
    FaceStatusResponse,
    FaceVerifyResponse,
)
from ml.inference.face_embedder import (
    FaceDetectionError,
    FaceRecognitionEngine,
    FaceVerificationResult,
    get_face_engine,
)

ALLOWED_IMAGE_EXTENSIONS: dict[str, tuple[str, str]] = {
    ".jpg": ("jpg", "image/jpeg"),
    ".jpeg": ("jpg", "image/jpeg"),
    ".png": ("png", "image/png"),
    ".webp": ("webp", "image/webp"),
}

ALLOWED_IMAGE_CONTENT_TYPES: dict[str, tuple[str, str]] = {
    "image/jpeg": ("jpg", "image/jpeg"),
    "image/jpg": ("jpg", "image/jpeg"),
    "image/png": ("png", "image/png"),
    "image/webp": ("webp", "image/webp"),
}

MAX_IMAGE_BYTES = 8 * 1024 * 1024


class FaceService:
    """Handles student face embedding extraction, registration, update, and verification."""

    def __init__(
        self,
        mahasiswa_repo: MahasiswaRepository,
        foto_wajah_repo: FotoWajahRepository,
        settings: Settings | None = None,
        engine: FaceRecognitionEngine | None = None,
    ) -> None:
        self.mahasiswa_repo = mahasiswa_repo
        self.foto_wajah_repo = foto_wajah_repo
        self.settings = settings or get_settings()
        self._engine = engine

    @property
    def engine(self) -> FaceRecognitionEngine:
        """Lazily initialize singleton PyTorch MTCNN + MobileFaceNet engine."""
        if self._engine is None:
            self._engine = get_face_engine(
                weights_dir=self.settings.ml_weights_dir,
                min_face_size=self.settings.mtcnn_min_face_size,
            )
        return self._engine

    def get_status(self, nim: str) -> FaceStatusResponse:
        """Return active face registration metadata and signed sample URLs for a student."""
        self._ensure_student_exists(nim)
        rows = self.foto_wajah_repo.list_by_nim(nim, active_only=True)
        paths = [str(row["storage_path"]) for row in rows if row.get("storage_path")]
        urls = [
            url
            for path in paths
            if (url := self.foto_wajah_repo.get_face_signed_url(path))
        ]
        first_emb = rows[0].get("embedding") if rows else None
        emb_dim = len(first_emb) if isinstance(first_emb, list) else None
        last_updated = max(
            (str(row.get("created_at")) for row in rows if row.get("created_at")),
            default=None,
        )
        return FaceStatusResponse(
            nim=nim,
            is_registered=len(rows) > 0,
            active_samples=len(rows),
            embedding_dimension=emb_dim,
            threshold=self.settings.face_similarity_threshold,
            storage_paths=paths,
            sample_urls=urls,
            last_updated_at=last_updated,
        )

    def register_face(
        self,
        nim: str,
        samples: list[tuple[bytes, str, str]],
    ) -> FaceRegistrationResponse:
        """Register initial face embeddings and images for a student without prior active samples."""
        self._ensure_student_exists(nim)
        existing = self.foto_wajah_repo.list_by_nim(nim, active_only=True)
        if existing:
            raise ConflictError(
                "Data wajah sudah terdaftar. Gunakan endpoint update wajah untuk memperbarui sampel."
            )
        return self._process_and_store(
            nim=nim,
            samples=samples,
            deactivate_existing=False,
            message="Registrasi data wajah berhasil.",
        )

    def update_face(
        self,
        nim: str,
        samples: list[tuple[bytes, str, str]],
    ) -> FaceRegistrationResponse:
        """Replace active face samples with newly extracted embeddings (creates if none yet)."""
        self._ensure_student_exists(nim)
        return self._process_and_store(
            nim=nim,
            samples=samples,
            deactivate_existing=True,
            message="Data wajah berhasil diperbarui.",
        )

    def delete_face(self, nim: str) -> MessageResponse:
        """Remove all stored face embeddings and Storage images for a student."""
        self._ensure_student_exists(nim)
        removed = self.foto_wajah_repo.delete_by_nim(nim)
        return MessageResponse(
            message=f"Berhasil menghapus {len(removed)} sampel data wajah untuk NIM {nim}."
        )

    def verify_face_bytes(self, nim: str, image_bytes: bytes) -> FaceVerifyResponse:
        """Verify a probe image against the student's averaged registered embeddings."""
        result, sample_count = self._compare_probe(nim, image_bytes)
        return FaceVerifyResponse(
            matched=result.matched,
            status=result.status,
            label=result.label,
            nim=nim,
            similarity=result.similarity,
            threshold=result.threshold,
            active_samples=sample_count,
        )

    def verify_for_attendance(
        self,
        nim: str,
        image_bytes: bytes,
    ) -> tuple[FaceVerificationResult, int]:
        """Run face verification for attendance check-in."""
        return self._compare_probe(nim, image_bytes)

    @staticmethod
    def decode_base64_sample(
        raw_b64: str,
        index: int = 1,
    ) -> tuple[bytes, str, str]:
        """Decode a single base64 string (or data URI) into `(bytes, filename, content_type)`."""
        value = (raw_b64 or "").strip()
        if not value:
            raise BadRequestError(f"Gambar base64 ke-{index} kosong.")

        ext = "jpg"
        content_type = "image/jpeg"
        if value.startswith("data:") and "," in value:
            header, value = value.split(",", 1)
            mime = header[5:].split(";")[0].strip().lower()
            if mime in ALLOWED_IMAGE_CONTENT_TYPES:
                ext, content_type = ALLOWED_IMAGE_CONTENT_TYPES[mime]

        try:
            decoded = base64.b64decode(value, validate=True)
        except Exception as exc:
            raise BadRequestError(f"Format base64 gambar ke-{index} tidak valid.") from exc

        if not decoded:
            raise BadRequestError(f"Gambar ke-{index} tidak berisi data.")
        return decoded, f"capture_{index}.{ext}", content_type

    @staticmethod
    def normalize_uploaded_metadata(
        filename: str | None,
        content_type: str | None,
        index: int,
    ) -> tuple[str, str]:
        """Validate image filename/content-type and return `(ext, mime)`."""
        mime = (content_type or "").split(";")[0].strip().lower()
        if mime in ALLOWED_IMAGE_CONTENT_TYPES:
            return ALLOWED_IMAGE_CONTENT_TYPES[mime]

        suffix = Path(filename or "").suffix.lower()
        if suffix in ALLOWED_IMAGE_EXTENSIONS:
            return ALLOWED_IMAGE_EXTENSIONS[suffix]

        raise BadRequestError(
            f"Format foto ke-{index} tidak didukung. Gunakan file JPG, JPEG, PNG, atau WEBP."
        )

    def _process_and_store(
        self,
        nim: str,
        samples: list[tuple[bytes, str, str]],
        deactivate_existing: bool,
        message: str,
    ) -> FaceRegistrationResponse:
        validated = self._validate_samples(samples)
        embeddings = self._extract_embeddings(validated)

        # Ensure averaged centroid embedding computes cleanly (even across diverse lighting/poses).
        avg_embedding = self.engine.compute_average_embedding(embeddings)

        batch_id = uuid4().hex[:12]
        uploaded_paths: list[str] = []
        rows_to_insert: list[dict[str, Any]] = []

        try:
            for idx, (content, ext, content_type) in enumerate(validated, start=1):
                storage_path = f"{nim}/{batch_id}_{idx}.{ext}"
                self.foto_wajah_repo.upload_face_image(
                    storage_path=storage_path,
                    content=content,
                    content_type=content_type,
                )
                uploaded_paths.append(storage_path)
                rows_to_insert.append(
                    {
                        "nim": nim,
                        "storage_path": storage_path,
                        "embedding": embeddings[idx - 1],
                        "is_active": True,
                    }
                )

            if deactivate_existing:
                self.foto_wajah_repo.deactivate_by_nim(nim)

            self.foto_wajah_repo.create_many(rows_to_insert)
        except Exception:
            self.foto_wajah_repo.delete_face_images(uploaded_paths)
            raise

        return FaceRegistrationResponse(
            message=message,
            nim=nim,
            samples_saved=len(rows_to_insert),
            embedding_dimension=len(avg_embedding),
            threshold=self.settings.face_similarity_threshold,
            storage_paths=uploaded_paths,
            is_registered=True,
        )

    def _validate_samples(
        self,
        samples: list[tuple[bytes, str, str]],
    ) -> list[tuple[bytes, str, str]]:
        if not samples:
            raise BadRequestError("Minimal unggah 1 foto wajah untuk diproses.")
        if len(samples) > self.settings.face_max_samples_per_request:
            raise BadRequestError(
                f"Maksimal {self.settings.face_max_samples_per_request} foto per permintaan."
            )

        normalized: list[tuple[bytes, str, str]] = []
        for idx, (content, filename, content_type) in enumerate(samples, start=1):
            if not content:
                raise BadRequestError(f"File foto ke-{idx} kosong.")
            if len(content) > MAX_IMAGE_BYTES:
                raise BadRequestError(f"Ukuran foto ke-{idx} melebihi batas 8 MB.")
            ext, mime = self.normalize_uploaded_metadata(filename, content_type, idx)
            normalized.append((content, ext, mime))
        return normalized

    def _extract_embeddings(
        self,
        validated_samples: list[tuple[bytes, str, str]],
    ) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for idx, (content, _, _) in enumerate(validated_samples, start=1):
            try:
                emb = self.engine.extract_embedding_from_bytes(content)
            except FaceDetectionError as exc:
                raise UnprocessableError(f"Foto ke-{idx}: {exc}") from exc
            embeddings.append(emb)
        return embeddings

    def _compare_probe(self, nim: str, image_bytes: bytes) -> tuple[FaceVerificationResult, int]:
        if not image_bytes:
            raise BadRequestError("File foto verifikasi wajah kosong.")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise BadRequestError("Ukuran foto verifikasi melebihi batas 8 MB.")

        self._ensure_student_exists(nim)
        active_rows = self.foto_wajah_repo.list_by_nim(nim, active_only=True)
        reference_embeddings = [
            row["embedding"]
            for row in active_rows
            if isinstance(row.get("embedding"), list) and len(row["embedding"]) > 0
        ]
        if not reference_embeddings:
            raise BadRequestError(
                "Data wajah belum diregistrasi. Silakan registrasi wajah terlebih dahulu."
            )

        try:
            result = self.engine.verify_from_bytes(
                image_bytes=image_bytes,
                reference_embeddings=reference_embeddings,
                threshold=self.settings.face_similarity_threshold,
            )
        except FaceDetectionError as exc:
            raise UnprocessableError(str(exc)) from exc

        return result, len(reference_embeddings)

    def _ensure_student_exists(self, nim: str) -> None:
        if not self.mahasiswa_repo.get_by_nim(nim):
            raise NotFoundError(f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.")

