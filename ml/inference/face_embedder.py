"""End-to-end MTCNN + Face Alignment + MobileFaceNet inference service."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms

from ml.detection.mtcnn import MTCNNDetector
from ml.models.mobilefacenet import MobileFaceNet
from ml.preprocessing.alignment import (
    align_face_crops,
    decode_base64_image,
    decode_image_bytes,
    select_primary_face_index,
)

DEFAULT_WEIGHTS_DIR = Path(__file__).resolve().parent.parent / "models" / "weights"


class FaceDetectionError(ValueError):
    """Raised when no valid face can be detected or aligned in an input image."""


@dataclass(frozen=True)
class FaceVerificationResult:
    """Result of comparing a probe face against registered reference embeddings."""

    matched: bool
    status: str
    label: str
    similarity: float
    threshold: float


class FaceRecognitionEngine:
    """Thread-safe inference engine matching the Colab MobileFaceNet + MTCNN pipeline."""

    def __init__(
        self,
        weights_dir: str | Path = DEFAULT_WEIGHTS_DIR,
        min_face_size: int = 20,
        embedding_size: int = 512,
    ) -> None:
        self.weights_dir = Path(weights_dir)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.embedding_size = embedding_size

        self.detector = MTCNNDetector(
            weights_dir=self.weights_dir,
            device=self.device,
            min_face_size=min_face_size,
        )

        self.model = MobileFaceNet(embedding_size).to(self.device)
        mobile_weights = self.weights_dir / "MobileFace_Net"
        self.model.load_state_dict(
            torch.load(mobile_weights, map_location=self.device, weights_only=True)
        )
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
        ])

    def extract_embedding_from_bgr(self, image_bgr: np.ndarray) -> list[float]:
        """Detect primary face, align to 112x112, and return L2-normalized 512-D embedding."""
        bboxes, landmarks = self.detector.detect(image_bgr)
        if landmarks is None or len(landmarks) == 0:
            raise FaceDetectionError("Wajah tidak terdeteksi pada gambar.")

        faces = align_face_crops(image_bgr, landmarks, default_square=True)
        if not faces:
            raise FaceDetectionError("Gagal melakukan alignment wajah.")

        idx = select_primary_face_index(bboxes)
        face_crop = np.ascontiguousarray(faces[idx])

        tensor = self.transform(face_crop).unsqueeze(0).to(self.device)
        with torch.no_grad():
            embedding = self.model(tensor)
            embedding = F.normalize(embedding, p=2, dim=1)

        return embedding.squeeze(0).cpu().tolist()

    def extract_embedding_from_bytes(self, image_bytes: bytes) -> list[float]:
        """Decode image bytes and extract its L2-normalized 512-D face embedding."""
        try:
            image_bgr = decode_image_bytes(image_bytes)
        except ValueError as exc:
            raise FaceDetectionError(str(exc)) from exc
        return self.extract_embedding_from_bgr(image_bgr)

    def extract_embedding_from_base64(self, image_b64: str) -> list[float]:
        """Decode base64/data-URL image and extract its L2-normalized 512-D face embedding."""
        try:
            image_bgr = decode_base64_image(image_b64)
        except ValueError as exc:
            raise FaceDetectionError(str(exc)) from exc
        return self.extract_embedding_from_bgr(image_bgr)

    @staticmethod
    def compute_average_embedding(embeddings: Sequence[Sequence[float]]) -> list[float]:
        """Compute L2-normalized centroid embedding across multiple face captures."""
        if not embeddings:
            raise ValueError("Daftar embedding tidak boleh kosong.")
        tensor = torch.tensor(embeddings, dtype=torch.float32)
        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(0)
        mean_emb = tensor.mean(dim=0, keepdim=True)
        normalized = F.normalize(mean_emb, p=2, dim=1)
        return normalized.squeeze(0).tolist()

    @staticmethod
    def cosine_similarity(
        embedding_a: Sequence[float], embedding_b: Sequence[float]
    ) -> float:
        """Compute cosine similarity between two embeddings in [-1.0, 1.0]."""
        t_a = torch.tensor(embedding_a, dtype=torch.float32).unsqueeze(0)
        t_b = torch.tensor(embedding_b, dtype=torch.float32).unsqueeze(0)
        return float(F.cosine_similarity(t_a, t_b).item())

    def verify_from_bytes(
        self,
        image_bytes: bytes,
        reference_embeddings: Sequence[Sequence[float]],
        threshold: float = 0.5,
    ) -> FaceVerificationResult:
        """Extract embedding from probe image and compare against student's centroid."""
        probe_embedding = self.extract_embedding_from_bytes(image_bytes)
        centroid = self.compute_average_embedding(reference_embeddings)
        similarity = self.cosine_similarity(centroid, probe_embedding)
        matched = similarity >= threshold
        return FaceVerificationResult(
            matched=matched,
            status="match" if matched else "unknown",
            label="WAJAH COCOK" if matched else "WAJAH TIDAK COCOK",
            similarity=round(similarity, 4),
            threshold=threshold,
        )


@lru_cache(maxsize=2)
def get_face_engine(
    weights_dir: str = str(DEFAULT_WEIGHTS_DIR),
    min_face_size: int = 20,
) -> FaceRecognitionEngine:
    """Return a cached FaceRecognitionEngine singleton so model weights load only once."""
    return FaceRecognitionEngine(weights_dir=weights_dir, min_face_size=min_face_size)

