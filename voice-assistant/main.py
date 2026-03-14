"""
SmartDesktop Voice Assistant - Main Entry Point

Orchestrates:
  1. Configuration loading
  2. Wake word detection (Porcupine)
  3. Speech recognition (Faster-Whisper)
  4. Command parsing & execution

Architecture:
    Microphone → Wake Word Engine (Porcupine)
                      │
                      ▼
              Speech Recognition (Faster-Whisper)
                      │
                      ▼
              Command Parser
                      │
                      ▼
              Action Executor
              ┌────────────────┬──────────────┬──────────────┐
              │  OS automation │  open apps   │  terminal    │
              └────────────────┴──────────────┴──────────────┘

Usage:
    python main.py [--config path/to/config.yaml]
"""

import argparse
import logging
import os
import sys
import threading
import time
from pathlib import Path

import yaml
from colorama import Fore, Style, init as colorama_init

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

colorama_init(autoreset=True)

_DEFAULT_CONFIG = Path(__file__).parent / "config.yaml"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SmartDesktop — local voice automation assistant"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_DEFAULT_CONFIG,
        help="Path to config.yaml (default: ./config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override log level from config.",
    )
    parser.add_argument(
        "--list-commands",
        action="store_true",
        help="Print all registered commands and exit.",
    )
    return parser.parse_args()


def _setup_logging(config: dict, override_level: str = None) -> None:
    log_cfg = config.get("logging", {})
    level_name = override_level or log_cfg.get("level", "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)
    log_file = log_cfg.get("file")

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        print(
            f"{Fore.RED}Config file not found: {config_path}{Style.RESET_ALL}"
        )
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# ---------------------------------------------------------------------------
# Assistant orchestration
# ---------------------------------------------------------------------------

class SmartDesktopAssistant:
    """
    Top-level controller that wires together wake word, STT, and command execution.
    """

    def __init__(self, config: dict):
        self.config = config
        self._ready_event = threading.Event()
        self._shutdown_event = threading.Event()

        # Deferred imports so modules are only loaded when actually needed
        from commands import CommandParser
        from speech import SpeechRecognizer

        speech_cfg = config.get("speech", {})
        self._recognizer = SpeechRecognizer(
            model_size=speech_cfg.get("model_size", "base"),
            language=speech_cfg.get("language", "en") or None,
            device=speech_cfg.get("device", "auto"),
            compute_type=speech_cfg.get("compute_type", "int8"),
            max_record_seconds=float(speech_cfg.get("max_record_seconds", 10)),
            silence_threshold=int(speech_cfg.get("silence_threshold", 500)),
            silence_duration=float(speech_cfg.get("silence_duration", 1.5)),
        )

        self._parser = CommandParser(config)

    def run(self) -> None:
        """Start the assistant and block until interrupted."""
        from wakeword import WakeWordDetector

        ww_cfg = self.config.get("wakeword", {})
        access_key = ww_cfg.get("access_key", "")
        # Support environment variable expansion (e.g. "${PORCUPINE_ACCESS_KEY}")
        access_key = os.path.expandvars(access_key)

        if not access_key or access_key == "YOUR_PORCUPINE_ACCESS_KEY":
            _warn(
                "Porcupine access key not configured.\n"
                "  1. Sign up at https://console.picovoice.ai/ (free tier available).\n"
                "  2. Copy your access key into config.yaml → wakeword.access_key"
            )
            sys.exit(1)

        keywords = ww_cfg.get("keywords", ["jarvis"])
        sensitivity = float(ww_cfg.get("sensitivity", 0.5))

        detector = WakeWordDetector(
            access_key=access_key,
            keywords=keywords,
            sensitivity=sensitivity,
            on_detected=self._on_wake_word,
        )

        _info(
            f"SmartDesktop is ready. Say one of {keywords} to activate."
        )

        with detector:
            try:
                while not self._shutdown_event.is_set():
                    time.sleep(0.1)
            except KeyboardInterrupt:
                _info("Shutting down SmartDesktop...")

    def _on_wake_word(self, keyword: str) -> None:
        """
        Called on the WakeWord thread when the wake word is detected.
        Records and processes a command synchronously on the same thread.
        """
        _info(f"Wake word '{keyword}' detected! Listening for command...")
        transcript = self._recognizer.listen()

        if not transcript:
            _warn("No command detected.")
            return

        _info(f"You said: \"{transcript}\"")
        success = self._parser.execute(transcript)
        if not success:
            _warn(f"Command not recognised: \"{transcript}\"")

    def list_commands(self) -> None:
        """Print all registered commands to stdout."""
        print(f"\n{Fore.CYAN}Registered commands:{Style.RESET_ALL}")
        for cmd in self._parser.registered_commands:
            print(f"  • {cmd}")
        print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _info(message: str) -> None:
    print(f"{Fore.GREEN}[SmartDesktop]{Style.RESET_ALL} {message}")


def _warn(message: str) -> None:
    print(f"{Fore.YELLOW}[SmartDesktop]{Style.RESET_ALL} {message}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()
    config = _load_config(args.config)
    _setup_logging(config, args.log_level)

    assistant = SmartDesktopAssistant(config)

    if args.list_commands:
        assistant.list_commands()
        return

    assistant.run()


if __name__ == "__main__":
    main()
