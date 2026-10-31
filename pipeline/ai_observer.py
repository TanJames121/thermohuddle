"""ThermoHuddle model observation packets. No fabricated thermal measurements."""


def assemble_packet(vision, audio, assessment, *, now, seq, boot_id, cam_ok):
    return {'v': 'ai-observer-1', 'boot_id': boot_id, 'seq': seq, 'ts': now,
            'cam_ok': bool(cam_ok),
            'count': vision['count'] if cam_ok else 0,
            'chicks': vision['chicks'] if cam_ok else [],
            'vision': vision.get('vision', {}),
            'audio': audio or {'label': 'Unknown', 'available': False,
                               'model': 'chicken-vocalization-classifier'},
            'assessment': assessment}


def main():
    import argparse

    import fcntl
    import json
    import logging
    import math
    import os
    from pathlib import Path
    import signal
    import sys
    import threading
    import time
    import uuid
    import numpy as np
    import cv2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames', type=int, default=0, help='0: run continuously')
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--output', type=Path, default=Path.home() / 'Thesis/tracking_latest.json')
    parser.add_argument('--evidence', type=Path, default=Path.home() / 'Thesis/ai_observation')
    parser.add_argument('--audio-device', default='snd_rpi_googlevoicehat_soundcar')
    parser.add_argument('--no-mqtt', action='store_true')
    args = parser.parse_args()
    if args.frames < 0 or args.interval < .5 or not math.isfinite(args.interval):
        parser.error('invalid frame limit/interval')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.mkdir(parents=True, exist_ok=True)
    lock = (Path.home() / 'Thesis/ai_observer.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    # Reuse hardware capture and telemetry only. Never instantiate old sensor/PID/control stubs.
    sys.path.insert(0, str(Path.home() / 'Thesis'))
    from thermohuddle_v3 import Config, CameraSource, AudioMonitor, Telemetry
    from chicken_vision import ChickenVision
    from chicken_audio import ChickenAudioClassifier
    from comfort_observer import ComfortObserver

    class RawMicrophone(AudioMonitor):
        def __init__(self, cfg):
            self.capture_bad = False
            self.capture_ts = 0
            super().__init__(cfg)

        def _cb(self, indata, frames, time_info, status):
            super()._cb(indata, frames, time_info, status)
            with self._lock:
                if status:
                    self.capture_bad = True
                self.capture_ts = time.time()

        def samples(self):
            with self._lock:
                if not self._blocks:
                    return None, self.capture_ts
                x = np.concatenate(self._blocks)
                self._blocks.clear()
                self._n = 0
                bad, timestamp = self.capture_bad, self.capture_ts
                self.capture_bad = False
            if bad or time.time() - timestamp > 5:
                return None, timestamp
            return x[-int(self.cfg.audio_window_s * self.rate):], timestamp

    cfg = Config(audio_rate=48000, audio_device=args.audio_device, json_out=args.output,
                 boot_id=uuid.uuid4().hex[:12])
    telemetry = None if args.no_mqtt else Telemetry(cfg)
    vision = ChickenVision(Path.home() / 'CameraModel/best.pt')
    audio_model = ChickenAudioClassifier(Path.home() / 'Audiomodel/Chicken_CNN_Disease_Detection_Model.pth')
    camera, microphone = CameraSource(cfg), RawMicrophone(cfg)
    observer = ComfortObserver()
    stopping = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())
    logging.info('Observation-only AI started; camera backend=%s mic=%s; no actuator topics',
                 camera.kind, microphone.ok)
    frames = 0
    try:
        # Give live input one complete classifier window; never pad missing live sound into a diagnosis.
        stopping.wait(1.6)
        while not stopping.is_set() and (not args.frames or frames < args.frames):
            cycle = time.monotonic()
            captured_at = time.time()
            frame = camera.read()
            detection = {'count': 0, 'chicks': [], 'vision': {'model': 'PoultryVision-YOLOv11m',
                          'calibrated': False, 'coordinate_system': 'uncalibrated_camera'}}
            cam_ok = frame is not None
            if cam_ok:
                try:
                    detection = vision.predict(frame)
                except Exception:
                    logging.exception('Camera inference failed; discarding detections')
                    cam_ok = False
            raw, audio_ts = microphone.samples()
            audio = {'label': 'Unknown', 'available': False, 'model': 'chicken-vocalization-classifier',
                     'ts': audio_ts}
            if raw is not None and len(raw) >= int(1.5 * microphone.rate):
                try:
                    audio.update(audio_model.predict(raw, microphone.rate))
                    if np.isfinite(raw).all():
                        audio['level_db'] = round(20 * math.log10(float(np.sqrt(np.mean(raw ** 2))) + 1e-10), 1)
                        spectrum = abs(np.fft.rfft(raw * np.hanning(len(raw)))) ** 2
                        freqs = np.fft.rfftfreq(len(raw), 1 / microphone.rate)
                        relevant = freqs >= 300
                        if relevant.any():
                            audio['peak_hz'] = round(float(freqs[relevant][np.argmax(spectrum[relevant])]), 1)
                            total = float(spectrum[relevant].sum())
                            audio['distress_ratio'] = round(float(spectrum[(freqs >= 2000) & (freqs <= 5000)].sum()) / (total + 1e-20), 4)
                except Exception:
                    logging.exception('Audio inference failed; label remains Unknown')
            assessment = observer.update(detection['chicks'] if cam_ok else [], audio, now=time.time())
            packet = assemble_packet(detection, audio, assessment, now=captured_at,
                                     seq=frames + 1, boot_id=cfg.boot_id, cam_ok=cam_ok)
            packet_tmp = args.output.with_suffix(args.output.suffix + '.partial')
            packet_tmp.write_text(json.dumps(packet, allow_nan=False) + '\n')
            os.replace(packet_tmp, args.output)
            if telemetry is not None:
                telemetry._publish('thermohuddle/inference/window', packet)
                if audio.get('available'):
                    telemetry._publish('thermohuddle/telemetry/audio', audio)
            # Local evidence only, with no image publication or fabricated readings.
            if frame is not None:
                annotated = frame.copy()
                for x1, y1, x2, y2, confidence, cls in detection.get('boxes', []):
                    cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    cv2.putText(annotated, f'chicken {confidence:.2f}', (int(x1), max(15, int(y1))),
                                cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 0), 1)
                image_tmp = args.evidence / 'frame_latest.partial.jpg'
                if not cv2.imwrite(str(image_tmp), annotated):
                    logging.warning('Could not save local camera evidence')
                else:
                    os.replace(image_tmp, args.evidence / 'frame_latest.jpg')
            with (args.evidence / 'observations.jsonl').open('a') as journal:
                journal.write(json.dumps(packet, allow_nan=False) + '\n')
            logging.info('seq=%d camera=%s chicken_detections=%d vision_ms=%s audio=%s probs=%s assessment=%s/%s',
                         frames + 1, cam_ok, packet['count'], packet['vision'].get('inference_ms'),
                         audio['label'], audio.get('probabilities'), assessment['state'], assessment['candidate'])
            frames += 1
            if args.frames and frames >= args.frames:
                break
            stopping.wait(max(0, args.interval - (time.monotonic() - cycle)))
    finally:
        camera.close()
        microphone.close()
        if telemetry is not None and telemetry.client:
            telemetry.client.loop_stop()
            telemetry.client.disconnect()
        lock.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
