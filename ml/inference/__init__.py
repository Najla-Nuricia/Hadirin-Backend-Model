"""Face recognition inference engine."""

from ml.inference.face_embedder import (
    FaceDetectionError,
    FaceRecognitionEngine,
    FaceVerificationResult,
    get_face_engine,
)

__all__ = [
    "FaceDetectionError",
    "FaceRecognitionEngine",
    "FaceVerificationResult",
    "get_face_engine",
]

