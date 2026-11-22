"""Image decoding and 5-point affine face alignment for MobileFaceNet (112x112)."""

import base64
import binascii

import cv2
import numpy as np

COORD_5_POINT_SQUARE = np.array(
    [
        [38.29459953, 51.69630051],
        [73.53179932, 51.50139999],
        [56.02519989, 71.73660278],
        [41.54930115, 92.36550140],
        [70.72990036, 92.20410156],
    ],
    dtype=np.float64,
)

COORD_5_POINT_RECT = np.array(
    [
        [30.29459953, 51.69630051],
        [65.53179932, 51.50139999],
        [48.02519989, 71.73660278],
        [33.54930115, 92.36550140],
        [62.72990036, 92.20410156],
    ],
    dtype=np.float64,
)


def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    """Decode raw image bytes (JPG/PNG/WEBP) into a BGR OpenCV ndarray."""
    if not image_bytes:
        raise ValueError("File gambar kosong.")
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        raise ValueError("Format gambar tidak valid atau file rusak.")
    return img


def decode_base64_image(data_or_url: str) -> np.ndarray:
    """Decode a base64 string or data URL into a BGR OpenCV ndarray."""
    encoded = data_or_url.split(",", 1)[1] if "," in data_or_url else data_or_url
    try:
        raw = base64.b64decode(encoded.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Payload base64 gambar tidak valid.") from exc
    return decode_image_bytes(raw)


def transformation_from_points(points1: np.ndarray, points2: np.ndarray) -> np.ndarray:
    """Compute a 3x3 similarity transform matrix aligning points1 onto points2."""
    p1 = np.asarray(points1, dtype=np.float64).copy()
    p2 = np.asarray(points2, dtype=np.float64).copy()

    c1 = np.mean(p1, axis=0)
    c2 = np.mean(p2, axis=0)
    p1 -= c1
    p2 -= c2

    s1 = float(np.std(p1))
    s2 = float(np.std(p2))
    if s1 <= 1e-12 or s2 <= 1e-12:
        raise ValueError("Landmark wajah tidak valid untuk alignment.")

    p1 /= s1
    p2 /= s2

    u, _, vt = np.linalg.svd(p1.T @ p2)
    rot = (u @ vt).T
    scale = s2 / s1
    translation = c2.reshape(2, 1) - scale * (rot @ c1.reshape(2, 1))
    top = np.hstack((scale * rot, translation))
    return np.vstack([top, np.array([[0.0, 0.0, 1.0]], dtype=np.float64)])


def align_face_crops(
    image_bgr: np.ndarray,
    landmarks: np.ndarray | None,
    default_square: bool = True,
) -> list[np.ndarray]:
    """Align and crop detected faces into 112x112 (or 112x96) BGR patches."""
    faces: list[np.ndarray] = []
    if landmarks is None or len(landmarks) == 0:
        return faces

    reference = COORD_5_POINT_SQUARE if default_square else COORD_5_POINT_RECT
    crop_w = 112 if default_square else 96

    for i in range(landmarks.shape[0]):
        pts1 = landmarks[i, :].reshape(2, 5).T
        matrix = transformation_from_points(pts1, reference)
        aligned = cv2.warpAffine(
            image_bgr,
            matrix[:2],
            (image_bgr.shape[1], image_bgr.shape[0]),
        )
        crop = aligned[0:112, 0:crop_w]
        if crop.shape[0] != 112 or crop.shape[1] != crop_w:
            crop = cv2.resize(crop, (crop_w, 112), interpolation=cv2.INTER_LINEAR)
        faces.append(crop)

    return faces


def select_primary_face_index(bboxes: np.ndarray) -> int:
    """Pick the most prominent face (largest bounding box area weighted by score)."""
    if len(bboxes) <= 1:
        return 0
    widths = np.maximum(1.0, bboxes[:, 2] - bboxes[:, 0])
    heights = np.maximum(1.0, bboxes[:, 3] - bboxes[:, 1])
    scores = np.maximum(0.01, bboxes[:, 4])
    weights = widths * heights * scores
    return int(np.argmax(weights))

