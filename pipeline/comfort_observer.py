"""Observation-only flock assessment. No actuator calls or fabricated sensors.

shortcut: thresholds are uncalibrated hypotheses; replace with labeled brooder
validation before treating any candidate as confirmed thermal comfort.
"""
from collections import Counter, deque
import math
import statistics


class ComfortObserver:
    def __init__(self, window_s=60):
        if not math.isfinite(window_s) or window_s <= 0:
            raise ValueError('invalid window duration')
        self.window_s = window_s
        self.start = None
        self.last = None
        self.rows = []
        self.history = deque(maxlen=5)
        self.crowd_streak = 0
        self.candidate = 'UNKNOWN'

    def update(self, points, audio, *, now):
        if not isinstance(now, (int, float)) or not math.isfinite(now):
            raise ValueError('invalid observation timestamp')
        invalid_points = (not isinstance(points, (list, tuple)) or len(points) > 1000
                          or any(not isinstance(p, (list, tuple)) or len(p) != 2
                                 or any(not isinstance(v, (int, float)) or not math.isfinite(v)
                                        or abs(v) > 50 for v in p) for p in points))
        if invalid_points:
            points = []
        enough = len(points) >= 3
        result = {'state': 'UNKNOWN', 'candidate': 'UNKNOWN',
                  'pattern': 'INSUFFICIENT' if points or invalid_points else 'NO_DETECTIONS',
                  'status': 'uncalibrated', 'control_allowed': False,
                  'reason': 'Need at least three detections and calibrated brooder geometry.',
                  'window_s': self.window_s, 'samples': 0,
                  'audio_support': 'unavailable'}
        if audio and audio.get('available') and 0 <= now - audio.get('ts', -1e10) <= 15:
            result['audio_support'] = {'Healthy': 'healthy_vocalization',
                                       'Noise': 'noise',
                                       'Unhealthy': 'abnormal_vocalization'}.get(
                                           audio.get('label'), 'unavailable')
        if not enough:
            self.start, self.rows, self.candidate = None, [], 'UNKNOWN'
            self.history.clear()
            self.crowd_streak = 0
            self.last = now
            return result
        cells = Counter((min(3, max(0, int((x + 50) / 25))),
                         min(3, max(0, int((y + 50) / 25)))) for x, y in points)
        max_cell = max(cells.values()) / len(points)
        import numpy as np
        p = np.asarray(points, dtype=float)
        distance2 = ((p[:, None, :] - p[None, :, :]) ** 2).sum(-1)
        np.fill_diagonal(distance2, np.inf)
        nnd = float(np.sqrt(distance2.min(axis=1)).mean())
        centroid = float(np.hypot(*p.mean(axis=0)))
        radius = np.hypot(p[:, 0], p[:, 1])
        entropy = -sum((v / len(points)) * math.log2(v / len(points))
                       for v in cells.values()) / min(4, math.log2(len(points)))
        clustered = max_cell >= .45 or (nnd < 5 and centroid < 15 and radius.mean() < 20)
        if clustered:
            pattern, raw_candidate = 'CLUSTERED', 'POSSIBLE_COLD'
        elif centroid > 20 and entropy < .8:
            pattern, raw_candidate = 'ASYMMETRIC', 'POSSIBLE_DRAFT'
        elif float((radius > 40).mean()) >= .75:
            pattern, raw_candidate = 'DISPERSED', 'POSSIBLE_HOT'
        elif entropy >= .75 and centroid < 15:
            pattern, raw_candidate = 'EVEN', 'COMFY_CANDIDATE'
        else:
            pattern, raw_candidate = 'INSUFFICIENT', 'UNKNOWN'
        result['pattern'] = pattern
        if self.last is not None and (now <= self.last or now - self.last > 30):
            self.start, self.rows, self.candidate = None, [], 'UNKNOWN'
            self.history.clear()
            self.crowd_streak = 0
        self.last = now
        if self.start is None:
            self.start = now
        self.rows.append({'max_cell': max_cell, 'candidate': raw_candidate})
        if now - self.start >= self.window_s:
            # Features aggregate per frame, never count the same chick again by stacking frames.
            if len(self.rows) >= 3:
                crowd = statistics.median(row['max_cell'] for row in self.rows) >= .45
                self.crowd_streak = self.crowd_streak + 1 if crowd else 0
                votes = Counter(row['candidate'] for row in self.rows)
                winner, count = votes.most_common(1)[0]
                self.history.append(winner if count / len(self.rows) >= .8 else 'UNKNOWN')
                self.candidate = 'UNKNOWN'
                if len(self.history) == 5:
                    winner, count = Counter(self.history).most_common(1)[0]
                    if count >= 4:
                        self.candidate = winner
                if self.crowd_streak >= 3:
                    self.candidate = 'CROWDING'
            self.rows = []
            self.start = now
        result.update(candidate=self.candidate, samples=len(self.rows),
                      status='warming_up' if len(self.history) < 3 else 'uncalibrated',
                      reason='Uncalibrated camera geometry; no measured floor temperature. '
                             'Candidates are behavioral hypotheses, not thermal diagnoses.')
        # Report available evidence across completed windows too.
        result['samples'] = max(len(self.rows), len(self.history))
        return result
