#!/usr/bin/env python3
"""
ThermoHuddle — Smart Brooder Edge Pipeline (DRAFT v0.1)
CpE 404 · Capstone Design 1 — Bolda, Gabriel, Payumo, Tan, Tangcuangco

Runs on Raspberry Pi 5. Pipeline per frame:
  NoIR frame → background subtraction → blob detection → chick centroids
  → spatial stats (NND, entropy) → comfort classification → cascade control
  → dimmer PWM → MQTT telemetry + tracking_latest.json for the 3D tracker.

Usage:
  python3 thermohuddle_draft.py --camera 0 --width 640 --height 480
  python3 thermohuddle_draft.py --replay dataset/  # offline data gathering
"""

import argparse
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None  # replay/analysis mode can run without OpenCV

try:
    import picam  # placeholder for your Pi camera capture module
except ImportError:
    picam = None


# ============================================================
# CONFIG — all tunables in one place
# ============================================================
@dataclass
class Config:
    # --- camera / capture ---
    camera_index: int = 0
    width: int = 640
    height: int = 480
    fps: float = 1.0                 # proposal says 1 fps is plenty
    # --- detection ---
    bg_history: int = 300            # MOG2 history frames
    bg_var_thresh: float = 24.0
    blob_min_area: int = 12          # px² — tune per camera height/res
    blob_max_area: int = 800
    morph_kernel: int = 3
    # --- floor mapping (pixels → cm) ---
    # measured once with a ruler on the floor, or via 4-point perspective fix
    floor_cm: float = 100.0          # brooder is 1.0 m × 1.0 m
    px_per_cm: float = 4.8          # calibration: floor_px_width / 100
    # --- spatial stats (fused with floor temperature) ---
    grid: int = 4                    # 4×4 occupancy grid
    nnd_tight: float = 3.0           # cm — panic-pile NND threshold
    nnd_cold_pile: float = 5.0       # cm — cold-huddle NND threshold
    ent_crowd: float = 0.58
    ent_hot: float = 0.80
    ent_draft: float = 0.75
    centroid_draft: float = 15.0    # cm — flock off-center → draft sign
    center_radius: float = 20.0      # cm — "under the lamp" zone
    center_occ_hot: float = 0.06     # fraction in lamp zone below which → HOT
    cold_floor: float = 31.5         # °C — floor below this = "cold" context
    # --- classifier hold (anti-chatter) ---
    hold_frames: int = 45
    # --- cascade controller ---
    setpoint_comfy: float = 33.0
    setpoint_cold: float = 34.5
    setpoint_hot: float = 30.5
    setpoint_draft: float = 34.0
    kp: float = 0.012
    setpoint_rate: float = 0.02      # max setpoint change per update (°C)
    pwm_min: int = 0
    pwm_max: int = 255
    # --- ammonia fan ---
    nh3_warn: float = 25.0           # ppm — exhaust fan trigger
    # --- output ---
    mqtt_host: str = "localhost"
    mqtt_topic: str = "thermohuddle/telemetry"
    json_out: Path = Path("tracking_latest.json")


# ============================================================
# DETECTION — NoIR frame → chick centroids
# ============================================================
@dataclass
class Detection:
    x_cm: float          # world X, cm from center (-50..50)
    z_cm: float          # world Z, cm from center (-50..50)
    area_px: int
    cx: float            # raw pixel centroid (for logging)
    cy: float


class ChickDetector:
    """Background-subtraction blob detector for overhead NoIR frames.

    Chicks appear as bright moving blobs against static dark litter.
    MOG2 is robust to the slow IR illumination changes; blobs are
    filtered by area and de-noised with a morphological open.
    """

    def __init__(self, cfg: Config):
        if cv2 is None:
            raise RuntimeError("OpenCV required for live detection (pip install opencv-python-headless)")
        self.cfg = cfg
        self.bgsub = cv2.createBackgroundSubtractorMOG2(
            history=cfg.bg_history, varThreshold=cfg.bg_var_thresh, detectShadows=False
        )
        k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (cfg.morph_kernel, cfg.morph_kernel)
        )
        self.kernel = k

    def detect(self, frame_bgr: "np.ndarray") -> List[Detection]:
        cfg = self.cfg
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        # gentle contrast stretch — IR frames are low-contrast
        gray = cv2.equalizeHist(gray)
        mask = self.bgsub.apply(gray)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, self.kernel)
        n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask, connectivity=8
        )
        dets = []
        half_w = cfg.width / 2.0
        half_h = cfg.height / 2.0
        for i in range(1, n_labels):  # 0 = background
            area = stats[i, cv2.CC_STAT_AREA]
            if not (cfg.blob_min_area <= area <= cfg.blob_max_area):
                continue
            cx, cy = centroids[i]
            # pixel → cm mapping (centered). Calibrate px_per_cm once;
            # replace with a homography if the camera is not perpendicular.
            x_cm = (cx - half_w) / cfg.px_per_cm
            z_cm = (cy - half_h) / cfg_px_per_cm_safe(cfg)
            dets.append(Detection(x_cm, z_cm, area, cx, cy))
        return dets


