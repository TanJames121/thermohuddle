"""ChickDetector (3-class YOLOv8n) detections with optional ArUco box mapping."""
import math
import hashlib
from collections import Counter
from pathlib import Path
import time

CORNER_MAP = {
    0: (-50.0, -50.0),  # Top-Left
    1: (50.0, -50.0),   # Top-Right
    2: (-50.0, 50.0),   # Bottom-Left
    3: (50.0, 50.0),    # Bottom-Right
}
BOX_PERIMETER_IDS = (0, 1, 3, 2)


def detect_aruco_markers(frame):
    """Detect DICT_4X4_50 ArUco markers {0,1,2,3} and return {id: (cx, cy)} pixel centers."""
    import cv2
    import numpy as np

    if frame is None or not isinstance(frame, np.ndarray) or frame.ndim < 2:
        return {}
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(dictionary, parameters)

    centers = {}
    for candidate in (gray, cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)):
        corners, ids, _ = detector.detectMarkers(candidate)
        if ids is not None:
            for marker_corners, marker_id in zip(corners, ids.flatten()):
                mid = int(marker_id)
                if mid in CORNER_MAP and mid not in centers:
                    pts = marker_corners.reshape(-1, 2)
                    centers[mid] = (float(pts[:, 0].mean()), float(pts[:, 1].mean()))
        if len(centers) == 4:
            break
    return centers


def map_point_homography(cx, cy, homography):
    """Transform a pixel point (cx, cy) through a 3x3 homography matrix."""
    import cv2
    import numpy as np

    pt = np.array([[[float(cx), float(cy)]]], dtype=np.float32)
    mapped = cv2.perspectiveTransform(pt, np.asarray(homography, dtype=np.float32))
    bx, bz = float(mapped[0, 0, 0]), float(mapped[0, 0, 1])
    return bx, bz


class ArucoBoxMapper:
    """Maps NoIR camera pixel coordinates into the ArUco-bounded brooder box [-50, 50]^2."""

    def __init__(self):
        self.homography = None
        self.corner_pixels = {}
        self.frame_shape = None

    def update(self, frame):
        """Detect ArUco corner markers and update or reuse cached perspective transform."""
        import cv2
        import numpy as np

        height, width = frame.shape[:2]
        if self.frame_shape != (height, width):
            self.homography = None
            self.corner_pixels = {}
            self.frame_shape = (height, width)

        detected = detect_aruco_markers(frame)
        detected_ids = sorted(detected.keys())

        if len(detected) == 4:
            src_pts = np.array([detected[i] for i in (0, 1, 2, 3)], dtype=np.float32)
            dst_pts = np.array([CORNER_MAP[i] for i in (0, 1, 2, 3)], dtype=np.float32)
            H = cv2.getPerspectiveTransform(src_pts, dst_pts)
            if H is not None and np.isfinite(H).all() and abs(float(np.linalg.det(H))) > 1e-6:
                self.homography = H
                self.corner_pixels = {
                    mid: [round(px, 1), round(py, 1)] for mid, (px, py) in detected.items()
                }

        mapped = self.homography is not None and len(self.corner_pixels) == 4
        if mapped:
            corners_px = [self.corner_pixels[mid] for mid in BOX_PERIMETER_IDS]
            corners_norm = [
                [round(max(0.0, min(1.0, px / width)), 4),
                 round(max(0.0, min(1.0, py / height)), 4)]
                for px, py in corners_px
            ]
        else:
            corners_px = []
            corners_norm = []

        return {
            'mapped': mapped,
            'homography': self.homography,
            'detected_ids': detected_ids,
            'corners_px': corners_px,
            'corners_norm': corners_norm,
            'detected_pixels': {mid: [round(px, 1), round(py, 1)] for mid, (px, py) in detected.items()},
        }


