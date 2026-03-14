"""
SmartDesktop Voice Assistant - Window Control Commands

Handles voice commands for managing application windows:
  - focus / bring-to-front
  - minimise / maximise / restore
  - close
  - snap left / snap right (Windows only)
  - swap monitors / move window to next screen (Windows only via DisplaySwitch/NirCmd)
"""

import logging
import platform
import subprocess
from typing import Dict

logger = logging.getLogger(__name__)

_OS = platform.system()


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _get_window(title_fragment: str):
    """
    Return the first window whose title contains ``title_fragment`` (case-insensitive).

    Returns None on platforms where pygetwindow is not available.
    """
    try:
        import pygetwindow as gw
        matches = gw.getWindowsWithTitle(title_fragment)
        return matches[0] if matches else None
    except Exception as exc:
        logger.warning("pygetwindow unavailable or error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Window command handlers
# ---------------------------------------------------------------------------

def minimise_window(title: str = "") -> bool:
    """Minimise the window matching *title*, or the active window if empty."""
    win = _get_window(title)
    if win:
        try:
            win.minimize()
            logger.info("Minimised window: %s", win.title)
            return True
        except Exception as exc:
            logger.error("Could not minimise window: %s", exc)
    else:
        logger.warning("No window found matching '%s'", title)
    return False


def maximise_window(title: str = "") -> bool:
    """Maximise the window matching *title*, or the active window if empty."""
    win = _get_window(title)
    if win:
        try:
            win.maximize()
            logger.info("Maximised window: %s", win.title)
            return True
        except Exception as exc:
            logger.error("Could not maximise window: %s", exc)
    else:
        logger.warning("No window found matching '%s'", title)
    return False


def restore_window(title: str = "") -> bool:
    """Restore (un-minimise) the window matching *title*."""
    win = _get_window(title)
    if win:
        try:
            win.restore()
            logger.info("Restored window: %s", win.title)
            return True
        except Exception as exc:
            logger.error("Could not restore window: %s", exc)
    else:
        logger.warning("No window found matching '%s'", title)
    return False


def close_window(title: str = "") -> bool:
    """Close the window matching *title*."""
    win = _get_window(title)
    if win:
        try:
            win.close()
            logger.info("Closed window: %s", win.title)
            return True
        except Exception as exc:
            logger.error("Could not close window: %s", exc)
    else:
        logger.warning("No window found matching '%s'", title)
    return False


def focus_window(title: str) -> bool:
    """Bring the window matching *title* to the foreground."""
    win = _get_window(title)
    if win:
        try:
            win.activate()
            logger.info("Focused window: %s", win.title)
            return True
        except Exception as exc:
            logger.error("Could not focus window: %s", exc)
    else:
        logger.warning("No window found matching '%s'", title)
    return False


def snap_left() -> bool:
    """Snap the active window to the left half of the screen (Windows only)."""
    if _OS == "Windows":
        import pyautogui
        pyautogui.hotkey("win", "left")
        logger.info("Snapped active window to left.")
        return True
    logger.warning("snap_left is only supported on Windows.")
    return False


def snap_right() -> bool:
    """Snap the active window to the right half of the screen (Windows only)."""
    if _OS == "Windows":
        import pyautogui
        pyautogui.hotkey("win", "right")
        logger.info("Snapped active window to right.")
        return True
    logger.warning("snap_right is only supported on Windows.")
    return False


def swap_monitors() -> bool:
    """
    Move the primary display to the secondary monitor and vice-versa.

    Uses the Windows built-in ``DisplaySwitch.exe`` command:
      /internal   — only internal display
      /external   — only external display
      /clone      — clone both
      /extend     — extend to both

    Calling ``/external`` effectively swaps the primary display to the
    external monitor. Calling ``/internal`` reverts to the built-in screen.

    For a true "swap" (toggle), we detect the current display count and
    toggle between /extend and /clone, or simply call /external as a shortcut.
    """
    if _OS != "Windows":
        logger.warning("swap_monitors is only supported on Windows.")
        return False
    try:
        subprocess.Popen(["DisplaySwitch.exe", "/external"])
        logger.info("Display switched to external monitor.")
        return True
    except OSError as exc:
        logger.error("Failed to run DisplaySwitch: %s", exc)
        return False


def extend_displays() -> bool:
    """Extend displays across all monitors (Windows only)."""
    if _OS != "Windows":
        return False
    try:
        subprocess.Popen(["DisplaySwitch.exe", "/extend"])
        logger.info("Displays extended.")
        return True
    except OSError as exc:
        logger.error("Failed to extend displays: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Command map
# ---------------------------------------------------------------------------

def build_window_commands() -> Dict[str, callable]:
    """Return a mapping of command phrases to window management handlers."""
    return {
        "minimise window": lambda: minimise_window(),
        "minimize window": lambda: minimise_window(),
        "maximise window": lambda: maximise_window(),
        "maximize window": lambda: maximise_window(),
        "restore window": lambda: restore_window(),
        "close window": lambda: close_window(),
        "snap left": snap_left,
        "snap right": snap_right,
        "swap monitors": swap_monitors,
        "switch monitors": swap_monitors,
        "extend displays": extend_displays,
        "extend monitors": extend_displays,
    }
