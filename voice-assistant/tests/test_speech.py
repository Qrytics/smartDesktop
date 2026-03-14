"""
Tests for the SpeechRecognizer CUDA-fallback logic.
These tests mock Faster-Whisper and PyAudio so they run without hardware.
"""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# ------------------------------------------------------------------
# Stub hardware/ML dependencies before importing project code
# ------------------------------------------------------------------

def _stub_module(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


# PyAudio stub
pa_mod = _stub_module("pyaudio")
pa_mod.paInt16 = 8
pa_mod.PyAudio = MagicMock()

# Faster-Whisper stub — we replace WhisperModel per-test via patch
fw_mod = _stub_module("faster_whisper")
fw_mod.WhisperModel = MagicMock()

# numpy is real — keep it

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from speech import SpeechRecognizer  # noqa: E402 (import after stubs)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_segment(text: str):
    seg = MagicMock()
    seg.text = text
    return seg


def _make_info(language: str = "en", language_probability: float = 0.99):
    info = MagicMock()
    info.language = language
    info.language_probability = language_probability
    return info


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestIsCudaError(unittest.TestCase):
    """Unit tests for the _is_cuda_error static method."""

    def test_cublas_dll_missing(self):
        exc = RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
        self.assertTrue(SpeechRecognizer._is_cuda_error(exc))

    def test_cudnn_missing(self):
        exc = RuntimeError("Library cudnn64_8.dll is not found or cannot be loaded")
        self.assertTrue(SpeechRecognizer._is_cuda_error(exc))

    def test_cuda_generic(self):
        exc = RuntimeError("CUDA error: no kernel image is available")
        self.assertTrue(SpeechRecognizer._is_cuda_error(exc))

    def test_cannot_be_loaded(self):
        exc = OSError("libcublas.so.12: cannot be loaded")
        self.assertTrue(SpeechRecognizer._is_cuda_error(exc))

    def test_not_cuda_error(self):
        exc = ValueError("invalid audio input")
        self.assertFalse(SpeechRecognizer._is_cuda_error(exc))

    def test_unrelated_runtime_error(self):
        exc = RuntimeError("out of memory")
        self.assertFalse(SpeechRecognizer._is_cuda_error(exc))


class TestTranscribeCudaFallback(unittest.TestCase):
    """_transcribe falls back to CPU when CUDA library is missing during inference."""

    def setUp(self):
        # speech/__init__.py uses `from faster_whisper import WhisperModel`, so
        # we must patch the name in the speech module's namespace.
        with patch("speech.WhisperModel") as mock_wm_cls:
            self.mock_model = MagicMock()
            mock_wm_cls.return_value = self.mock_model
            self.recognizer = SpeechRecognizer(model_size="base", device="auto")

    def test_fallback_reloads_on_cpu_and_returns_transcript(self):
        import numpy as np

        audio = np.zeros(16000, dtype=np.float32)

        cuda_exc = RuntimeError(
            "Library cublas64_12.dll is not found or cannot be loaded"
        )

        # Build an iterator that raises the CUDA error when iterated
        def _bad_iter():
            raise cuda_exc
            yield  # pragma: no cover — makes this a generator function

        info = _make_info()
        ok_segments = [_make_segment(" open chrome")]

        # First call returns a broken iterator; second (CPU retry) is never used
        # on self.mock_model because _reload_on_cpu replaces self._model.
        self.mock_model.transcribe.return_value = (_bad_iter(), info)

        cpu_model = MagicMock()
        cpu_model.transcribe.return_value = (iter(ok_segments), info)

        with patch("speech.WhisperModel", return_value=cpu_model) as mock_wm:
            result = self.recognizer._transcribe(audio)

        # Fallback model loaded on cpu
        mock_wm.assert_called_once_with("base", device="cpu", compute_type="int8")
        # CPU model was asked to transcribe
        cpu_model.transcribe.assert_called_once()
        # Transcript returned correctly (stripped and lowercased)
        self.assertEqual(result, "open chrome")

    def test_non_cuda_error_returns_none_without_reload(self):
        import numpy as np

        audio = np.zeros(16000, dtype=np.float32)

        unrelated_exc = ValueError("some unrelated error")

        def _bad_iter():
            raise unrelated_exc
            yield  # pragma: no cover

        info = _make_info()
        self.mock_model.transcribe.return_value = (_bad_iter(), info)

        with patch("speech.WhisperModel") as mock_wm:
            result = self.recognizer._transcribe(audio)

        # No new model should have been loaded
        mock_wm.assert_not_called()
        self.assertIsNone(result)

    def test_successful_transcription_no_fallback(self):
        import numpy as np

        audio = np.zeros(16000, dtype=np.float32)

        info = _make_info()
        segments = [_make_segment(" hello world ")]
        self.mock_model.transcribe.return_value = (iter(segments), info)

        with patch("speech.WhisperModel") as mock_wm:
            result = self.recognizer._transcribe(audio)

        mock_wm.assert_not_called()
        self.assertEqual(result, "hello world")


class TestInitCudaFallback(unittest.TestCase):
    """SpeechRecognizer.__init__ falls back to CPU when model load itself fails."""

    def test_init_falls_back_to_cpu_on_cuda_load_error(self):
        cuda_exc = RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
        cpu_model = MagicMock()

        with patch(
            "speech.WhisperModel",
            side_effect=[cuda_exc, cpu_model],
        ) as mock_wm:
            recognizer = SpeechRecognizer(model_size="base", device="cuda")

        self.assertEqual(mock_wm.call_count, 2)
        # Second call must be CPU
        self.assertEqual(mock_wm.call_args_list[1], call("base", device="cpu", compute_type="int8"))
        self.assertIs(recognizer._model, cpu_model)

    def test_init_does_not_swallow_non_cuda_errors(self):
        non_cuda_exc = FileNotFoundError("model weights not found")

        with patch("speech.WhisperModel", side_effect=non_cuda_exc):
            with self.assertRaises(FileNotFoundError):
                SpeechRecognizer(model_size="base", device="cuda")

    def test_init_does_not_fall_back_when_device_is_already_cpu(self):
        """If device='cpu' and loading fails, re-raise instead of infinite loop."""
        cuda_exc = RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")

        with patch("speech.WhisperModel", side_effect=cuda_exc):
            with self.assertRaises(RuntimeError):
                SpeechRecognizer(model_size="base", device="cpu")


if __name__ == "__main__":
    unittest.main(verbosity=2)