def cfg_px_per_cm_safe(cfg: Config) -> float:
    """Guard against px_per_cm = 0 (unset calibration)."""
    return cfg.px_per_cm if cfg.px_per_cm > 0 else 1.0


# ============================================================
# SPATIAL STATS — the proposal's core math
# ============================================================
class SpatialStats:
    """NND (mean nearest-neighbour distance) + Shannon occupancy entropy.

    Thresholds mirror the 3D tracker (brooder_tracker.html) so results
    stay comparable between sim and live modes.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def nnd(self, pts: np.ndarray) -> float:
        if len(pts) < 2:
            return 0.0
        d2 = ((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1)
        np.fill_diagonal(d2, np.inf)
        return float(np.sqrt(d2.min(axis=1)).mean())

    def occupancy_entropy(self, pts: np.ndarray) -> float:
        cfg = self.cfg
        if len(pts) == 0:
            return 0.0
        g = cfg.grid
        counts = np.zeros((g, g), dtype=int)
        # world -50..50 → grid index
        idx = np.clip(((pts + 50) / 100 * g).astype(int), 0, g - 1)
        np.add.at(counts, (idx[:, 1], idx[:, 0]), 1)
        p = counts[counts > 0] / len(pts)
        return float(-(p * np.log(p)).sum() / math.log(g * g))

    def centroid_distance(self, pts: np.ndarray) -> float:
        """Distance of flock centroid from brooder center (cm)."""
        if len(pts) == 0:
            return 0.0
        return float(np.hypot(*(pts.mean(axis=0))))

    def center_occupancy(self, pts: np.ndarray) -> float:
        """Fraction of the flock within the lamp zone (radius center_radius)."""
        if len(pts) == 0:
            return 0.0
        r = np.hypot(pts[:, 0], pts[:, 1])
        return float((r < self.cfg.center_radius).mean())

    def classify(self, nnd: float, entropy: float,
                 centroid_dist: float = 0.0, center_occ: float = 1.0,
                 cold_floor: bool = False) -> str:
        """Fused decision (order matters):
        1. DRAFT  — flock pushed off-center (draft flocks are also compressed;
                    the centroid offset is what separates them from cold huddles)
        2. HOT    — lamp zone abandoned + high spread entropy
        3. Pile   — tight pile: cold floor → COLD huddle; warm floor → CROWD
        4. COLD   — moderate compression + cold floor
        """
        cfg = self.cfg
        if centroid_dist > cfg.centroid_draft and entropy < cfg.ent_draft:
            return "DRAFT"
        if center_occ < cfg.center_occ_hot and entropy > cfg.ent_hot:
            return "HOT"
        if nnd < cfg.nnd_tight and entropy < cfg.ent_crowd:
            return "COLD" if cold_floor else "CROWD"
        if nnd < cfg.nnd_cold_pile and cold_floor:
            return "COLD"
        return "COMFY"


# ============================================================
# CLASSIFIER — state machine with hold timer
# ============================================================
class ComfortClassifier:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.state = "COMFY"
        self.hold = 0

    def update(self, raw_state: str) -> str:
        if raw_state == self.state:
            self.hold = 0
        else:
            self.hold += 1
            if self.hold > self.cfg.hold_frames:
                self.state = raw_state
                self.hold = 0
        return self.state


# ============================================================
# CASCADE CONTROL — outer behavioral setpoint + inner PWM loop
# ============================================================
class CascadeController:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.setpoint = cfg.setpoint_comfy
        self.pwm = 200  # start warm
        self.integral = 0.0

    def update(self, class_state: str, floor_t: float) -> int:
        cfg = self.cfg
        # outer loop: behavior → setpoint (rate-limited)
        target = {
            "COMFY": cfg.setpoint_comfy,
            "COLD": cfg.setpoint_cold,
            "HOT": cfg.setpoint_hot,
            "DRAFT": cfg.setpoint_draft,
        }.get(class_state, cfg.setpoint_comfy)
        self.setpoint += cfg.setpoint_rate * (target - self.setpoint)
        # inner loop: PI on floor temperature
        err = self.setpoint - floor_t
        self.integral = max(-200, min(200, self.integral + err * 0.002))
        self.pwm = int(np.clip(self.pwm + err * cfg.kp + self.integral * 0.001,
                               cfg.pwm_min, cfg.pwm_max))
        return self.pwm


# ============================================================
# TELEMETRY — MQTT + JSON for the 3D tracker
# ============================================================
class Telemetry:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = None
        try:
            import paho.mqtt.client as mqtt  # type: ignore
            self.client = mqtt.Client()
            self.client.connect(cfg.mqtt_host, 1883, 30)
            self.client.loop_start()
        except Exception:
            print("[telemetry] MQTT unavailable — running in offline mode")

    def publish(self, payload: dict):
        if self.client:
            try:
                self.client.publish(self.cfg.mqtt_topic, json.dumps(payload))
            except Exception:
                pass
        # always write the JSON the 3D tracker polls
        try:
            tmp = self.cfg.json_out.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload))
            tmp.replace(self.cfg.json_out)
        except Exception:
            pass


# ============================================================
# MAIN LOOP
# ============================================================
def run_live(cfg: Config):
    if cv2 is None or picam is None:
        raise RuntimeError(
            "Live mode needs OpenCV + a capture module. For development, "
            "run with --replay <dir> on your laptop first."
        )
    detector = ChickDetector(cfg)
    stats = SpatialStats(cfg)
    classifier = ComfortClassifier(cfg)
    ctrl = CascadeController(cfg)
    telemetry = Telemetry(cfg)
    period = 1.0 / cfg.fps

    print(f"[thermohuddle] live: camera {cfg.camera_index} @ {cfg.fps} fps")
    t_next = time.monotonic()
    frame_no = 0
    while True:
        frame = picam.capture_array()  # numpy BGR
        dets = detector.detect(frame)
        pts = np.array([[d.x_cm, d.z_cm] for d in dets], dtype=float)
        nnd = stats.nnd(pts)
        entropy = stats.occupancy_entropy(pts)
        centroid_dist = stats.centroid_distance(pts)
        center_occ = stats.center_occupancy(pts)
        # placeholder floor temp: replace with real DS18B20 read
        floor_t = read_floor_temp_stub()
        cold_floor = floor_t < cfg.cold_floor
        state = classifier.update(
            stats.classify(nnd, entropy, centroid_dist, center_occ, cold_floor)
        )
        pwm = ctrl.update(state, floor_t)

        telemetry.publish({
            "ts": time.time(),
            "frame": frame_no,
            "chicks": [[round(d.x_cm, 1), round(d.z_cm, 1)] for d in dets],
            "count": len(dets),
            "nnd": round(nnd, 2),
            "entropy": round(entropy, 3),
            "state": state,
            "floorT": round(floor_t, 1),
            "setpoint": round(ctrl.setpoint, 1),
            "pwm": pwm,
            "nh3": read_nh3_stub(),
        })
        frame_no += 1
        t_next += period
        time.sleep(max(0, t_next - time.monotonic()))


def read_floor_temp_stub() -> float:
    """Replace with w1thermsensor DS18B20 read (4-sensor average)."""
    return 32.5


def read_nh3_stub() -> float:
    """Replace with ADS1115 + MQ-137 read (after clean-air baseline)."""
    return 6.0


# ============================================================
# REPLAY MODE — data gathering & threshold tuning on recordings
# ============================================================
def run_replay(cfg: Config, frames_dir: Path):
    """Replay saved frames through the detector to tune thresholds and
    gather labeled data without chicks present (or while recording)."""
    if cv2 is None:
        raise RuntimeError("Replay mode needs OpenCV installed")
    detector = ChickDetector(cfg)
    stats = SpatialStats(cfg)
    classifier = ComfortClassifier(cfg)
    out_rows = []
    frames = sorted(frames_dir.glob("*.png")) + sorted(frames_dir.glob("*.jpg"))
    print(f"[replay] {len(frames)} frames in {frames_dir}")
    for i, fp in enumerate(frames):
        img = cv2.imread(str(fp))
        if img is None:
            continue
        dets = detector.detect(img)
        pts = np.array([[d.x_cm, d.z_cm] for d in dets], dtype=float)
        nnd = stats.nnd(pts)
        entropy = stats.occupancy_entropy(pts)
        centroid_dist = stats.centroid_distance(pts)
        center_occ = stats.center_occupancy(pts)
        cold_floor = read_floor_temp_stub() < cfg.cold_floor
        state = classifier.update(
            stats.classify(nnd, entropy, centroid_dist, center_occ, cold_floor)
        )
        out_rows.append({
            "frame": i, "file": fp.name, "count": len(dets),
            "nnd": round(nnd, 2), "entropy": round(entropy, 3),
            "centroid_dist": round(centroid_dist, 1),
            "center_occ": round(center_occ, 2), "state": state,
        })
        print(f"  {fp.name}: {len(dets)} chicks, NND {nnd:.1f} cm, "
              f"H {entropy:.2f} → {state}")
    outp = frames_dir / "replay_results.json"
    outp.write_text(json.dumps(out_rows, indent=2))
    print(f"[replay] results → {outp}")


# ============================================================
def main():
    ap = argparse.ArgumentParser(description="ThermoHuddle edge pipeline (draft)")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fps", type=float, default=1.0)
    ap.add_argument("--replay", type=str, help="directory of saved frames to replay")
    ap.add_argument("--out", type=str, default="tracking_latest.json")
    args = ap.parse_args()

    cfg = Config(
        camera_index=args.camera, width=args.width, height=args.height,
        fps=args.fps, json_out=Path(args.out),
    )
    if args.replay:
        run_replay(cfg, Path(args.replay))
    else:
        run_live(cfg)


if __name__ == "__main__":
    main()
