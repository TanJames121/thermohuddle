"""PoultryVision chicken detections; normalized display positions are NOT cm."""
import math
import hashlib
from pathlib import Path
import time


class ChickenVision:
    """Load only the audited, revision-pinned checkpoint, never arbitrary pickle."""
    SHA256 = 'f68d3a009631b2d42f3d7cccd0dc315568b75a2c33b05a9443f599350ade329d'

    def __init__(self, checkpoint, confidence=.35, image_size=640):
        import torch
        from ultralytics import YOLO
        checkpoint = Path(checkpoint)
        if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != self.SHA256:
            raise ValueError('camera checkpoint hash differs from verified Hub revision')
        if not 0 < confidence <= 1 or image_size < 32:
            raise ValueError('invalid inference configuration')
        torch.set_num_threads(2)
        self.model = YOLO(str(checkpoint), task='detect')
        if self.model.names != {0: 'chicken', 1: 'egg'}:
            raise ValueError('unexpected camera class mapping')
        self.confidence, self.image_size = confidence, image_size

    def predict(self, frame):
        import numpy as np
        if (not isinstance(frame, np.ndarray) or frame.ndim != 3
                or frame.shape[2] != 3 or frame.dtype != np.uint8
                or min(frame.shape[:2]) < 1):
            raise ValueError('expected nonempty uint8 BGR frame')
        start = time.monotonic()
        result = self.model.predict(frame, conf=self.confidence, classes=[0],
                                    imgsz=self.image_size, device='cpu',
                                    max_det=1000, verbose=False)[0]
        rows = result.boxes.data.cpu().tolist()
        height, width = frame.shape[:2]
        points = positions_from_boxes(rows, width, height)
        return {'count': len(points), 'chicks': points, 'boxes': rows,
                'vision': {'model': 'PoultryVision-YOLOv11m',
                           'confidence_min': self.confidence,
                           'inference_ms': round((time.monotonic() - start) * 1000, 2),
                           'coordinate_system': 'uncalibrated_camera',
                           'calibrated': False}}


def positions_from_boxes(rows, width, height):
    if width <= 0 or height <= 0:
        raise ValueError('invalid frame dimensions')
    positions = []
    for x1, y1, x2, y2, confidence, cls in rows:
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2, confidence, cls)):
            raise ValueError('non-finite detection')
        if int(cls) != 0 or x2 <= x1 or y2 <= y1:
            continue
        cx = min(width, max(0, (x1 + x2) / 2))
        cy = min(height, max(0, (y1 + y2) / 2))
        positions.append([100 * cx / width - 50, 100 * cy / height - 50])
    return positions
