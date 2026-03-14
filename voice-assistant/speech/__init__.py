"""
SmartDesktop Voice Assistant - Speech Recognition Module

Uses Faster-Whisper for fast, accurate, fully offline speech-to-text.
Records audio from the microphone after a wake word is detected, then
transcribes it into text for the command parser.
"""

import logging
import queue
import threading
import time
from typing import Optional

import numpy as np
import pyaudio
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Audio recording constants
SAMPLE_RATE = 16000  # Hz — required by Whisper
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024  # frames per buffer


class SpeechRecognizer:
    """
    Records microphone audio and transcribes it using Faster-Whisper.

    Workflow:
        1. Call ``listen()`` — starts recording and returns when silence is detected.
        2. The recorded audio is passed to Faster-Whisper for transcription.
        3. The transcribed text is returned as a lowercase, stripped string.
    """

    def __init__(
        self,
        model_size: str = "base",
        language: Optional[str] = "en",
        device: str = "auto",
        compute_type: str = "int8",
        max_record_seconds: float = 10.0,
        silence_threshold: int = 500,
        silence_duration: float = 1.5,
    ):
        """
        Initialize the speech recognizer.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large).
            language: Language code for transcription (None = auto-detect).
            device: Inference device ("cpu", "cuda", or "auto").
            compute_type: Quantization type ("int8", "float16", "float32").
            max_record_seconds: Maximum recording duration in seconds.
            silence_threshold: RMS energy level below which audio is considered silent.
            silence_duration: Seconds of continuous silence that ends recording.
        """
        self.language = language
        self.max_record_seconds = max_record_seconds
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self._model_size = model_size
        self._compute_type = compute_type

        logger.info(
            "Loading Faster-Whisper model '%s' on device '%s' (%s)...",
            model_size,
            device,
            compute_type,
        )
        try:
            self._model = WhisperModel(
                model_size, device=device, compute_type=compute_type
            )
        except Exception as exc:
            if device != "cpu" and self._is_cuda_error(exc):
                logger.warning(
                    "Failed to load model on device '%s' (%s); falling back to CPU. Error: %s",
                    device,
                    compute_type,
                    exc,
                )
                self._model = WhisperModel(
                    model_size, device="cpu", compute_type=compute_type
                )
            else:
                raise
        logger.info("Faster-Whisper model loaded.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def listen(self) -> Optional[str]:
        """
        Record a command from the microphone and return its transcription.

        Recording stops when:
        - The silence threshold is exceeded for ``silence_duration`` seconds, OR
        - ``max_record_seconds`` have elapsed.

        Returns:
            Transcribed text (lowercase, stripped), or None if nothing was heard.
        """
        audio_data = self._record()
        if audio_data is None or len(audio_data) == 0:
            return None
        return self._transcribe(audio_data)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _record(self) -> Optional[np.ndarray]:
        """
        Capture microphone audio until silence or timeout.

        Returns:
            Numpy float32 array of audio samples normalised to [-1, 1],
            or None if the stream could not be opened.
        """
        pa = pyaudio.PyAudio()
        try:
            stream = pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
        except OSError as exc:
            logger.error("Failed to open microphone stream: %s", exc)
            pa.terminate()
            return None

        logger.info("Recording... (speak your command)")
        frames = []
        silent_chunks = 0
        max_chunks = int(SAMPLE_RATE / CHUNK_SIZE * self.max_record_seconds)
        silence_chunks_needed = int(
            SAMPLE_RATE / CHUNK_SIZE * self.silence_duration
        )

        try:
            for _ in range(max_chunks):
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)
                rms = self._rms(data)
                if rms < self.silence_threshold:
                    silent_chunks += 1
                else:
                    silent_chunks = 0
                if silent_chunks >= silence_chunks_needed:
                    logger.debug("Silence detected — stopping recording.")
                    break
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

        if not frames:
            return None

        raw = b"".join(frames)
        audio_np = (
            np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        )
        return audio_np

    def _transcribe(self, audio: np.ndarray) -> Optional[str]:
        """
        Run Faster-Whisper inference on the recorded audio.

        Args:
            audio: Float32 numpy array of audio samples.

        Returns:
            Transcribed text or None if no speech was detected.
        """
        logger.info("Transcribing audio...")
        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
        )

        try:
            text_parts = [segment.text for segment in segments]
        except Exception as exc:
            if self._is_cuda_error(exc):
                logger.warning(
                    "Transcription failed due to missing CUDA library (%s). "
                    "Reloading model on CPU and retrying...",
                    exc,
                )
                self._reload_on_cpu()
                segments, info = self._model.transcribe(
                    audio,
                    language=self.language,
                    beam_size=5,
                )
                try:
                    text_parts = [segment.text for segment in segments]
                except Exception as retry_exc:
                    logger.error(
                        "Transcription failed on CPU fallback: %s",
                        retry_exc,
                        exc_info=True,
                    )
                    return None
            else:
                logger.error(
                    "Transcription failed during segment iteration: %s",
                    exc,
                    exc_info=True,
                )
                return None

        logger.debug(
            "Detected language '%s' with probability %.2f",
            info.language,
            info.language_probability,
        )

        if not text_parts:
            logger.warning("No speech detected in audio.")
            return None

        transcript = " ".join(text_parts).strip().lower()
        logger.info("Transcription: '%s'", transcript)
        return transcript

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reload_on_cpu(self) -> None:
        """Reinitialise the Whisper model on CPU (int8) as a safe fallback."""
        logger.info(
            "Loading Faster-Whisper model '%s' on device 'cpu' (%s)...",
            self._model_size,
            self._compute_type,
        )
        self._model = WhisperModel(
            self._model_size, device="cpu", compute_type=self._compute_type
        )
        logger.info("Faster-Whisper model reloaded on CPU.")

    @staticmethod
    def _is_cuda_error(exc: Exception) -> bool:
        """Return True when *exc* indicates a missing or broken CUDA/GPU library."""
        msg = str(exc).lower()
        cuda_keywords = ("cublas", "cudnn", "cuda", "cannot be loaded")
        return any(kw in msg for kw in cuda_keywords)

    @staticmethod
    def _rms(data: bytes) -> float:
        """Compute the root-mean-square energy of a raw PCM audio chunk."""
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(samples))))
