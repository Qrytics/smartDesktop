"""
SmartDesktop Voice Assistant - Wake Word Detection Module

Uses Porcupine (by Picovoice) for efficient, always-on wake word detection.
Porcupine runs entirely on-device with very low CPU usage.
"""

import logging
import struct
import threading
from typing import Callable, List, Optional

import pyaudio
import pvporcupine

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """
    Listens continuously for a wake word using Picovoice Porcupine.

    Porcupine processes audio in small frames and detects the wake word
    with extremely low CPU overhead, making it suitable for always-on use.
    """

    def __init__(
        self,
        access_key: str,
        keywords: List[str],
        sensitivity: float = 0.5,
        on_detected: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the wake word detector.

        Args:
            access_key: Picovoice console access key.
            keywords: List of wake word keywords (e.g. ["jarvis", "computer"]).
            sensitivity: Detection sensitivity (0.0–1.0). Higher = more sensitive.
            on_detected: Callback invoked with the detected keyword when triggered.
        """
        self.access_key = access_key
        self.keywords = keywords
        self.sensitivity = sensitivity
        self.on_detected = on_detected

        self._porcupine: Optional[pvporcupine.Porcupine] = None
        self._audio_stream: Optional[pyaudio.Stream] = None
        self._pa: Optional[pyaudio.PyAudio] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _initialize_porcupine(self) -> None:
        """Create the Porcupine instance with requested keywords."""
        sensitivities = [self.sensitivity] * len(self.keywords)
        self._porcupine = pvporcupine.create(
            access_key=self.access_key,
            keywords=self.keywords,
            sensitivities=sensitivities,
        )
        logger.info(
            "Porcupine initialized | keywords=%s | sensitivity=%.2f",
            self.keywords,
            self.sensitivity,
        )

    def _open_audio_stream(self) -> None:
        """Open the PyAudio microphone stream matching Porcupine's requirements."""
        self._pa = pyaudio.PyAudio()
        self._audio_stream = self._pa.open(
            rate=self._porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self._porcupine.frame_length,
        )
        logger.debug(
            "Audio stream opened | sample_rate=%d | frame_length=%d",
            self._porcupine.sample_rate,
            self._porcupine.frame_length,
        )

    def _detection_loop(self) -> None:
        """Main audio-processing loop — runs on a background thread."""
        logger.info("Wake word detection loop started, listening...")
        while self._running:
            try:
                pcm = self._audio_stream.read(
                    self._porcupine.frame_length, exception_on_overflow=False
                )
                pcm = struct.unpack_from(
                    "h" * self._porcupine.frame_length, pcm
                )
                result = self._porcupine.process(pcm)
                if result >= 0:
                    detected_keyword = self.keywords[result]
                    logger.info("Wake word detected: '%s'", detected_keyword)
                    if self.on_detected:
                        try:
                            self.on_detected(detected_keyword)
                        except Exception as exc:
                            logger.error(
                                "Error in wake word callback for '%s': %s",
                                detected_keyword,
                                exc,
                                exc_info=True,
                            )
            except OSError as exc:
                if self._running:
                    logger.error("Audio read error: %s", exc)

    def start(self) -> None:
        """Start the background wake word detection thread."""
        if self._running:
            logger.warning("WakeWordDetector is already running.")
            return

        self._initialize_porcupine()
        self._open_audio_stream()
        self._running = True
        self._thread = threading.Thread(
            target=self._detection_loop, daemon=True, name="WakeWordThread"
        )
        self._thread.start()
        logger.info("WakeWordDetector started.")

    def stop(self) -> None:
        """Stop the detection thread and release audio/Porcupine resources."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

        if self._audio_stream is not None:
            self._audio_stream.close()
            self._audio_stream = None
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None
        if self._porcupine is not None:
            self._porcupine.delete()
            self._porcupine = None

        logger.info("WakeWordDetector stopped and resources released.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()
