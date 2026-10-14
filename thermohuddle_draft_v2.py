#!/usr/bin/env python3
"""
ThermoHuddle — Edge Pipeline (DRAFT v0.2 — aligned with the Software Build Plan)

CpE 404 · Capstone Design 1 — Bolda, Gabriel, Payumo, Tan, Tangcuangco

Aligned with the team Software Build Plan (Oct 14, 2026):
  * Age-based baseline schedule (34→29°C, Day 1–14) + bounded trim (±2°C)
    instead of per-state absolute setpoints. Trim follows the S3 rules:
    10-min dwell, 1°C/h rate limit, fan blanking, camera-loss decay.
  * Crowding is a DETERMINISTIC hard override OUTSIDE the classifier
    (S6): max-cell-fraction rule → alarm + vent burst + human ack.
  * Comfort classification = COMFY/COLD/HOT/DRAFT only, as a 60-s
    windowed decision with a temporal filter (4-of-5 agreement).
  * Plan-style MQTT topics: telemetry/env, inference/window,
    control/setpoint, events, status. Payloads carry version,
    ts, boot_id, seq (S0 schema rules).
  * Ammonia S2 rules: 25 ppm on / 15 ppm off hysteresis, 5-min min-run,
    50 ppm critical, MQ-137 10-min warmup with scheduled venting.

This is still the single-file draft for bring-up and data gathering; the
real system splits into th-sensord / th-visiond / th-audiod / th-brain /
th-uplink per the build plan.

Usage:
  python3 thermohuddle_draft.py --camera 0 --width 640 --height 480
  python3 thermohuddle_draft.py --replay dataset/          # offline tuning
  python3 thermohuddle_draft.py --simulate                 # no hardware at all
"""

import argparse
import json
import math
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

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
# CONFIG — all tunables in one place ([A] = assumption from the plan)
# ============================================================
@dataclass
class Config:
    # --- camera / capture ---
    camera_index: int = 0
    width: int = 640
    height: int = 480
    fps: float = 0.2               # plan: 0.2 fps (5 s interval)
    # --- detection ---
    bg_history: int = 300
    bg_var_thresh: float = 24.0
    blob_min_area: int = 12
    blob_max_area: int = 800
    single_chick_area_px: int = 60    # [A] tune per camera height/res
    morph_kernel: int = 3
    # --- floor mapping (pixels → cm) ---
    floor_cm: float = 100.0
    px_per_cm: float = 4.8
    # --- spatial stats / classifier ---
    grid: int = 4
    nnd_tight: float = 3.0
    nnd_cold_pile: float = 5.0
    ent_crowd: float = 0.58
    ent_hot: float = 0.80
    ent_draft: float = 0.75
    centroid_draft: float = 15.0
    center_radius: float = 20.0
    center_occ_hot: float = 0.06
    cold_floor: float = 31.5
    # --- temporal filter (S6) ---
    window_s: float = 60.0            # one decision window
    temporal_agree: int = 4            # 4 of last 5 windows must agree
    temporal_conf: float = 0.6         # [A] top-probability cutoff
    # --- crowding hard override (S6, outside the model) ---
    crowd_cell_frac: float = 0.45     # [A] max-cell-fraction threshold
    crowd_windows: int = 3            # consecutive windows to fire
    # --- baseline schedule + trim (S1/S3) ---
    brooding_day: int = 1
    base_day1_c: float = 34.0         # [A] linear 34 → 29 °C
    base_day14_c: float = 29.0
    trim_step_c: float = 0.5          # per-state step from the signature table
    trim_limit: float = 2.0           # ±2.0 °C authority
    trim_rate_c_per_h: float = 1.0    # [A] 1 °C/h
    trim_dwell_s: float = 600.0       # [A] 10 min between trims
    # --- fan blanking (S3) ---
    fan_blank_s: float = 600.0        # fans on → draft outputs suppressed 10 min [A]
    # --- inner PID (S1) — tuned on PlantSim (tau=120s, dead 8s):
    # kp=0.6/ki=0.01 → converges ~33°C, <1°C overshoot; re-tune after dummy-load test
    kp: float = 0.6
    ki: float = 0.01
    kd: float = 0.0
    ts_s: float = 2.0                 # control loop period
    duty_min: float = 0.0
    duty_max: float = 100.0
    ramp_limit_per_s: float = 100.0 / 60.0 / 20.0   # soft-start ≤5 %/min [A]
    # --- ammonia (S2) ---
    nh3_on: float = 25.0
    nh3_off: float = 15.0
    nh3_min_run_s: float = 300.0
    nh3_crit: float = 50.0
    mq137_warmup_s: float = 600.0
    # --- hard safety (S2) ---
    t_max_c: float = 38.0             # over-temp cutoff
    t_resume_c: float = 36.0          # resume at T_max − 2
    # --- MQTT (plan topics) ---
    mqtt_host: str = "localhost"
    topic_env: str = "thermohuddle/telemetry/env"
    topic_infer: str = "thermohuddle/inference/window"
    topic_sp: str = "thermohuddle/control/setpoint"
    topic_events: str = "thermohuddle/events"
    topic_status: str = "thermohuddle/status"
    json_out: Path = Path("tracking_latest.json")
    boot_id: str = ""