class ChickenVision:
    """Load only the audited, revision-pinned checkpoint, never arbitrary pickle."""
    SHA256 = '3b11fc21f667e582e1d2c28ea209473a43508a6f34c9ae15ee6b585cd5a11581'
    # Chicks are small relative to the visible floor; a box covering ~1/3 of the
    # frame height is a person/foreground object the 3-class model was never
    # trained to reject (no negative images). Size, unlike appearance, cannot lie.
    MAX_BOX_HEIGHT_FRAC = 0.30

    def __init__(self, checkpoint, confidence=.30, image_size=640):
        import torch
        from ultralytics import YOLO
        checkpoint = Path(checkpoint)
        if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != self.SHA256:
            raise ValueError('camera checkpoint hash differs from verified Hub revision')
        if not 0 < confidence <= 1 or image_size < 32:
            raise ValueError('invalid inference configuration')
        torch.set_num_threads(2)
        self.model = YOLO(str(checkpoint), task='detect')
        if self.model.names != {0: 'Healthy_chick', 1: 'Lame_chick', 2: 'chick'}:
            raise ValueError('unexpected camera class mapping')
        self.confidence, self.image_size = confidence, image_size
        self.aruco_mapper = ArucoBoxMapper()

    def predict(self, frame):
        import numpy as np
        if (not isinstance(frame, np.ndarray) or frame.ndim != 3
                or frame.shape[2] != 3 or frame.dtype != np.uint8
                or min(frame.shape[:2]) < 1):
            raise ValueError('expected nonempty uint8 BGR frame')
        start = time.monotonic()
        aruco_info = self.aruco_mapper.update(frame)
        result = self.model.predict(frame, conf=self.confidence,
                                    imgsz=self.image_size, device='cpu',
                                    augment=True,
                                    max_det=1000, verbose=False)[0]
        rows = result.boxes.data.cpu().tolist()
        height, width = frame.shape[:2]
        points = positions_from_boxes(rows, width, height, homography=aruco_info['homography'])
        tally = Counter(int(r[5]) for r in rows)
        healthy, lame = tally.get(0, 0), tally.get(1, 0)
        return {'count': len(points), 'chicks': points, 'boxes': rows,
                'aruco_pixels': aruco_info['corners_px'],
                'aruco_detected_pixels': aruco_info['detected_pixels'],
                'vision': {'model': 'ChickDetector-YOLOv8n',
                           'confidence_min': self.confidence,
                           'inference_ms': round((time.monotonic() - start) * 1000, 2),
                           'coordinate_system': 'uncalibrated_camera',
                           'calibrated': False,
                           'aruco_mapped': bool(aruco_info['mapped']),
                           'aruco_markers': aruco_info['detected_ids'],
                           'aruco_corners': aruco_info['corners_norm'],
                           'classes': {self.model.names[k]: v for k, v in tally.items()},
                           'lame_ratio': round(lame / (healthy + lame), 4)
                                         if healthy + lame else None}}


def positions_from_boxes(rows, width, height, homography=None, clip_to_box=True):
    if width <= 0 or height <= 0:
        raise ValueError('invalid frame dimensions')
    cls_limit = ChickenVision.MAX_BOX_HEIGHT_FRAC * height
    positions = []
    for x1, y1, x2, y2, confidence, cls in rows:
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2, confidence, cls)):
            raise ValueError('non-finite detection')
        if x2 <= x1 or y2 <= y1 or (y2 - y1) > cls_limit:
            continue
        cx = min(width, max(0, (x1 + x2) / 2))
        cy = min(height, max(0, (y1 + y2) / 2))
        if homography is not None:
            bx, bz = map_point_homography(cx, cy, homography)
            if not (math.isfinite(bx) and math.isfinite(bz)):
                continue
            if clip_to_box:
                if abs(bx) > 55.0 or abs(bz) > 55.0:
                    continue
                bx = max(-50.0, min(50.0, bx))
                bz = max(-50.0, min(50.0, bz))
            positions.append([round(bx, 3), round(bz, 3)])
        else:
            positions.append([100 * cx / width - 50, 100 * cy / height - 50])
    return positions
