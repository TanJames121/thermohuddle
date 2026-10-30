#!/usr/bin/env python3
"""Publish allowlisted camera/mic JSON only; credentials stay in runtime env."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shlex
import stat
import time
import urllib.error
import urllib.request


def number(value, low, high):
    return (type(value) in (int, float) and low <= value <= high
            and math.isfinite(value))


def sanitize(source, *, now):
    """Reject malformed/stale samples; never synthesize a measurement or time."""
    if not isinstance(source, dict):
        raise ValueError("invalid snapshot")
    ts = source.get("ts")
    if not number(ts, 1, now) or now - ts >= 30:
        raise ValueError("stale or invalid timestamp")
    chicks = source.get("chicks")
    count = source.get("count")
    if (type(count) is not int or not 0 <= count <= 1000
            or not isinstance(chicks, list) or len(chicks) != count):
        raise ValueError("invalid detections")
    if any(not isinstance(point, list) or len(point) != 2
           or not all(number(n, -10000, 10000) for n in point)
           for point in chicks):
        raise ValueError("invalid positions")
    if type(source.get("cam_ok")) is not bool:
        raise ValueError("invalid camera flag")
    if "seq" in source and (type(source["seq"]) is not int
                             or not 0 <= source["seq"] <= 2**63 - 1):
        raise ValueError("invalid sequence")
    if "boot_id" in source and (not isinstance(source["boot_id"], str)
                               or not re.fullmatch(r"[0-9a-f]{12,32}", source["boot_id"])):
        raise ValueError("invalid boot identifier")
    if "audio" in source:
        audio = source["audio"]
        if not isinstance(audio, dict):
            raise ValueError("invalid audio")
        for key, bounds in (("level_db", (-200, 10)), ("peak_hz", (0, 96000)),
                            ("distress_ratio", (0, 1))):
            if key in audio and not number(audio[key], *bounds):
                raise ValueError("invalid audio measurement")
        if "label" in audio and audio["label"] not in (
                "quiet", "normal", "loud", "distress_like"):
            raise ValueError("invalid audio label")
    snapshot = {key: source[key] for key in
                ("ts", "seq", "boot_id", "count", "chicks", "cam_ok")
                if key in source}
    if "audio" in source:
        snapshot["audio"] = {key: source["audio"][key] for key in
                             ("level_db", "peak_hz", "label", "distress_ratio")
                             if key in source["audio"]}
    return snapshot


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward service credentials to another endpoint.


class Bridge:
    def __init__(self, source, project_ref, key, *, opener=None,
                 clock=time.time):
        self.source = Path(source)
        self.url = (f"https://{project_ref}.supabase.co/storage/v1/object/"
                    "frames/telemetry/latest.json")
        self.key = key
        self.opener = opener or urllib.request.build_opener(NoRedirect()).open
        self.clock = clock
        self.last = None
        self.delay = 2

    def step(self):
        """One poll; mark a sample sent only after a successful upload."""
        try:
            with self.source.open("rb") as stream:
                raw = stream.read(256 * 1024 + 1)
            if len(raw) > 256 * 1024:
                raise ValueError("oversized snapshot")
            snapshot = sanitize(json.loads(raw), now=self.clock())
        except (OSError, ValueError, RecursionError):
            # Includes JSONDecodeError while the producer is writing its file.
            return 2
        if self.last is not None:
            if snapshot["ts"] <= self.last["ts"]:
                return 2
            if (snapshot.get("boot_id") == self.last.get("boot_id")
                    and "seq" in snapshot and "seq" in self.last
                    and snapshot["seq"] <= self.last["seq"]):
                return 2
        request = urllib.request.Request(
            self.url, data=json.dumps(snapshot, allow_nan=False,
                                      separators=(",", ":")).encode(), method="POST",
            headers={"Content-Type": "application/json", "Cache-Control": "max-age=0",
                     "x-upsert": "true", "apikey": self.key,
                     "Authorization": "Bearer " + self.key})
        try:
            with self.opener(request, timeout=10) as response:
                if not 200 <= response.status < 300:
                    raise OSError("upload failed")
        except urllib.error.HTTPError as error:
            # Never log error bodies, headers, URLs or credentials.
            print(f"snapshot upload HTTP {error.code}", flush=True)
            self.delay = min(self.delay * 2, 30)
            return self.delay
        except (OSError, ValueError):
            print("snapshot upload unavailable", flush=True)
            self.delay = min(self.delay * 2, 30)
            return self.delay
        self.last = snapshot
        self.delay = 2
        return 2


def configuration(values):
    project_ref = values.get("SUPABASE_PROJECT_REF", "")
    key = values.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if (not re.fullmatch(r"[a-z]{20}", project_ref) or not key
            or any(c.isspace() for c in key)):
        raise ValueError("invalid runtime configuration")
    return project_ref, key


def prepare_environment(source, target):
    """Normalize private shell-style exports without executing shell or logging."""
    metadata = source.stat()
    if stat.S_IMODE(metadata.st_mode) & 0o077 or metadata.st_uid != os.getuid():
        raise ValueError("configuration must be private")
    values = {}
    for line in source.read_text().splitlines():
        tokens = shlex.split(line, comments=True)
        if tokens and tokens[0] == "export":
            tokens = tokens[1:]
        for token in tokens:
            name, separator, value = token.partition("=")
            if separator and name in ("SUPABASE_PROJECT_REF", "SUPABASE_SERVICE_ROLE_KEY"):
                values[name] = value
    project_ref, key = configuration(values)
    # The user service owns the 0700 runtime directory. Nothing enters the repo.
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(f"SUPABASE_PROJECT_REF={project_ref}\nSUPABASE_SERVICE_ROLE_KEY={key}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--source", type=Path)
    mode.add_argument("--prepare-env", type=Path, metavar="PRIVATE_RUNTIME_FILE")
    args = parser.parse_args()
    try:
        if args.prepare_env:
            prepare_environment(Path.home() / ".config/thermohuddle/supabase.env",
                                args.prepare_env)
            return
        # systemd EnvironmentFile supplies only the two runtime variables.
        project_ref, key = configuration(os.environ)
    except (OSError, ValueError):
        raise SystemExit("missing or invalid Supabase runtime configuration") from None
    worker = Bridge(args.source, project_ref, key)
    while True:
        time.sleep(worker.step())


if __name__ == "__main__":
    main()
