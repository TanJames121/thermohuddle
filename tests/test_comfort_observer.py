"""Synthetic pattern fixtures verify logic, not biological classification accuracy."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))


class ObserverTests(unittest.TestCase):
    def test_zero_or_one_detection_cannot_mean_comfortable_or_crowded(self):
        self.assertIsNotNone(importlib.util.find_spec('comfort_observer'),
                             'safe observation fusion is not implemented')
        from comfort_observer import ComfortObserver
        observer = ComfortObserver(window_s=60)
        for now, points in [(0, []), (60, [[0, 0]]), (120, [])]:
            assessment = observer.update(points, None, now=now)
            self.assertEqual(assessment['state'], 'UNKNOWN')
            self.assertEqual(assessment['candidate'], 'UNKNOWN')
            self.assertFalse(assessment['control_allowed'])

    def test_persistent_clustering_is_a_candidate_not_thermal_proof(self):
        from comfort_observer import ComfortObserver
        observer = ComfortObserver(window_s=60)
        points = [[float(i) / 10, float(i) / 10] for i in range(10)]
        for now in range(0, 181, 5):
            assessment = observer.update(points, {'label': 'Healthy', 'available': True,
                                                  'ts': now}, now=now)
        self.assertEqual(assessment['candidate'], 'CROWDING')
        self.assertEqual(assessment['pattern'], 'CLUSTERED')
        self.assertEqual(assessment['state'], 'UNKNOWN')
        self.assertFalse(assessment['control_allowed'])
        self.assertEqual(assessment['audio_support'], 'healthy_vocalization')
        self.assertGreaterEqual(assessment['samples'], 3)

    def test_windowed_patterns_are_only_unvalidated_candidates(self):
        from comfort_observer import ComfortObserver
        even = [[x, y] for x in [-37.5, -12.5, 12.5, 37.5]
                for y in [-37.5, -12.5, 12.5, 37.5]]
        ring = [[45, 0], [-45, 0], [0, 45], [0, -45],
                [32, 32], [-32, 32], [32, -32], [-32, -32]]
        asymmetric = [[30 + i / 2, -30 + j * 15] for i in range(3) for j in range(5)]
        tight = [[x, y] for x in [-1, 1] for y in [-1, 1]]
        for points, pattern, candidate in [(even, 'EVEN', 'COMFY_CANDIDATE'),
                                           (ring, 'DISPERSED', 'POSSIBLE_HOT'),
                                           (asymmetric, 'ASYMMETRIC', 'POSSIBLE_DRAFT'),
                                           (tight, 'CLUSTERED', 'POSSIBLE_COLD')]:
            with self.subTest(candidate=candidate):
                observer = ComfortObserver()
                result = None
                for now in range(0, 301, 5):
                    result = observer.update(points, None, now=now)
                self.assertEqual(result['pattern'], pattern)
                self.assertEqual(result['candidate'], candidate)
                self.assertEqual(result['state'], 'UNKNOWN')
                self.assertFalse(result['control_allowed'])
                self.assertEqual(observer.update([], None, now=305)['candidate'], 'UNKNOWN')

    def test_stale_audio_missing_frames_and_camera_gap_reset_evidence(self):
        from comfort_observer import ComfortObserver
        observer = ComfortObserver()
        points = [[float(i) / 10, float(i) / 10] for i in range(10)]
        for now in range(0, 181, 5):
            observer.update(points, None, now=now)
        result = observer.update(points, {'label': 'Unhealthy', 'available': True, 'ts': 0}, now=185)
        self.assertEqual(result['audio_support'], 'unavailable')
        result = observer.update(points, None, now=500)
        self.assertEqual(result['candidate'], 'UNKNOWN')
        for invalid in [[[float('nan'), 0]] * 3, [[0, 0, 0]] * 3, [[100, 0]] * 3]:
            result = observer.update(invalid, None, now=505)
            self.assertEqual(result['state'], 'UNKNOWN')
            self.assertEqual(result['candidate'], 'UNKNOWN')
            self.assertEqual(result['pattern'], 'INSUFFICIENT')


if __name__ == '__main__':
    unittest.main()
