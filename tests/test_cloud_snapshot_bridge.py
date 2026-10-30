"""Tests-only fixtures; these samples are never sent to a cloud endpoint."""
import contextlib
import copy
import io
import json
import os
import tempfile
import urllib.error
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "pipeline/cloud_snapshot_bridge.py"
if MODULE.exists():
    spec = importlib.util.spec_from_file_location("cloud_snapshot_bridge", MODULE)
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
else:
    bridge = None


def sample():
    return {
        "ts": 1700000000.0, "seq": 1, "boot_id": "012345abcdef",
        "count": 1, "chicks": [[-2.5, 4]], "cam_ok": True,
        "audio": {"level_db": -35, "peak_hz": 3200,
                  "label": "normal", "distress_ratio": 0.2},
    }


class SnapshotTests(unittest.TestCase):
    def test_allowlist_drops_thermal_control_and_nested_secrets(self):
        self.assertIsNotNone(bridge, "snapshot bridge implementation is missing")
        source = sample()
        expected = copy.deepcopy(source)
        source.update(floorT=32.5, state="warm", conf=0.8,
                      secret="tests-only-not-a-credential", control={"duty": 5})
        source["audio"]["secret"] = {"token": "tests-only"}
        self.assertEqual(bridge.sanitize(source, now=1700000001), expected)

    def test_rejects_stale_future_nonfinite_and_invalid_fields(self):
        invalid = [
            ("ts", 1699999971), ("ts", 1700000002), ("ts", float("nan")),
            ("ts", float("inf")), ("ts", True), ("ts", "1700000000"),
            ("count", -1), ("count", 1.5), ("count", True), ("count", 2),
            ("seq", -1), ("seq", False), ("boot_id", "secret:not-an-id"),
            ("cam_ok", "true"), ("chicks", [[0, float("inf")]]),
            ("chicks", [[0, float("nan")]]), ("chicks", [[True, 1]]),
            ("chicks", [[0, 1, 2]]), ("chicks", [[10001, 0]]),
            ("chicks", [[0, 0]] * 1001), ("audio", []),
        ]
        for key, value in invalid:
            with self.subTest(key=key, value=value):
                source = sample()
                source[key] = value
                with self.assertRaises(ValueError):
                    bridge.sanitize(source, now=1700000001)
        for key, value in [("level_db", float("nan")), ("peak_hz", float("inf")),
                           ("level_db", True), ("peak_hz", -1),
                           ("distress_ratio", 1.1), ("label", "secret-text")]:
            with self.subTest(audio=key):
                source = sample()
                source["audio"][key] = value
                with self.assertRaises(ValueError):
                    bridge.sanitize(source, now=1700000001)
        for key in ("ts", "count", "chicks", "cam_ok"):
            source = sample()
            del source[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                bridge.sanitize(source, now=1700000001)
        with self.assertRaises(ValueError):
            bridge.sanitize([], now=1700000001)

    def test_preserves_empty_camera_detections_and_existing_optional_fields(self):
        source = sample()
        source.update(count=0, chicks=[], cam_ok=False)
        del source["seq"], source["boot_id"], source["audio"]
        self.assertEqual(bridge.sanitize(source, now=1700000001), source)


class PublishingTests(unittest.TestCase):
    def test_upload_headers_allowlist_duplicates_and_retry(self):
        self.assertTrue(hasattr(bridge, "Bridge"), "polling bridge is missing")
        requests = []
        fail = [True]

        def sender(request, *, timeout):
            requests.append(request)
            self.assertEqual(timeout, 10)
            if fail[0]:
                raise urllib.error.HTTPError(request.full_url, 503,
                                             "tests-only-secret-error", {}, None)
            response = io.BytesIO(b"")
            response.status = 200
            return response

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            path = Path(directory) / "tests-only.json"
            source = sample()
            source["secret"] = "tests-only"
            path.write_text(json.dumps(source))
            worker = bridge.Bridge(path, "thoissoyiupjrrsqmika", "tests-only-key",
                                   opener=sender, clock=lambda: 1700000001)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(worker.step(), 4)
                fail[0] = False
                self.assertEqual(worker.step(), 2)
                self.assertEqual(worker.step(), 2)
            self.assertEqual(len(requests), 2)
            self.assertNotIn("tests-only-secret-error", output.getvalue())
            request = requests[-1]
            self.assertEqual(request.full_url,
                "https://thoissoyiupjrrsqmika.supabase.co/storage/v1/object/frames/telemetry/latest.json")
            self.assertEqual(request.method, "POST")
            headers = {key.lower(): value for key, value in request.header_items()}
            self.assertEqual(headers["content-type"], "application/json")
            self.assertEqual(headers["cache-control"], "max-age=0")
            self.assertEqual(headers["x-upsert"], "true")
            self.assertEqual(headers["apikey"], "tests-only-key")
            self.assertEqual(headers["authorization"], "Bearer tests-only-key")
            self.assertEqual(json.loads(request.data), sample())
            # Either unchanged timestamp or sequence must suppress a duplicate.
            source["seq"] = 2
            path.write_text(json.dumps(source))
            worker.step()
            source.update(ts=1700000000.5, seq=1)
            path.write_text(json.dumps(source))
            worker.step()
            self.assertEqual(len(requests), 2)
            source["seq"] = 2
            path.write_text(json.dumps(source))
            worker.step()
            self.assertEqual(len(requests), 3)

    def test_partial_missing_stale_and_failed_uploads_retry_without_refresh(self):
        requests = []
        now = [1700000001]

        def sender(request, *, timeout):
            requests.append(request)
            raise urllib.error.URLError("tests-only-secret-network-message")

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            path = Path(directory) / "tests-only.json"
            worker = bridge.Bridge(path, "thoissoyiupjrrsqmika", "tests-only-key",
                                   opener=sender, clock=lambda: now[0])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(worker.step(), 2)  # missing source
                path.write_text('{"ts":')
                self.assertEqual(worker.step(), 2)  # mid-write source
                path.write_text(json.dumps(sample()))
                self.assertEqual([worker.step() for _ in range(7)],
                                 [4, 8, 16, 30, 30, 30, 30])
                self.assertIsNone(worker.last)
                now[0] = 1700000030
                self.assertEqual(worker.step(), 2)
                self.assertEqual(len(requests), 7)
                path.write_text("[" * 1100)
                self.assertEqual(worker.step(), 2)  # deeply malformed source
                path.write_text(json.dumps(sample()) + " " * (256 * 1024))
                self.assertEqual(worker.step(), 2)  # oversized source
                self.assertEqual(len(requests), 7)
            self.assertNotIn("tests-only-secret", output.getvalue())

    def test_runtime_requires_environment_credentials_without_disclosure(self):
        import subprocess
        import sys
        result = subprocess.run([sys.executable, str(MODULE), "--source", "tests-only"],
                                env={}, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing or invalid Supabase runtime configuration", result.stderr)

    def test_export_style_private_config_prepared_for_systemd_safely(self):
        self.assertTrue(hasattr(bridge, "prepare_environment"),
                        "private config normalization is missing")
        import stat
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            source = Path(directory) / "tests-only-source.env"
            target = Path(directory) / "tests-only-runtime.env"
            source.write_text("export SUPABASE_PROJECT_REF=thoissoyiupjrrsqmika\n"
                              "export SUPABASE_SERVICE_ROLE_KEY='tests-only-key'\n"
                              "export OTHER_SECRET=tests-only-unrelated\n")
            source.chmod(0o600)
            bridge.prepare_environment(source, target)
            self.assertEqual(target.read_text(),
                             "SUPABASE_PROJECT_REF=thoissoyiupjrrsqmika\n"
                             "SUPABASE_SERVICE_ROLE_KEY=tests-only-key\n")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            source.chmod(0o644)
            with self.assertRaises(ValueError):
                bridge.prepare_environment(source, target)

    def test_redirects_cannot_forward_privileged_headers(self):
        self.assertTrue(hasattr(bridge, "NoRedirect"), "redirect protection is missing")
        handler = bridge.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 307, "", {},
                                                   "https://example.invalid/"))


if __name__ == "__main__":
    unittest.main()
