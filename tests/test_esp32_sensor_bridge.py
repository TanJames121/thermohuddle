import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import esp32_sensor_bridge as bridge  # noqa: E402


class Esp32SensorBridgeTests(unittest.TestCase):
    def test_parses_ok_packet(self):
        line = json.dumps({
            "status": "ok",
            "ambient_temp_c": 31.426,
            "humidity_pct": 62.55,
            "mq137_raw": 1420,
            "mq137_volts": 0.42156,
            "nh3_rel_ppm": 2.754,
            "mq137_do_alert": False,
            "fan_on": True,
        })
        parsed = bridge.parse_esp32_line(line, now=1700000000.1234)
        self.assertEqual(parsed, {
            "available": True,
            "status": "ok",
            "ts": 1700000000.123,
            "ambient_temp_c": 31.43,
            "humidity_pct": 62.55,
            "mq137_raw": 1420,
            "mq137_volts": 0.4216,
            "nh3_rel_ppm": 2.75,
            "mq137_do_alert": False,
            "fan_on": True,
        })

    def test_parses_degraded_and_error_packets(self):
        degraded = bridge.parse_esp32_line(json.dumps({
            "status": "degraded",
            "ambient_temp_c": None,
            "humidity_pct": None,
            "mq137_raw": 900,
            "mq137_volts": 0.25,
            "nh3_rel_ppm": 1.1,
            "mq137_do_alert": False,
            "fan_on": False,
        }), now=1700000000.0)
        self.assertTrue(degraded["available"])
        self.assertIsNone(degraded["ambient_temp_c"])
        self.assertIsNone(degraded["humidity_pct"])

        err = bridge.parse_esp32_line(json.dumps({
            "status": "error",
            "msg": "ADS1115 init failed",
        }), now=1700000000.0)
        self.assertFalse(err["available"])
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["mq137_raw"], 0)

    def test_rejects_invalid_and_out_of_range_lines(self):
        self.assertIsNone(bridge.parse_esp32_line("booting esp32...", now=1700000000.0))
        self.assertIsNone(bridge.parse_esp32_line("{not json}", now=1700000000.0))
        self.assertIsNone(bridge.parse_esp32_line("[]", now=1700000000.0))
        bad_temp = json.dumps({
            "status": "ok", "ambient_temp_c": 199.0, "humidity_pct": 50.0,
            "mq137_raw": 100, "mq137_volts": 0.1, "nh3_rel_ppm": 0.5,
            "mq137_do_alert": False, "fan_on": False,
        })
        self.assertIsNone(bridge.parse_esp32_line(bad_temp, now=1700000000.0))
        bad_raw = json.dumps({
            "status": "ok", "ambient_temp_c": 30.0, "humidity_pct": 50.0,
            "mq137_raw": True, "mq137_volts": 0.1, "nh3_rel_ppm": 0.5,
            "mq137_do_alert": False, "fan_on": False,
        })
        self.assertIsNone(bridge.parse_esp32_line(bad_raw, now=1700000000.0))

    def test_fan_command_and_reader_freshness(self):
        self.assertEqual(bridge.format_fan_command(True), b"FAN:1\n")
        self.assertEqual(bridge.format_fan_command(False), b"FAN:0\n")
        reader = bridge.ESP32SerialReader(max_age_s=10.0, start=False)
        self.assertIsNone(reader.latest(now=1700000000.0))
        reader._latest = bridge.parse_esp32_line(json.dumps({
            "status": "ok", "ambient_temp_c": 29.0, "humidity_pct": 55.0,
            "mq137_raw": 500, "mq137_volts": 0.15, "nh3_rel_ppm": 0.8,
            "mq137_do_alert": False, "fan_on": False,
        }), now=1700000000.0)
        self.assertIsNotNone(reader.latest(now=1700000005.0))
        self.assertIsNone(reader.latest(now=1700000012.0))


if __name__ == "__main__":
    unittest.main()
