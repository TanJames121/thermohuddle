"""ChickDetector (3-class YOLOv8n) detections; normalized display positions are NOT cm."""
import math
import hashlib
from collections import Counter
from pathlib import Path
import time


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

    def predict(self, frame):
        import numpy as np
        if (not isinstance(frame, np.ndarray) or frame.ndim != 3
                or frame.shape[2] != 3 or frame.dtype != np.uint8
                or min(frame.shape[:2]) < 1):
            raise ValueError('expected nonempty uint8 BGR frame')
        start = time.monotonic()
        result = self.model.predict(frame, conf=self.confidence,
                                    imgsz=self.image_size, device='cpu',
                                    augment=True,
                                    max_det=1000, verbose=False)[0]
        rows = result.boxes.data.cpu().tolist()
        height, width = frame.shape[:2]
        points = positions_from_boxes(rows, width, height)
        tally = Counter(int(r[5]) for r in rows)
        healthy, lame = tally.get(0, 0), tally.get(1, 0)
        return {'count': len(points), 'chicks': points, 'boxes': rows,
                'vision': {'model': 'ChickDetector-YOLOv8n',
                           'confidence_min': self.confidence,
                           'inference_ms': round((time.monotonic() - start) * 1000, 2),
                           'coordinate_system': 'uncalibrated_camera',
                           'calibrated': False,
                           'classes': {self.model.names[k]: v for k, v in tally.items()},
                           'lame_ratio': round(lame / (healthy + lame), 4)
                                         if healthy + lame else None}}


def positions_from_boxes(rows, width, height):
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
        positions.append([100 * cx / width - 50, 100 * cy / height - 50])
    return positions
