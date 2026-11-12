"""Bounding box math, NMS, and tensor preprocessing helpers for MTCNN."""

import numpy as np


def preprocess_mtcnn_image(img: np.ndarray) -> np.ndarray:
    """Convert BGR HxWxC image to normalized RGB NCHW float32 array for MTCNN."""
    rgb = img[:, :, ::-1]
    arr = np.asarray(rgb, dtype=np.float32)
    arr = arr.transpose((2, 0, 1))
    arr = np.expand_dims(arr, 0)
    return (arr - 127.5) * 0.0078125


def nms(boxes: np.ndarray, overlap_threshold: float = 0.5, mode: str = "union") -> list[int]:
    """Non-maximum suppression over [x1, y1, x2, y2, score] boxes."""
    if len(boxes) == 0:
        return []

    pick: list[int] = []
    x1, y1, x2, y2, score = (boxes[:, i] for i in range(5))
    area = (x2 - x1 + 1.0) * (y2 - y1 + 1.0)
    ids = np.argsort(score)

    while len(ids) > 0:
        last = len(ids) - 1
        idx = int(ids[last])
        pick.append(idx)

        ix1 = np.maximum(x1[idx], x1[ids[:last]])
        iy1 = np.maximum(y1[idx], y1[ids[:last]])
        ix2 = np.minimum(x2[idx], x2[ids[:last]])
        iy2 = np.minimum(y2[idx], y2[ids[:last]])

        w = np.maximum(0.0, ix2 - ix1 + 1.0)
        h = np.maximum(0.0, iy2 - iy1 + 1.0)
        inter = w * h

        if mode == "min":
            overlap = inter / np.minimum(area[idx], area[ids[:last]])
        else:
            overlap = inter / (area[idx] + area[ids[:last]] - inter)

        suppressed = np.where(overlap > overlap_threshold)[0]
        ids = np.delete(ids, np.concatenate(([last], suppressed)))

    return pick


def calibrate_box(bboxes: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    """Apply bounding box regression offsets."""
    calibrated = bboxes.copy()
    x1, y1, x2, y2 = (calibrated[:, i] for i in range(4))
    w = np.expand_dims(x2 - x1 + 1.0, 1)
    h = np.expand_dims(y2 - y1 + 1.0, 1)
    calibrated[:, 0:4] = calibrated[:, 0:4] + np.hstack([w, h, w, h]) * offsets
    return calibrated


def convert_to_square(bboxes: np.ndarray) -> np.ndarray:
    """Expand bounding boxes to square shape centered at each box."""
    square = np.zeros_like(bboxes)
    x1, y1, x2, y2 = (bboxes[:, i] for i in range(4))
    h = y2 - y1 + 1.0
    w = x2 - x1 + 1.0
    max_side = np.maximum(h, w)
    square[:, 0] = x1 + w * 0.5 - max_side * 0.5
    square[:, 1] = y1 + h * 0.5 - max_side * 0.5
    square[:, 2] = square[:, 0] + max_side - 1.0
    square[:, 3] = square[:, 1] + max_side - 1.0
    square[:, 4] = bboxes[:, 4]
    return square


def correct_bboxes(bboxes: np.ndarray, width: int, height: int) -> list[np.ndarray]:
    """Clip bounding boxes to image boundaries and return cutout coordinates."""
    x1, y1, x2, y2 = (bboxes[:, i].copy() for i in range(4))
    x2 = np.clip(x2, x1, None)
    y2 = np.clip(y2, y1, None)
    w = x2 - x1 + 1.0
    h = y2 - y1 + 1.0
    num_boxes = bboxes.shape[0]

    x, y, ex, ey = x1, y1, x2, y2
    dx = np.zeros((num_boxes,))
    dy = np.zeros((num_boxes,))
    edx = w.copy() - 1.0
    edy = h.copy() - 1.0

    ind = np.where(ex > width - 1.0)[0]
    edx[ind] = w[ind] + width - 2.0 - ex[ind]
    ex[ind] = width - 1.0

    ind = np.where(ey > height - 1.0)[0]
    edy[ind] = h[ind] + height - 2.0 - ey[ind]
    ey[ind] = height - 1.0

    ind = np.where(x < 0.0)[0]
    dx[ind] = 0.0 - x[ind]
    x[ind] = 0.0

    ind = np.where(y < 0.0)[0]
    dy[ind] = 0.0 - y[ind]
    y[ind] = 0.0

    return [arr.astype("int32") for arr in (dy, edy, dx, edx, y, ey, x, ex, w, h)]

