"""MTCNN face detector with preloaded model weights and safe empty-face handling."""

import math
from pathlib import Path

import cv2
import numpy as np
import torch

from ml.detection.nets import ONet, PNet, RNet
from ml.detection.utils import (
    calibrate_box,
    convert_to_square,
    correct_bboxes,
    nms,
    preprocess_mtcnn_image,
)


class MTCNNDetector:
    """Cached three-stage MTCNN detector (P-Net -> R-Net -> O-Net)."""

    def __init__(
        self,
        weights_dir: str | Path,
        device: torch.device | None = None,
        min_face_size: int = 20,
    ) -> None:
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.min_face_size = min_face_size
        weights_path = Path(weights_dir)

        self.pnet = PNet().to(self.device)
        self.pnet.load_state_dict(
            torch.load(weights_path / "pnet_Weights", map_location=self.device, weights_only=True)
        )
        self.pnet.eval()

        self.rnet = RNet().to(self.device)
        self.rnet.load_state_dict(
            torch.load(weights_path / "rnet_Weights", map_location=self.device, weights_only=True)
        )
        self.rnet.eval()

        self.onet = ONet().to(self.device)
        self.onet.load_state_dict(
            torch.load(weights_path / "onet_Weights", map_location=self.device, weights_only=True)
        )
        self.onet.eval()

    def detect(self, image_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Detect face bounding boxes and 5-point facial landmarks from a BGR image."""
        if image_bgr is None or image_bgr.ndim != 3 or image_bgr.size == 0:
            return np.empty((0, 5), dtype=np.float32), np.empty((0, 10), dtype=np.float32)

        bboxes = self._detect_pnet(image_bgr)
        if len(bboxes) == 0:
            return np.empty((0, 5), dtype=np.float32), np.empty((0, 10), dtype=np.float32)

        bboxes = self._detect_rnet(image_bgr, bboxes)
        if len(bboxes) == 0:
            return np.empty((0, 5), dtype=np.float32), np.empty((0, 10), dtype=np.float32)

        return self._detect_onet(image_bgr, bboxes)

    def _detect_pnet(self, image: np.ndarray) -> np.ndarray:
        threshold = 0.7
        nms_threshold = 0.7
        height, width, _ = image.shape
        min_length = min(height, width)

        min_detection_size = 12
        factor = 0.707
        m = min_detection_size / float(self.min_face_size)
        min_length *= m

        scales: list[float] = []
        factor_count = 0
        while min_length > min_detection_size:
            scales.append(m * (factor ** factor_count))
            min_length *= factor
            factor_count += 1

        if not scales:
            return np.empty((0, 5), dtype=np.float32)

        candidate_boxes: list[np.ndarray] = []
        with torch.no_grad():
            for scale in scales:
                sw = max(1, math.ceil(width * scale))
                sh = max(1, math.ceil(height * scale))
                if sw < min_detection_size or sh < min_detection_size:
                    continue

                resized = cv2.resize(image, (sw, sh), interpolation=cv2.INTER_LINEAR)
                tensor = torch.from_numpy(preprocess_mtcnn_image(resized)).to(self.device)
                offset, prob = self.pnet(tensor)

                probs = prob.cpu().numpy()[0, 1, :, :]
                offsets = offset.cpu().numpy()
                inds = np.where(probs > threshold)
                if inds[0].size == 0:
                    continue

                stride, cell_size = 2, 12
                tx1, ty1, tx2, ty2 = (offsets[0, i, inds[0], inds[1]] for i in range(4))
                score = probs[inds[0], inds[1]]
                box_arr = np.vstack([
                    np.round((stride * inds[1] + 1.0) / scale),
                    np.round((stride * inds[0] + 1.0) / scale),
                    np.round((stride * inds[1] + 1.0 + cell_size) / scale),
                    np.round((stride * inds[0] + 1.0 + cell_size) / scale),
                    score,
                    np.array([tx1, ty1, tx2, ty2]),
                ]).T
                keep = nms(box_arr[:, 0:5], overlap_threshold=0.5)
                if keep:
                    candidate_boxes.append(box_arr[keep])

        if not candidate_boxes:
            return np.empty((0, 5), dtype=np.float32)

        stacked = np.vstack(candidate_boxes)
        keep = nms(stacked[:, 0:5], nms_threshold)
        if not keep:
            return np.empty((0, 5), dtype=np.float32)

        stacked = stacked[keep]
        bboxes = calibrate_box(stacked[:, 0:5], stacked[:, 5:])
        bboxes = convert_to_square(bboxes)
        bboxes[:, 0:4] = np.round(bboxes[:, 0:4])
        return bboxes

    def _crop_stage_inputs(
        self, image: np.ndarray, bboxes: np.ndarray, size: int
    ) -> np.ndarray:
        height, width, _ = image.shape
        num_boxes = len(bboxes)
        dy, edy, dx, edx, y, ey, x, ex, w, h = correct_bboxes(bboxes, width, height)
        crops = np.zeros((num_boxes, 3, size, size), dtype=np.float32)

        for i in range(num_boxes):
            if h[i] <= 0 or w[i] <= 0:
                continue
            img_box = np.zeros((h[i], w[i], 3), dtype=image.dtype)
            if edy[i] >= dy[i] and edx[i] >= dx[i] and ey[i] >= y[i] and ex[i] >= x[i]:
                img_box[dy[i] : edy[i] + 1, dx[i] : edx[i] + 1, :] = image[
                    y[i] : ey[i] + 1, x[i] : ex[i] + 1, :
                ]
            resized = cv2.resize(img_box, (size, size), interpolation=cv2.INTER_LINEAR)
            crops[i] = preprocess_mtcnn_image(resized)[0]

        return crops

    def _detect_rnet(self, image: np.ndarray, bboxes: np.ndarray) -> np.ndarray:
        threshold = 0.8
        nms_threshold = 0.7
        crops = self._crop_stage_inputs(image, bboxes, size=24)

        with torch.no_grad():
            tensor = torch.from_numpy(crops).to(self.device)
            offset, prob = self.rnet(tensor)

        offsets = offset.cpu().numpy()
        probs = prob.cpu().numpy()
        keep = np.where(probs[:, 1] > threshold)[0]
        if keep.size == 0:
            return np.empty((0, 5), dtype=np.float32)

        bboxes = bboxes[keep].copy()
        bboxes[:, 4] = probs[keep, 1]
        offsets = offsets[keep]

        nms_keep = nms(bboxes, nms_threshold)
        if not nms_keep:
            return np.empty((0, 5), dtype=np.float32)

        bboxes = calibrate_box(bboxes[nms_keep], offsets[nms_keep])
        bboxes = convert_to_square(bboxes)
        bboxes[:, 0:4] = np.round(bboxes[:, 0:4])
        return bboxes

    def _detect_onet(
        self, image: np.ndarray, bboxes: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        threshold = 0.98
        nms_threshold = 0.7
        crops = self._crop_stage_inputs(image, bboxes, size=48)

        with torch.no_grad():
            tensor = torch.from_numpy(crops).to(self.device)
            landmark, offset, prob = self.onet(tensor)

        landmarks = landmark.cpu().numpy()
        offsets = offset.cpu().numpy()
        probs = prob.cpu().numpy()

        keep = np.where(probs[:, 1] > threshold)[0]
        if keep.size == 0:
            return np.empty((0, 5), dtype=np.float32), np.empty((0, 10), dtype=np.float32)

        bboxes = bboxes[keep].copy()
        bboxes[:, 4] = probs[keep, 1]
        offsets = offsets[keep]
        landmarks = landmarks[keep].copy()

        width = bboxes[:, 2] - bboxes[:, 0] + 1.0
        height = bboxes[:, 3] - bboxes[:, 1] + 1.0
        xmin, ymin = bboxes[:, 0], bboxes[:, 1]
        landmarks[:, 0:5] = np.expand_dims(xmin, 1) + np.expand_dims(width, 1) * landmarks[:, 0:5]
        landmarks[:, 5:10] = np.expand_dims(ymin, 1) + np.expand_dims(height, 1) * landmarks[:, 5:10]

        bboxes = calibrate_box(bboxes, offsets)
        nms_keep = nms(bboxes, nms_threshold, mode="min")
        if not nms_keep:
            return np.empty((0, 5), dtype=np.float32), np.empty((0, 10), dtype=np.float32)

        return bboxes[nms_keep], landmarks[nms_keep]

