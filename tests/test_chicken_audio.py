"""Offline tests; no microphone, MQTT, camera, or running service access."""
import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ConstructorTests(unittest.TestCase):
    def test_missing_checkpoint_returns_unavailable_not_a_prediction(self):
        from pipeline.chicken_audio import ChickenAudioClassifier

        classifier = ChickenAudioClassifier(ROOT / "missing-chicken-checkpoint.pth")
        result = classifier.predict(np.ones(33075, dtype=np.float32), 22050)
        self.assertFalse(result["available"])
        self.assertEqual(result["label"], "Unknown")
        self.assertEqual(result["probabilities"], dict.fromkeys(
            ("Healthy", "Noise", "Unhealthy"), 0.0))
        self.assertEqual(result["model"], "chicken-vocalization-classifier")
        self.assertGreaterEqual(result["inference_ms"], 0.0)
        self.assertIn("checkpoint", result["reason"].lower())


    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch dependency missing")
    def test_rejected_weights_never_retry_unsafe_deserialization(self):
        import pickle
        import torch
        from unittest.mock import patch
        from pipeline.chicken_audio import ChickenAudioClassifier

        checkpoint = ROOT.parent / "Audiomodel/Chicken_CNN_Disease_Detection_Model.pth"
        with patch.object(torch, "load", side_effect=pickle.UnpicklingError("unsafe globals")) as load:
            classifier = ChickenAudioClassifier(checkpoint)
        load.assert_called_once_with(checkpoint, weights_only=True, map_location="cpu")
        result = classifier.predict(np.ones(33075, dtype=np.float32), 22050)
        self.assertFalse(result["available"])
        self.assertIn("UnpicklingError", result["reason"])

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch dependency missing")
    def test_partial_state_dict_is_rejected_instead_of_partially_loaded(self):
        import torch
        from unittest.mock import patch
        from pipeline.chicken_audio import ChickenAudioClassifier

        checkpoint = ROOT.parent / "Audiomodel/Chicken_CNN_Disease_Detection_Model.pth"
        state = torch.load(checkpoint, weights_only=True, map_location="cpu")
        del state["classifier.1.bias"]
        with patch.object(torch, "load", return_value=state):
            classifier = ChickenAudioClassifier(checkpoint)
        self.assertIsNone(classifier._model)
        self.assertIn("Missing key", classifier.reason)

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch dependency missing")
    def test_real_checkpoint_strictly_loads_cpu_eval_architecture(self):
        import torch
        from unittest.mock import patch
        from pipeline.chicken_audio import ChickenAudioClassifier

        checkpoint = ROOT.parent / "Audiomodel/Chicken_CNN_Disease_Detection_Model.pth"
        # Spy on the security boundary, but actually deserialize real weights.
        with patch.object(torch, "load", wraps=torch.load) as load:
            classifier = ChickenAudioClassifier(checkpoint)
        self.assertIsNotNone(classifier._model, classifier.reason)
        load.assert_called_once_with(checkpoint, weights_only=True, map_location="cpu")
        self.assertFalse(classifier._model.training)
        self.assertEqual(next(classifier._model.parameters()).device.type, "cpu")
        self.assertEqual(tuple(classifier._model.classifier[1].weight.shape), (256, 25088))
        self.assertIsInstance(classifier._model.features[1], torch.nn.BatchNorm2d)
        with torch.inference_mode():
            actual = classifier._model(torch.zeros(1, 1, 128, 130))
        self.assertEqual(tuple(actual.shape), (1, 3))


