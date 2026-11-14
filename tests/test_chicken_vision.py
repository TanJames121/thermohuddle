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

    def test_aruco_homography_maps_corners_and_caches_on_occlusion(self):
        import cv2
        import numpy as np
        import chicken_vision

        frame = np.full((480, 640, 3), 255, dtype=np.uint8)
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        centers = {0: (90, 70), 1: (550, 70), 2: (90, 410), 3: (550, 410)}
        marker_size = 64
        for marker_id, (cx, cy) in centers.items():
            tag = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_size)
            tag_bgr = cv2.cvtColor(tag, cv2.COLOR_GRAY2BGR)
            x0, y0 = cx - marker_size // 2, cy - marker_size // 2
            frame[y0:y0 + marker_size, x0:x0 + marker_size] = tag_bgr

        mapper = chicken_vision.ArucoBoxMapper()
        state = mapper.update(frame)
        self.assertTrue(state['mapped'])
        self.assertEqual(state['detected_ids'], [0, 1, 2, 3])
        self.assertEqual(len(state['corners_norm']), 4)

        cx_world, cz_world = chicken_vision.map_point_homography(320.0, 240.0, state['homography'])
        self.assertAlmostEqual(cx_world, 0.0, delta=2.0)
        self.assertAlmostEqual(cz_world, 0.0, delta=2.0)

        mapped_pts = chicken_vision.positions_from_boxes(
            [
                (295.0, 215.0, 345.0, 265.0, 0.9, 0),
                (75.0, 230.0, 89.0, 250.0, 0.9, 0),
                (5.0, 5.0, 15.0, 15.0, 0.9, 0),
            ],
            width=640, height=480, homography=state['homography'], clip_to_box=True,
        )
        self.assertEqual(len(mapped_pts), 2)
        self.assertAlmostEqual(mapped_pts[0][0], 0.0, delta=2.0)
        self.assertAlmostEqual(mapped_pts[0][1], 0.0, delta=2.0)
        self.assertEqual(mapped_pts[1][0], -50.0)

        occluded = mapper.update(np.full((480, 640, 3), 255, dtype=np.uint8))
        self.assertTrue(occluded['mapped'])
        self.assertEqual(occluded['detected_ids'], [])


if __name__ == '__main__':
    unittest.main()
