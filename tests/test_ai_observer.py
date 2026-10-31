"""Packet tests use synthetic detections, never substitute them for hardware output."""
import importlib.util
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))


class PipelineTests(unittest.TestCase):
    def test_packet_preserves_model_evidence_without_stub_thermal_or_actuators(self):
        self.assertIsNotNone(importlib.util.find_spec('ai_observer'),
                             'model pipeline connection is not implemented')
        from ai_observer import assemble_packet
        vision = {'count': 0, 'chicks': [], 'vision': {'model': 'PoultryVision-YOLOv11m'}}
        assessment = {'state': 'UNKNOWN', 'control_allowed': False}
        packet = assemble_packet(vision, None, assessment, now=1000, seq=1,
                                 boot_id='123456abcdef', cam_ok=True)
        self.assertEqual(packet['count'], len(packet['chicks']))
        self.assertEqual(packet['ts'], 1000)
        self.assertEqual(packet['assessment'], assessment)
        self.assertEqual(packet['audio']['label'], 'Unknown')
        self.assertFalse(packet['audio']['available'])
        self.assertEqual(packet['vision']['model'], 'PoultryVision-YOLOv11m')
        for forbidden in ['floorT', 'nh3', 'duty', 'setpoint', 'trim']:
            self.assertNotIn(forbidden, packet)


if __name__ == '__main__':
    unittest.main()
