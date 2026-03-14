"""
SmartDesktop Voice Assistant - Command Registry

The ``CommandParser`` aggregates all command handlers (apps, windows, terminal)
and maps transcribed phrases to the appropriate action.

Command matching strategy (in priority order):
  1. Exact match after stripping the wake word prefix.
  2. Prefix / fuzzy substring match — the longest registered phrase that
     appears as a substring of the transcript wins.
  3. Unknown command → user-friendly feedback.
"""

import logging
from typing import Callable, Dict, Optional, Tuple

from commands.apps import build_app_commands
from commands.terminal import build_terminal_commands
from commands.windows import build_window_commands

logger = logging.getLogger(__name__)

# Type alias
CommandMap = Dict[str, Callable[[], bool]]


class CommandParser:
    """
    Parses a raw transcript and dispatches it to the correct action handler.

    Usage::

        parser = CommandParser(config)
        success = parser.execute("open chrome")
    """

    def __init__(self, config: dict):
        """
        Build the command registry from the given configuration.

        Args:
            config: Parsed ``config.yaml`` dict (full document).
        """
        cmd_cfg = config.get("commands", {})
        self.prefix: str = cmd_cfg.get("prefix", "jarvis").lower()

        self._commands: CommandMap = {}
        self._commands.update(build_app_commands(cmd_cfg.get("apps")))
        self._commands.update(build_window_commands())
        self._commands.update(
            build_terminal_commands(
                projects_config=cmd_cfg.get("projects"),
                macros_config=cmd_cfg.get("macros"),
            )
        )

        logger.info(
            "CommandParser initialised with %d commands.", len(self._commands)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, transcript: str) -> bool:
        """
        Parse *transcript* and execute the matching command.

        Args:
            transcript: Raw transcription from the speech recogniser
                        (lowercase, stripped).

        Returns:
            True if a command was matched and executed successfully.
        """
        phrase = self._strip_prefix(transcript)
        logger.debug("Parsed phrase: '%s'", phrase)

        handler, matched = self._match(phrase)
        if handler is None:
            logger.warning("No command matched for: '%s'", phrase)
            return False

        logger.info("Executing command '%s'...", matched)
        try:
            result = handler()
            if result:
                logger.info("Command '%s' completed successfully.", matched)
            else:
                logger.warning("Command '%s' returned failure.", matched)
            return bool(result)
        except Exception as exc:
            logger.error(
                "Error executing command '%s': %s", matched, exc, exc_info=True
            )
            return False

    @property
    def registered_commands(self) -> list:
        """Return a sorted list of all registered command phrases."""
        return sorted(self._commands.keys())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _strip_prefix(self, transcript: str) -> str:
        """
        Remove the wake word prefix from the beginning of *transcript*.

        Example:
            prefix = "jarvis", transcript = "jarvis open chrome"
            → "open chrome"
        """
        transcript = transcript.strip().lower()
        if transcript.startswith(self.prefix):
            transcript = transcript[len(self.prefix):].strip()
        return transcript

    def _match(self, phrase: str) -> Tuple[Optional[Callable], Optional[str]]:
        """
        Find the best command handler for *phrase*.

        Matching order:
          1. Exact match.
          2. Longest registered phrase that is a substring of *phrase*.

        Returns:
            (handler, matched_phrase) or (None, None) if no match.
        """
        # 1. Exact match
        if phrase in self._commands:
            return self._commands[phrase], phrase

        # 2. Substring match — prefer longer (more specific) matches
        candidates = [
            cmd for cmd in self._commands if cmd in phrase
        ]
        if candidates:
            best = max(candidates, key=len)
            return self._commands[best], best

        return None, None