def make_boot_id() -> str:
    return uuid.uuid4().hex[:12]


def baseline_schedule(day: int, cfg: Config) -> float:
    """Age-based baseline setpoint: linear 34 °C (Day 1) → 29 °C (Day 14) [A]."""
    day = min(max(day, 1), 14)
    frac = (day - 1) / 13.0
    return cfg.base_day1_c + frac * (cfg.base_day14_c - cfg.base_day1_c)


# ============================================================
# DETECTION — NoIR frame → chick centroids
# ============================================================
@dataclass
class Detection:
    x_cm: float
    z_cm: float
    area_px: int
    cx: float
    cy: float


class ChickDetector:
    """Background-subtraction blob detector for overhead NoIR frames."""

    def __init__(self, cfg: Config):
        if cv2 is None:
            raise RuntimeError("OpenCV required (pip install opencv-python-headless)")
        self.cfg = cfg
        self.bgsub = cv2.createBackgroundSubtractorMOG2(
            history=cfg.bg_history, varThreshold=cfg.bg_var_thresh, detectShadows=False
        )
        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (cfg.morph_kernel, cfg.morph_kernel)
        )

    def detect(self, frame_bgr) -> List[Detection]:
        cfg = self.cfg
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        mask = self.bgsub.apply(gray)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, self.kernel)
        n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask, connectivity=8
        )
        dets = []
        half_w, half_h = cfg.width / 2.0, cfg.height / 2.0
        for i in range(1, n_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if not (cfg.blob_min_area <= area <= cfg.blob_max_area):
                continue
            cx, cy = centroids[i]
            x_cm = (cx - half_w) / cfg.px_per_cm
            z_cm = (cy - half_h) / cfg.px_per_cm
            dets.append(Detection(x_cm, z_cm, area, cx, cy))
        return dets


# ============================================================
# SPATIAL STATS — plan feature set (subset in the draft)
# ============================================================
class SpatialStats:
    """Features from S4: NND stats, Clark–Evans R, occupancy entropy,
    centroid offset, anisotropy, max cell fraction, radial distance,
    hidden fraction. The draft computes the ones the app HUD mirrors;
    the full set lands in th-visiond/features.py."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    # ---- features ----
    def nnd_stats(self, pts: np.ndarray) -> dict:
        if len(pts) < 2:
            return {"mean": 0.0, "median": 0.0, "cov": 0.0}
        d2 = ((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1)
        np.fill_diagonal(d2, np.inf)
        d = np.sqrt(d2.min(axis=1))
        mean = float(d.mean())
        cov = float(d.std() / d.mean()) if d.mean() > 0 else 0.0
        return {"mean": mean, "median": float(np.median(d)), "cov": cov}

    def clark_evans(self, pts: np.ndarray) -> float:
        """R = mean NND / (0.5·√(A/n)); R<1 clustered, ~1 random, >1 uniform."""
        n = len(pts)
        if n < 2:
            return 1.0
        A = (self.cfg.floor_cm / 100.0) ** 2  # m²
        expected = 0.5 * math.sqrt(A / n)
        return float(self.nnd_stats(pts)["mean"] / 100.0 / expected)

    def occupancy_entropy(self, pts: np.ndarray) -> float:
        cfg = self.cfg
        if len(pts) == 0:
            return 0.0
        g = cfg.grid
        counts = np.zeros((g, g), dtype=int)
        idx = np.clip(((pts + 50) / 100 * g).astype(int), 0, g - 1)
        np.add.at(counts, (idx[:, 1], idx[:, 0]), 1)
        p = counts[counts > 0] / len(pts)
        return float(-(p * np.log2(p)).sum() / 4.0)  # H/4, normalized per plan

    def max_cell_fraction(self, pts: np.ndarray) -> float:
        if len(pts) == 0:
            return 0.0
        g = self.cfg.grid
        counts = np.zeros((g, g), dtype=int)
        idx = np.clip(((pts + 50) / 100 * g).astype(int), 0, g - 1)
        np.add.at(counts, (idx[:, 1], idx[:, 0]), 1)
        return float(counts.max() / len(pts))

    def centroid_distance(self, pts: np.ndarray) -> float:
        if len(pts) == 0:
            return 0.0
        return float(np.hypot(*(pts.mean(axis=0))))

    def anisotropy(self, pts: np.ndarray) -> float:
        """Eigenvalue ratio of position covariance (λ2/λ1 ∈ [0,1];
        low = stretched/lopsided flock)."""
        if len(pts) < 3:
            return 1.0
        cov = np.cov(pts.T)
        if cov.ndim != 2 or cov.shape != (2, 2):
            return 1.0
        ev = np.linalg.eigvalsh(cov)
        if ev[1] <= 1e-9:
            return 1.0
        return float(ev[0] / ev[1])

    def center_occupancy(self, pts: np.ndarray) -> float:
        if len(pts) == 0:
            return 0.0
        r = np.hypot(pts[:, 0], pts[:, 1])
        return float((r < self.cfg.center_radius).mean())

    def radial_distance(self, pts: np.ndarray) -> float:
        if len(pts) == 0:
            return 0.0
        return float(np.hypot(pts[:, 0], pts[:, 1]).mean())

    # ---- comfort classification (CROWDING handled outside!) ----
    def classify(self, feats: dict, cold_floor: bool) -> str:
        """COMFY / COLD / HOT / DRAFT only. Crowding is a separate
        deterministic rule (see CrowdingOverride)."""
        cfg = self.cfg
        nnd = feats["nnd_mean"]
        entropy = feats["entropy"]
        centroid = feats["centroid"]
        center_occ = feats["center_occ"]
        if centroid > cfg.centroid_draft and entropy < cfg.ent_draft:
            return "DRAFT"
        if center_occ < cfg.center_occ_hot and entropy > cfg.ent_hot:
            return "HOT"
        if nnd < cfg.nnd_cold_pile and cold_floor:
            return "COLD"
        return "COMFY"


# ============================================================
# CROWDING HARD OVERRIDE — deterministic, outside the model (S6)
# ============================================================
class CrowdingOverride:
    """Fires when max cell fraction ≥ threshold for N consecutive
    windows: alarm + notification + ventilation burst, re-alerting
    every 5 min until acknowledged (human in the loop)."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.streak = 0
        self.active = False
        self.last_alert = 0.0

    def update(self, max_cell_frac: float, now: float) -> dict:
        cfg = self.cfg
        if max_cell_frac >= cfg.crowd_cell_frac:
            self.streak += 1
        else:
            self.streak = 0
        fired = False
        if self.streak >= cfg.crowd_windows and not self.active:
            self.active = True
            self.last_alert = now
            fired = True
        elif self.active and now - self.last_alert >= 300.0:
            self.last_alert = now
            fired = True   # re-alert every 5 min until acknowledged
        return {
            "active": self.active,
            "fired": fired,
            "streak": self.streak,
            "action": "alarm+vent_burst+notify" if self.active else "none",
        }

    def acknowledge(self):
        """Human ack via cmd topic clears the latched alarm."""
        self.active = False
        self.streak = 0


# ============================================================
# TEMPORAL FILTER (S6) — 4-of-5 window agreement
# ============================================================
class TemporalFilter:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.history: List[str] = []

    def update(self, raw_state: str) -> Optional[str]:
        """Returns the confirmed state when ≥4 of last 5 windows agree,
        else None (hold the previous decision)."""
        self.history.append(raw_state)
        if len(self.history) > 5:
            self.history.pop(0)
        if len(self.history) < 5:
            return None
        votes = {}
        for s in self.history:
            votes[s] = votes.get(s, 0) + 1
        top, count = max(votes.items(), key=lambda kv: kv[1])
        if count >= self.cfg.temporal_agree:
            self.history.clear()  # window consumed
            return top
        return None


# ============================================================
# TRIM MANAGER (S3) — bounded behavioral trim on the baseline
# ============================================================
class TrimManager:
    """trim = clamp(trim + step[state], ±limit); applied only when the
    decision is confirmed, dwell ≥10 min elapsed, rate ≤1 °C/h, and fan
    blanking is off. Camera loss → freeze and decay to 0 over 30 min."""

    STEP = {"COMFY": 0.0, "COLD": +0.5, "HOT": -0.5, "DRAFT": +0.5}

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.trim = 0.0
        self.last_change = None      # None = dwell starts at first confirmed window
        self.rate_window: List[tuple] = []   # (t, trim) for 1 °C/h check
        self.fan_until = 0.0                 # fan blanking deadline
        self.cam_lost_at: Optional[float] = None

    def note_fans(self, now: float):
        self.fan_until = max(self.fan_until, now + self.cfg.fan_blank_s)

    def note_camera_lost(self, now: float):
        """Freeze + decay-to-0 trigger; remembers the trim at loss."""
        if self.cam_lost_at is None:
            self._trim_at_loss = self.trim
            self.cam_lost_at = now

    def note_camera_back(self):
        self.cam_lost_at = None

    def update(self, state: str, now: float) -> float:
        cfg = self.cfg
        # camera loss: freeze + linear decay to 0 over 30 min
        if self.cam_lost_at is not None:
            dt = now - self.cam_lost_at
            self.trim = max(0.0, self._trim_at_loss * (1 - dt / 1800.0))
            if dt >= 1800.0:
                self.trim = 0.0
            return self.trim
        # fan blanking: DRAFT and COLD are logged but suppressed
        if now < self.fan_until and state in ("DRAFT", "COLD"):
            return self.trim
        if state not in self.STEP:
            return self.trim
        if self.last_change is None:
            # first confirmed window after boot: start the dwell clock
            self.last_change = now
            return self.trim
        if now - self.last_change < cfg.trim_dwell_s:
            return self.trim
        # rate limit: 1 °C/h over the trailing hour
        self.rate_window = [(t, v) for (t, v) in self.rate_window if t > now - 3600.0]
        if self.rate_window:
            (t0, v0), _ = self.rate_window[0], self.rate_window[-1]
            moved = abs(self.rate_window[-1][1] - self.rate_window[0][1])
            span = max(1e-6, self.rate_window[-1][0] - self.rate_window[0][0])
            rate = moved / (span / 3600.0)
            if rate >= cfg.trim_rate_c_per_h:
                return self.trim
        new = float(np.clip(self.trim + self.STEP[state], -cfg.trim_limit, cfg.trim_limit))
        if abs(new - self.trim) > 1e-9:
            self.trim = new
            self.last_change = now
            self.rate_window.append((now, new))
        return self.trim

    def trim_off(self):
        """Instant off switch (cmd topic) — resets to 0."""
        self.trim = 0.0


# ============================================================
# SAFETY (S2) — deterministic rules, work with the brain dead
# ============================================================
class SafetyRules:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.vent_until = 0.0
        self.crit_active = False
        self.mq_warmup_end = 0.0
        self.overtemp_active = False

    def begin_boot(self, now: float):
        self.mq_warmup_end = now + self.cfg.mq137_warmup_s

    def evaluate(self, pv: float, nh3: float, now: float) -> dict:
        cfg = self.cfg
        heater_ok = True
        vent = False
        alarm = False
        reasons = []
        # over-temperature (P1) — resume clears before outputs are applied
        if pv > cfg.t_max_c:
            self.overtemp_active = True
        if self.overtemp_active:
            if pv < cfg.t_resume_c:
                self.overtemp_active = False
                reasons.append("OVERTEMP_RESUMED")
            else:
                heater_ok = False
                vent = True
                alarm = True
                reasons.append("OVERTEMP")
        # ammonia (P2) — hysteresis + min-run; warmup → scheduled vent
        warming = now < self.mq_warmup_end
        if warming:
            # scheduled ventilation: 5 min every 30 [A]
            phase = (now - (self.mq_warmup_end - cfg.mq137_warmup_s)) % 1800.0
            if phase < 300.0:
                vent = True
                reasons.append("MQ137_WARMUP_VENT")
        else:
            if nh3 >= cfg.nh3_on and not self.crit_active:
                self.vent_until = max(self.vent_until, now + cfg.nh3_min_run_s)
            if nh3 >= cfg.nh3_crit:
                self.crit_active = True
            if self.crit_active:
                vent = True
                alarm = True
                reasons.append("NH3_CRITICAL")
            if now < self.vent_until:
                vent = True
                if "NH3_VENT" not in reasons:
                    reasons.append("NH3_VENT")
            elif nh3 < cfg.nh3_off and not self.crit_active:
                self.vent_until = 0.0
        return {"heater_ok": heater_ok, "vent": vent, "alarm": alarm,
                "reasons": reasons, "mq_warming": warming,
                "crit_active": self.crit_active,
                "overtemp": self.overtemp_active}


# ============================================================
# INNER PID (S1) — positional form, derivative on PV, anti-windup
# ============================================================
class PID:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.integral = 0.0
        self.prev_pv = None
        self.duty = 0.0

    def update(self, sp: float, pv: float) -> float:
        cfg = self.cfg
        err = sp - pv
        self.integral = float(np.clip(self.integral + err * cfg.ki * cfg.ts_s,
                                      -50.0, 50.0))   # anti-windup clamp
        d = 0.0 if self.prev_pv is None else -(pv - self.prev_pv) / cfg.ts_s
        self.prev_pv = pv
        u = cfg.kp * err + self.integral + cfg.kd * d
        target = float(np.clip(u, cfg.duty_min, cfg.duty_max))
        # ramp limit (soft-start ≤5%/min toward baseline on boot; general slew)
        max_step = cfg.ramp_limit_per_s * cfg.ts_s
        self.duty += float(np.clip(target - self.duty, -max_step, max_step))
        return self.duty


# ============================================================
# TELEMETRY — plan-style topics + JSON for the 3D tracker
# ============================================================
class Telemetry:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.seq = 0
        self.client = None
        try:
            import paho.mqtt.client as mqtt  # type: ignore
            self.client = mqtt.Client()
            self.client.connect(cfg.mqtt_host, 1883, 30)
            self.client.loop_start()
        except Exception:
            print("[telemetry] MQTT unavailable — offline mode")

    def _publish(self, topic: str, payload: dict):
        if self.client:
            try:
                self.client.publish(topic, json.dumps(payload))
            except Exception:
                pass

    def publish_env(self, d: dict):
        cfg = self.cfg
        self.seq += 1
        p = {"v": 1, "ts": time.time(), "boot_id": cfg.boot_id,
             "seq": self.seq, **d}
        self._publish(cfg.topic_env, p)
        # merged legacy JSON for the 3D tracker app
        self._publish("thermohuddle/telemetry", {**p, **{
            "chicks": d.get("chicks", []),
        }})
        try:
            tmp = cfg.json_out.with_suffix(".tmp")
            tmp.write_text(json.dumps({**p, "chicks": d.get("chicks", [])}))
            tmp.replace(cfg.json_out)
        except Exception:
            pass

    def publish_infer(self, d: dict):
        cfg = self.cfg
        self.seq += 1
        self._publish(cfg.topic_infer, {"v": 1, "ts": time.time(),
                                        "boot_id": cfg.boot_id, "seq": self.seq, **d})

    def publish_event(self, kind: str, data: dict):
        cfg = self.cfg
        self.seq += 1
        self._publish(cfg.topic_events,
                      {"v": 1, "ts": time.time(), "boot_id": cfg.boot_id,
                       "seq": self.seq, "kind": kind, "data": data})

    def publish_status(self, state: str):
        cfg = self.cfg
        self.seq += 1
        self._publish(cfg.topic_status,
                      {"v": 1, "ts": time.time(), "boot_id": cfg.boot_id,
                       "seq": self.seq, "state": state}, )


# ============================================================
# PLANT SIMULATOR — no-hardware demo / dev loop (S1 simulate_plant)
# ============================================================
class PlantSim:
    """First-order + dead-time plant: dT/dt = (K·duty − (T − T_amb))/tau."""

    def __init__(self, cfg: Config, t0=26.0, amb=24.0, K=0.09, tau=120.0, dead_s=8.0):
        self.t = t0
        self.amb = amb
        self.K = K
        self.tau = tau
        self.dead_s = dead_s
        self.simtime = 0.0
        self.duty_hist: List[tuple] = []

    def step(self, duty: float, dt: float) -> float:
        # simulated clock so fast test loops behave like real time
        self.duty_hist.append((self.simtime, duty))
        self.simtime += dt
        horizon = self.simtime - self.dead_s
        d_eff = 0.0
        for (t, d) in self.duty_hist:
            if t <= horizon:
                d_eff = d
        # prune history older than the dead-time window
        if len(self.duty_hist) > 64:
            self.duty_hist = [x for x in self.duty_hist if x[0] > horizon]
        # slow exponential approach to equilibrium
        eq = self.amb + self.K * d_eff * 10.0
        self.t += (eq - self.t) * (dt / self.tau)
        return self.t


# ============================================================
# MAIN LOOP
# ============================================================
def run_live(cfg: Config, simulated: bool = False):
    detector = None
    if not simulated:
        if cv2 is None or picam is None:
            raise RuntimeError(
                "Live mode needs OpenCV + capture. Use --simulate for no-hardware dev."
            )
        detector = ChickDetector(cfg)
    stats = SpatialStats(cfg)
    crowd = CrowdingOverride(cfg)
    temporal = TemporalFilter(cfg)
    trim = TrimManager(cfg)
    safety = SafetyRules(cfg)
    pid = PID(cfg)
    telemetry = Telemetry(cfg)
    safety.begin_boot(time.time())

    plant = PlantSim(cfg) if simulated else None
    rng = np.random.default_rng(7)

    # window bookkeeping
    win_pts: List[np.ndarray] = []
    win_deadline = time.time() + cfg.window_s
    confirmed = "COMFY"
    env_period = 10.0
    next_env = time.time()

    print(f"[thermohuddle] {'SIMULATED' if simulated else 'LIVE'} · "
          f"day {cfg.brooding_day} · baseline {baseline_schedule(cfg.brooding_day, cfg):.1f}°C")
    t_next = time.monotonic()
    frame_no = 0
    while True:
        now = time.time()

        # ---- capture & detect (or simulate flock) ----
        if simulated:
            n = int(rng.integers(35, 50))
            mode = rng.integers(0, 4)
            if mode == 0:      # uniform roam
                pts = rng.uniform(-45, 45, (n, 2))
            elif mode == 1:    # cold huddle
                pts = rng.normal(0, 6, (n, 2))
            elif mode == 2:    # hot wall ring
                pts = rng.normal(0, 18, (n, 2))
                pts = np.clip(pts, -46, 46)
            else:              # off-center press (draft-ish)
                pts = rng.normal([28, 28], 8, (n, 2))
            dets = [Detection(p[0], p[1], 0, 0, 0) for p in pts]
        else:
            frame = picam.capture_array()
            dets = detector.detect(frame)
        pts = np.array([[d.x_cm, d.z_cm] for d in dets], dtype=float)

        # ---- features ----
        nnd = stats.nnd_stats(pts)
        feats = {
            "nnd_mean": nnd["mean"],
            "nnd_median": nnd["median"],
            "nnd_cov": nnd["cov"],
            "entropy": stats.occupancy_entropy(pts),
            "centroid": stats.centroid_distance(pts),
            "anisotropy": stats.anisotropy(pts),
            "max_cell": stats.max_cell_fraction(pts),
            "center_occ": stats.center_occupancy(pts),
            "radial": stats.radial_distance(pts),
        }

        # ---- safety first (P0/P1/P2 evaluated every loop) ----
        pv = plant.step(pid.duty, 2.0) if plant else read_floor_temp_stub()
        nh3 = read_nh3_stub() if not simulated else 6.0 + 3 * math.sin(now / 900)
        safe = safety.evaluate(pv, nh3, now)
        if safe["vent"]:
            trim.note_fans(now)
        if simulated:
            pass  # camera loss n/a in sim

        # ---- baseline + trim + PID (P3/P4) ----
        base = baseline_schedule(cfg.brooding_day, cfg)
        new_state = temporal.update(
            stats.classify(feats, cold_floor=(pv < cfg.cold_floor))
        )
        if new_state:
            confirmed = new_state
            telemetry.publish_event("state_change", {"state": confirmed})
        tr = trim.update(confirmed, now)
        sp = base + tr
        if safe["heater_ok"]:
            duty = pid.update(sp, pv)
        else:
            pid.duty = 0.0
            duty = 0.0
            telemetry.publish_event("heater_cutoff", {"pv": pv, "reasons": safe["reasons"]})

        # ---- crowding override (outside the model) ----
        cr = crowd.update(feats["max_cell"], now)
        if cr["fired"]:
            telemetry.publish_event("crowding", cr)

        # ---- telemetry ----
        if now >= next_env:
            next_env += env_period
            telemetry.publish_env({
                "chicks": [[round(p[0], 1), round(p[1], 1)] for p in pts],
                "count": len(pts),
                "floorT": round(pv, 1),
                "setpoint": round(sp, 1),
                "baseline": round(base, 2),
                "trim": round(tr, 2),
                "duty": round(duty, 1),
                "nh3": round(nh3, 1),
                "state": confirmed,
                "crowding": cr["active"],
            })
        frame_no += 1

        # ---- window boundary ----
        if now >= win_deadline:
            win_deadline += cfg.window_s
            # window result already consumed by temporal filter per frame;
            # in the full build this is where th-brain reads inference/window
            pass

        t_next += 1.0 / cfg.fps
        time.sleep(max(0, t_next - time.monotonic()))


def read_floor_temp_stub() -> float:
    """Replace with w1thermsensor DS18B20 read (4-sensor median)."""
    return 32.5


def read_nh3_stub() -> float:
    """Replace with ADS1115 + MQ-137 read (after clean-air baseline)."""
    return 6.0


# ============================================================
# REPLAY MODE — data gathering & threshold tuning on recordings
# ============================================================
def run_replay(cfg: Config, frames_dir: Path):
    if cv2 is None:
        raise RuntimeError("Replay mode needs OpenCV installed")
    detector = ChickDetector(cfg)
    stats = SpatialStats(cfg)
    crowd = CrowdingOverride(cfg)
    temporal = TemporalFilter(cfg)
    out_rows = []
    frames = sorted(frames_dir.glob("*.png")) + sorted(frames_dir.glob("*.jpg"))
    print(f"[replay] {len(frames)} frames in {frames_dir}")
    for i, fp in enumerate(frames):
        img = cv2.imread(str(fp))
        if img is None:
            continue
        dets = detector.detect(img)
        pts = np.array([[d.x_cm, d.z_cm] for d in dets], dtype=float)
        nnd = stats.nnd_stats(pts)
        feats = {
            "nnd_mean": nnd["mean"], "nnd_median": nnd["median"], "nnd_cov": nnd["cov"],
            "entropy": stats.occupancy_entropy(pts),
            "centroid": stats.centroid_distance(pts),
            "anisotropy": stats.anisotropy(pts),
            "max_cell": stats.max_cell_fraction(pts),
            "center_occ": stats.center_occupancy(pts),
            "radial": stats.radial_distance(pts),
        }
        cold_floor = read_floor_temp_stub() < cfg.cold_floor
        raw = stats.classify(feats, cold_floor)
        win = temporal.update(raw)
        if win:
            confirmed = win
        else:
            confirmed = None
        cr = crowd.update(feats["max_cell"], time.time())
        out_rows.append({
            "frame": i, "file": fp.name, "count": len(dets),
            "nnd": round(nnd["mean"], 2), "entropy": round(feats["entropy"], 3),
            "centroid_dist": round(feats["centroid"], 1),
            "anisotropy": round(feats["anisotropy"], 2),
            "max_cell": round(feats["max_cell"], 2),
            "raw_state": raw,
            "confirmed_state": confirmed,
            "crowding": cr["active"],
        })
        print(f"  {fp.name}: {len(dets)} chicks, NND {nnd['mean']:.1f} cm, "
              f"H {feats['entropy']:.2f} → {raw}"
              + (f" | CROWDING {'ACTIVE' if cr['active'] else 'streak '+str(cr['streak'])}"
                 if cr["streak"] else ""))
    outp = frames_dir / "replay_results.json"
    outp.write_text(json.dumps(out_rows, indent=2))
    print(f"[replay] results → {outp}")


# ============================================================
def main():
    ap = argparse.ArgumentParser(description="ThermoHuddle edge pipeline (draft v0.2)")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fps", type=float, default=0.2)
    ap.add_argument("--day", type=int, default=1, help="brooding day (baseline schedule)")
    ap.add_argument("--replay", type=str, help="directory of saved frames to replay")
    ap.add_argument("--simulate", action="store_true", help="no-hardware demo mode")
    ap.add_argument("--out", type=str, default="tracking_latest.json")
    args = ap.parse_args()

    cfg = Config(
        camera_index=args.camera, width=args.width, height=args.height,
        fps=args.fps, brooding_day=args.day, json_out=Path(args.out),
        boot_id=make_boot_id(),
    )
    if args.replay:
        run_replay(cfg, Path(args.replay))
    elif args.simulate:
        run_live(cfg, simulated=True)
    else:
        run_live(cfg)


if __name__ == "__main__":
    main()
