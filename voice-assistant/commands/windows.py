"""
SmartDesktop Voice Assistant - Window Control Commands

Handles voice commands for managing application windows:
  - focus / bring-to-front
  - minimise / maximise / restore
  - close
  - snap left / snap right (Windows only)
  - swap monitors / move all windows to next screen in rotation (Windows only)
"""

import ctypes
import ctypes.wintypes
import logging
import platform
import subprocess
from typing import Dict, List

logger = logging.getLogger(__name__)

_OS = platform.system()


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _get_monitors() -> List[Dict[str, int]]:
    """
    Return a list of monitor rectangles sorted left-to-right, top-to-bottom.

    Each entry is a dict with keys: ``left``, ``top``, ``right``, ``bottom``.
    Uses the Windows ``EnumDisplayMonitors`` API via ``ctypes``; returns an
    empty list on non-Windows platforms.
    """
    if _OS != "Windows":
        return []

    monitors: List[Dict[str, int]] = []

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.wintypes.RECT),
        ctypes.c_ssize_t,
    )

    def _callback(_hMonitor, _hdcMonitor, lprc, _dwData):
        rect = lprc.contents
        monitors.append(
            {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
            }
        )
        return True

    try:
        ctypes.windll.user32.EnumDisplayMonitors(
            None, None, MonitorEnumProc(_callback), 0
        )
    except OSError as exc:
        logger.error("EnumDisplayMonitors failed: %s", exc)

    monitors.sort(key=lambda m: (m["left"], m["top"]))
    return monitors


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
    Move all visible windows between monitors in a sequential rotation.

    With 2 monitors every window on monitor A moves to monitor B and vice-versa.
    With N monitors the windows rotate: monitor[0]→monitor[1]→…→monitor[N-1]→monitor[0].

    Each window is placed at the same *relative* position within its destination
    monitor so that the layout is preserved.  Minimised windows are left untouched.
    """
    if _OS != "Windows":
        logger.warning("swap_monitors is only supported on Windows.")
        return False

    monitors = _get_monitors()
    if len(monitors) < 2:
        logger.warning("swap_monitors requires at least 2 monitors; found %d.", len(monitors))
        return False

    try:
        import pygetwindow as gw
    except Exception as exc:
        logger.error("pygetwindow unavailable: %s", exc)
        return False

    all_windows = gw.getAllWindows()
    n = len(monitors)

    # Group windows by the monitor their centre point falls on.
    windows_by_monitor: List[list] = [[] for _ in monitors]
    for win in all_windows:
        if not win.title:
            continue
        try:
            if win.isMinimized:
                continue
        except Exception:
            pass
        if win.width <= 0 or win.height <= 0:
            continue

        cx = win.left + win.width // 2
        cy = win.top + win.height // 2
        for idx, mon in enumerate(monitors):
            if mon["left"] <= cx < mon["right"] and mon["top"] <= cy < mon["bottom"]:
                windows_by_monitor[idx].append(win)
                break

    # Rotate: windows on monitor[i] move to monitor[(i + 1) % n].
    moved = 0
    for i, windows in enumerate(windows_by_monitor):
        src = monitors[i]
        dst = monitors[(i + 1) % n]
        for win in windows:
            rel_x = win.left - src["left"]
            rel_y = win.top - src["top"]
            new_x = dst["left"] + rel_x
            new_y = dst["top"] + rel_y
            try:
                win.moveTo(new_x, new_y)
                moved += 1
            except Exception as exc:
                logger.warning("Could not move window '%s': %s", win.title, exc)

    logger.info("Rotated %d window(s) across %d monitor(s).", moved, n)
    return True


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