class InputSafetyTests(unittest.TestCase):
    def test_invalid_audio_never_produces_a_confident_prediction(self):
        from pipeline.chicken_audio import ChickenAudioClassifier

        classifier = ChickenAudioClassifier(ROOT / "missing-chicken-checkpoint.pth")
        cases = [
            (np.zeros(33075), 22050, "silence"),
            (np.full(33075, 1e-12), 22050, "silence"),
            (np.ones(33074), 22050, "short"),
            (np.ones(71999), 48000, "short"),
            (np.full(33075, np.nan), 22050, "finite"),
            (np.full(33075, np.inf), 22050, "finite"),
            (np.ones((33075, 2)), 22050, "mono"),
            (np.ones(33075), 0, "sample rate"),
            (np.ones(33075), 22050.5, "sample rate"),
            (np.ones(33075, dtype=complex), 22050, "real"),
            (np.ones(33075, dtype=str), 22050, "real"),
            (np.concatenate((np.ones(33075), np.zeros(33075))), 22050, "silence"),
        ]
        for samples, rate, reason in cases:
            with self.subTest(reason=reason, rate=rate):
                result = classifier.predict(samples, rate)
                self.assertFalse(result["available"])
                self.assertEqual(result["label"], "Unknown")
                self.assertEqual(sum(result["probabilities"].values()), 0.0)
                self.assertIn(reason, result["reason"].lower())


class TrainingTransformTests(unittest.TestCase):
    def test_log_mel_matches_notebook_at_22050_and_native_48000(self):
        from pipeline.chicken_audio import ChickenAudioClassifier

        for rate in (22050, 48000):
            samples = np.random.default_rng(123).normal(0, 0.1, rate * 2).astype(np.float32)
            samples[0] = 2.0  # Distinguishes normalize-before-crop from after.
            try:
                actual = ChickenAudioClassifier._log_mel(samples, rate)
            except ModuleNotFoundError as exc:
                self.skipTest(f"dependency missing: {exc.name}")
            import librosa
            wav = samples
            if rate != 22050:
                wav = librosa.resample(wav, orig_sr=rate, target_sr=22050)
            wav = librosa.util.normalize(wav)[-33075:]
            expected = librosa.power_to_db(librosa.feature.melspectrogram(
                y=wav, sr=22050, n_fft=2048, hop_length=256, n_mels=128), ref=np.max)
            self.assertEqual(actual.shape, (128, 130))
            self.assertEqual(actual.dtype, np.float32)
            np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-5)

    def test_training_normalization_happens_before_latest_window_crop(self):
        from pipeline.chicken_audio import ChickenAudioClassifier

        # The old loud prefix must influence normalization of the quiet tail.
        tail = np.tile(np.array([0.25, -0.25], dtype=np.float32), 16538)[:33075]
        samples = np.concatenate((np.array([2.0], dtype=np.float32), tail))
        actual = ChickenAudioClassifier._prepare_waveform(samples, 22050)
        np.testing.assert_array_equal(actual, tail / 2.0)
        self.assertEqual(actual.dtype, np.float32)

    def test_training_transform_pads_only_after_normalizing(self):
        from pipeline.chicken_audio import ChickenAudioClassifier

        actual = ChickenAudioClassifier._prepare_waveform(
            np.array([0.5, -0.25], dtype=np.float32), 22050)
        self.assertEqual(actual.shape, (33075,))
        np.testing.assert_array_equal(actual[:2], [1.0, -0.5])
        self.assertTrue((actual[2:] == 0).all())


