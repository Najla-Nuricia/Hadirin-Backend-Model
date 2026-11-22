"""Unit tests for average vs multiple embedding scoring (no model weights required)."""

import pytest

from ml.inference.face_embedder import FaceRecognitionEngine, FaceVerificationResult


def test_multiple_uses_best_single_reference() -> None:
    probe = [1.0, 0.0]
    references = [[0.9, 0.1], [-1.0, 0.0]]

    average = FaceRecognitionEngine.compare_embeddings(probe, references, "average")
    multiple = FaceRecognitionEngine.compare_embeddings(probe, references, "multiple")

    assert average < multiple
    assert multiple == pytest.approx(0.9939, abs=1e-3)


def test_average_uses_centroid() -> None:
    probe = [1.0, 0.0]
    references = [[1.0, 0.0], [-1.0, 0.0]]  # centroid is zero vector

    assert FaceRecognitionEngine.compare_embeddings(probe, references, "average") == pytest.approx(0.0)
    assert FaceRecognitionEngine.compare_embeddings(probe, references, "multiple") == pytest.approx(1.0)


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        FaceRecognitionEngine.compare_embeddings([1.0, 0.0], [], "average")
    with pytest.raises(ValueError):
        FaceRecognitionEngine.compare_embeddings([1.0, 0.0], [[1.0, 0.0]], "top5")


def test_verification_result_records_strategy() -> None:
    result = FaceVerificationResult(
        matched=True,
        status="match",
        label="WAJAH COCOK",
        similarity=0.9,
        threshold=0.5,
        strategy="multiple",
    )
    assert result.strategy == "multiple"
