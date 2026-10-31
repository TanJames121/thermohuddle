"""Offline adapter for the three-class chicken vocalization checkpoint.

This is not a thermal-distress detector and does not control live equipment.
"""
from pathlib import Path
from time import perf_counter

import numpy as np


CLASSES = ("Healthy", "Noise", "Unhealthy")
MODEL_NAME = "chicken-vocalization-classifier"


class ChickenAudioClassifier:
    """CPU-only inference, returning Unknown when the model/input is unavailable."""

    def __init__(self, checkpoint):
        self.checkpoint = Path(checkpoint)
        self._model = None
        self.reason = "checkpoint not found: " + str(self.checkpoint)
        if not self.checkpoint.is_file():
            return
        try:
            import torch
            self._torch = torch
            model = self._build_model(torch)
            state = torch.load(self.checkpoint, weights_only=True, map_location="cpu")
            model.load_state_dict(state, strict=True)
            model.eval()
            self._model = model
            self.reason = None
        except Exception as exc:
            # Never retry unsafe pickle loading or permit a partial state dict.
            self.reason = f"checkpoint unavailable: {type(exc).__name__}: {exc}"

    @staticmethod
    def _build_model(torch):
        from collections import OrderedDict
        nn = torch.nn
        return nn.Sequential(OrderedDict([
            ("features", nn.Sequential(
                nn.Conv2d(1, 32, kernel_size=3), nn.BatchNorm2d(32),
                nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(32, 64, kernel_size=3), nn.BatchNorm2d(64),
                nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(64, 128, kernel_size=3), nn.BatchNorm2d(128),
                nn.ReLU(), nn.MaxPool2d(2),
            )),
            ("classifier", nn.Sequential(
                nn.Flatten(), nn.Linear(25088, 256), nn.Dropout(0.5),
                nn.ReLU(), nn.Linear(256, 3),
            )),
        ]))

    def predict(self, samples: np.ndarray, sample_rate: int) -> dict:
        """Classify mono PCM; invalid/short/silent buffers are never inferred."""
        started = perf_counter()
        reason = self._input_reason(samples, sample_rate)
        result = {
            "label": "Unknown",
            "probabilities": dict.fromkeys(CLASSES, 0.0),
            "available": False,
            "model": MODEL_NAME,
            "inference_ms": 0.0,
        }
        if reason is None and self._model is None:
            reason = self.reason
        if reason is None:
            try:
                torch = self._torch
                mel = self._log_mel(samples, sample_rate)
                tensor = torch.from_numpy(mel)[None, None]
                with torch.inference_mode():
                    logits = self._model(tensor)
                    if tuple(logits.shape) != (1, 3):
                        raise ValueError("unexpected model output shape; expected (1, 3)")
                    if not torch.isfinite(logits).all().item():
                        raise ValueError("model output must be finite")
                    probabilities = torch.softmax(logits, dim=1)[0].tolist()
                result["probabilities"] = dict(zip(CLASSES, map(float, probabilities)))
                result["available"] = True
                winner = int(np.argmax(probabilities))
                if probabilities[winner] >= 0.6:
                    result["label"] = CLASSES[winner]
                else:
                    reason = "low confidence: maximum class probability below 0.6"
            except Exception as exc:
                reason = f"inference unavailable: {type(exc).__name__}: {exc}"
        if reason is not None:
            result["reason"] = reason
        result["inference_ms"] = (perf_counter() - started) * 1000.0
        return result

    @staticmethod
    def _log_mel(samples, sample_rate):
        import librosa
        wav = ChickenAudioClassifier._prepare_waveform(samples, sample_rate)
        mel = librosa.feature.melspectrogram(
            y=wav, sr=22050, n_fft=2048, hop_length=256, n_mels=128)
        return np.ascontiguousarray(librosa.power_to_db(mel, ref=np.max), dtype=np.float32)

    @staticmethod
    def _prepare_waveform(samples, sample_rate):
        """Resample, infinity-normalize the WHOLE buffer, then keep latest 1.5s.

        Infinity normalization is numerically equivalent to the notebook's
        librosa.util.normalize(wav); only the crop direction differs for live
        buffers. Padding is retained for parity tests; predict rejects short PCM.
        """
        wav = np.asarray(samples, dtype=np.float32)
        if sample_rate != 22050:
            import librosa
            wav = librosa.resample(wav, orig_sr=sample_rate, target_sr=22050)
        peak = np.max(np.abs(wav).astype(np.float64), initial=0.0)
        if peak >= np.finfo(wav.dtype).tiny:
            wav = (wav / peak).astype(np.float32)
        if len(wav) > 33075:
            wav = wav[-33075:]
        else:
            wav = np.pad(wav, (0, 33075 - len(wav)))
        return np.ascontiguousarray(wav, dtype=np.float32)

    @staticmethod
    def _input_reason(samples, sample_rate):
        if (isinstance(sample_rate, (bool, np.bool_))
                or not isinstance(sample_rate, (int, np.integer))
                or sample_rate <= 0):
            return "sample rate must be a positive integer"
        if not isinstance(samples, np.ndarray) or samples.ndim != 1:
            return "samples must be a one-dimensional mono numpy array"
        if samples.dtype.kind not in "fiu":
            return "samples must contain real numeric PCM"
        if not np.isfinite(samples).all():
            return "samples must be finite"
        if len(samples) * 2 < sample_rate * 3:
            return "input is too short: need a complete 1.5-second window"
        window = samples[-((sample_rate * 3 + 1) // 2):].astype(np.float64)
        if np.max(np.abs(window)) <= 1e-8:
            return "silence in latest 1.5-second window"
        return None
