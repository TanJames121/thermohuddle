"""Unit fixtures are synthetic; the smoke test executes the downloaded weights."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))


class VisionTests(unittest.TestCase):
    def test_detection_boxes_become_normalized_positions_for_every_class(self):
        self.assertIsNotNone(importlib.util.find_spec('chicken_vision'),
                             'camera inference adapter is not implemented')
        from chicken_vision import positions_from_boxes
        # x1,y1,x2,y2,confidence,class; any class counts as a chick detection
        # (3-class ChickDetector: counting must not drop Healthy/Lame boxes).
        result = positions_from_boxes([[100, 100, 200, 200, .9, 0],
                                       [200, 200, 240, 240, .8, 1],
                                       [100, 100, 500, 400, .8, 2]], 640, 480)
        # third box spans 62% of frame height -> person-sized, size gate drops it
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0][0], -26.5625)
        self.assertAlmostEqual(result[0][1], -18.75)
        self.assertAlmostEqual(result[1][0], -15.625)
        self.assertAlmostEqual(result[1][1], -4.1667, places=4)

    def test_real_checkpoint_runs_on_blank_frame_without_inventing_chicks(self):
        import chicken_vision
        self.assertTrue(hasattr(chicken_vision, 'ChickenVision'),
                        'real YOLO inference is not implemented')
        import numpy as np
        detector = chicken_vision.ChickenVision(Path.home() / 'CameraModel/best.pt')
        result = detector.predict(np.zeros((480, 640, 3), dtype=np.uint8))
        self.assertEqual(result['count'], len(result['chicks']))
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['vision']['model'], 'ChickDetector-YOLOv8n')
        self.assertFalse(result['vision']['calibrated'])
        self.assertGreater(result['vision']['inference_ms'], 0)
        with self.assertRaises(ValueError):
            detector.predict(np.zeros((480, 640), dtype=np.uint8))


if __name__ == '__main__':
    unittest.main()