@unittest.skipUnless(importlib.util.find_spec("torch"), "torch dependency missing")
class ConfidenceTests(unittest.TestCase):
    def test_nonfinite_or_wrong_shape_model_outputs_are_unavailable(self):
        import torch
        from unittest.mock import patch
        from pipeline.chicken_audio import ChickenAudioClassifier

        for output, reason in [([[float("nan"), 0.0, 0.0]], "finite"),
                               ([[float("inf"), 0.0, 0.0]], "finite"),
                               ([[0.0, 0.0, 0.0, 0.0]], "shape")]:
            with self.subTest(reason=reason):
                class InvalidOutput(torch.nn.Module):
                    def forward(self, tensor):
                        return torch.tensor(output)
                classifier = ChickenAudioClassifier(ROOT / "missing-chicken-checkpoint.pth")
                classifier._torch = torch
                classifier._model = InvalidOutput()
                classifier.reason = None
                with patch.object(classifier, "_log_mel", return_value=np.zeros(
                        (128, 130), dtype=np.float32)):
                    result = classifier.predict(np.ones(33075, dtype=np.float32), 22050)
                self.assertFalse(result["available"], result)
                self.assertEqual(result["label"], "Unknown")
                self.assertEqual(sum(result["probabilities"].values()), 0.0)
                self.assertIn(reason, result["reason"])

    def test_softmax_class_order_threshold_and_inference_mode(self):
        import torch
        from unittest.mock import patch
        from pipeline.chicken_audio import ChickenAudioClassifier

        samples = np.ones(33075, dtype=np.float32)
        for logits, label in [([5.0, 0.0, 0.0], "Healthy"),
                              ([0.0, 5.0, 0.0], "Noise"),
                              ([0.0, 0.0, 5.0], "Unhealthy"),
                              ([0.0, 0.0, 0.0], "Unknown")]:
            with self.subTest(label=label):
                class FixedLogits(torch.nn.Module):
                    def forward(inner_self, tensor):
                        self.assertFalse(torch.is_grad_enabled())
                        self.assertEqual(tuple(tensor.shape), (1, 1, 128, 130))
                        return torch.tensor([logits])
                classifier = ChickenAudioClassifier(ROOT / "missing-chicken-checkpoint.pth")
                classifier._torch = torch
                classifier._model = FixedLogits().eval()
                classifier.reason = None
                with patch.object(classifier, "_log_mel", return_value=np.zeros(
                        (128, 130), dtype=np.float32)):
                    result = classifier.predict(samples, 22050)
                self.assertTrue(result["available"], result)
                self.assertEqual(result["label"], label)
                self.assertEqual(list(result["probabilities"]), ["Healthy", "Noise", "Unhealthy"])
                expected = torch.softmax(torch.tensor(logits), dim=0).tolist()
                np.testing.assert_allclose(list(result["probabilities"].values()), expected)
                if label == "Unknown":
                    self.assertIn("confidence", result["reason"])


class RealSampleTests(unittest.TestCase):
    def test_real_checkpoint_sample_matches_independent_notebook_transform(self):
        try:
            import librosa
            import soundfile as sf
            import torch
        except ModuleNotFoundError as exc:
            self.skipTest(f"dependency missing: {exc.name}")
        import json
        from pipeline.chicken_audio import ChickenAudioClassifier

        model_dir = ROOT.parent / "Audiomodel"
        classifier = ChickenAudioClassifier(model_dir / "Chicken_CNN_Disease_Detection_Model.pth")
        self.assertIsNotNone(classifier._model, classifier.reason)
        samples, rate = sf.read(model_dir / "audio_test.mp3", dtype="float32")
        if samples.ndim == 2:
            samples = samples.mean(axis=1)
        for live_rate in (22050, 48000):
            audio = samples if live_rate == rate else librosa.resample(
                samples, orig_sr=rate, target_sr=live_rate)
            result = classifier.predict(audio, live_rate)
            self.assertTrue(result["available"], result)
            wav = audio if live_rate == 22050 else librosa.resample(
                audio, orig_sr=live_rate, target_sr=22050)
            wav = librosa.util.normalize(wav)[-33075:]
            mel = librosa.power_to_db(librosa.feature.melspectrogram(
                y=wav, sr=22050, n_fft=2048, hop_length=256, n_mels=128), ref=np.max)
            with torch.inference_mode():
                expected = torch.softmax(classifier._model(
                    torch.from_numpy(mel)[None, None]), dim=1)[0].tolist()
            np.testing.assert_allclose(list(result["probabilities"].values()),
                                       expected, rtol=1e-6, atol=1e-7)
            self.assertAlmostEqual(sum(result["probabilities"].values()), 1.0, places=6)
            winner = int(np.argmax(expected))
            self.assertEqual(result["label"], ("Healthy", "Noise", "Unhealthy")[winner]
                             if expected[winner] >= 0.6 else "Unknown")
            print("REAL_AUDIO_SMOKE " + json.dumps({
                "file": str(model_dir / "audio_test.mp3"),
                "sample_rate": live_rate, "sample_count": len(audio), **result}, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
