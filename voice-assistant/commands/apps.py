"""
SmartDesktop Voice Assistant - Application Launcher Commands

Handles voice commands that open applications.
"""

import logging
import os
import platform
import subprocess
import sys
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Detect the current operating system
_OS = platform.system()  # "Windows", "Darwin" (macOS), or "Linux"


def _open_app(app_path: str) -> bool:
    """
    Launch an application using the most appropriate method for the current OS.

    Args:
        app_path: Executable path, application name, or shell command string.

    Returns:
        True if the process was started successfully, False otherwise.
    """
    try:
        if _OS == "Windows":
            # Normalise forward slashes so Windows can find the file.
            normalized = app_path.replace("/", "\\")
            if os.path.isfile(normalized):
                # Use os.startfile (ShellExecuteEx) so Windows sets the
                # working directory to the app's own folder and resolves
                # DLL / resource paths correctly – identical to double-clicking
                # the file in Explorer.  Any OSError (e.g. if the file
                # disappears between the isfile check and the launch) is
                # caught by the outer except block below.
                os.startfile(normalized)
            else:
                # Fall back to shell=True for built-in commands such as
                # "start spotify", "calc", "explorer", or URI schemes like
                # "start spotify:collection".
                subprocess.Popen(app_path, shell=True)
        elif _OS == "Darwin":
            # macOS: prefer 'open' so .app bundles are handled correctly.
            if app_path.endswith(".app") or "/" not in app_path:
                subprocess.Popen(["open", "-a", app_path])
            else:
                subprocess.Popen(app_path, shell=True)
        else:
            # Linux / other POSIX
            subprocess.Popen(app_path, shell=True)
        logger.info("Launched application: %s", app_path)
        return True
    except (OSError, ValueError) as exc:
        logger.error("Failed to launch '%s': %s", app_path, exc)
        return False


# ---------------------------------------------------------------------------
# Built-in command handlers
# ---------------------------------------------------------------------------

def open_chrome() -> bool:
    """Open Google Chrome."""
    paths = {
        "Windows": "start chrome",
        "Darwin": "Google Chrome",
        "Linux": "google-chrome",
    }
    return _open_app(paths.get(_OS, "chrome"))


def open_firefox() -> bool:
    """Open Mozilla Firefox."""
    paths = {
        "Windows": "start firefox",
        "Darwin": "Firefox",
        "Linux": "firefox",
    }
    return _open_app(paths.get(_OS, "firefox"))


def open_terminal() -> bool:
    """Open the system terminal / command prompt."""
    paths = {
        "Windows": "start cmd",
        "Darwin": "Terminal",
        "Linux": "x-terminal-emulator",
    }
    return _open_app(paths.get(_OS, "xterm"))


def open_vscode() -> bool:
    """Open Visual Studio Code."""
    return _open_app("code")


def open_file_manager() -> bool:
    """Open the system file manager."""
    paths = {
        "Windows": "explorer",
        "Darwin": "Finder",
        "Linux": "xdg-open .",
    }
    return _open_app(paths.get(_OS, "xdg-open ."))


def open_calculator() -> bool:
    """Open the system calculator."""
    paths = {
        "Windows": "calc",
        "Darwin": "Calculator",
        "Linux": "gnome-calculator",
    }
    return _open_app(paths.get(_OS, "gnome-calculator"))


def open_spotify() -> bool:
    """Open Spotify, trying known install locations before falling back to the
    'start' shell command so the app reliably launches on Windows regardless
    of whether Spotify was installed from the web or the Microsoft Store."""
    if _OS == "Windows":
        candidates = [
            os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe"),
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return _open_app(candidate)
        # Fall back: works when Spotify is registered as a URI handler or is
        # findable on PATH.
        return _open_app("start spotify")
    paths = {
        "Darwin": "Spotify",
        "Linux": "spotify",
    }
    return _open_app(paths.get(_OS, "spotify"))


def play_spotify_liked_songs() -> bool:
    """Open Spotify and navigate to the liked-songs collection."""
    uris = {
        "Windows": "start spotify:collection",
        "Darwin": "open spotify:collection",
        "Linux": "xdg-open spotify:collection",
    }
    return _open_app(uris.get(_OS, "xdg-open spotify:collection"))


def open_discord() -> bool:
    """Open Discord."""
    paths = {
        "Windows": "start discord",
        "Darwin": "Discord",
        "Linux": "discord",
    }
    return _open_app(paths.get(_OS, "discord"))


def open_slack() -> bool:
    """Open Slack."""
    paths = {
        "Windows": "start slack",
        "Darwin": "Slack",
        "Linux": "slack",
    }
    return _open_app(paths.get(_OS, "slack"))


# ---------------------------------------------------------------------------
# Factory: build command map from config
# ---------------------------------------------------------------------------

def build_app_commands(apps_config: Optional[Dict[str, str]] = None) -> Dict[str, callable]:
    """
    Return a mapping of command phrases to callable handlers.

    Built-in commands are always included. If ``apps_config`` is provided
    (from config.yaml), custom app entries are added dynamically.

    Args:
        apps_config: Dict of {phrase: path/command} from the YAML config.

    Returns:
        Dict mapping lowercase command phrase → callable that launches the app.
    """
    commands: Dict[str, callable] = {
        "open chrome": open_chrome,
        "open firefox": open_firefox,
        "open terminal": open_terminal,
        "open vscode": open_vscode,
        "open vs code": open_vscode,
        "open code": open_vscode,
        "open file manager": open_file_manager,
        "open explorer": open_file_manager,
        "open calculator": open_calculator,
        "open spotify": open_spotify,
        "open discord": open_discord,
        "open slack": open_slack,
        "open new window": open_chrome,  # shortcut: new browser window
        "play liked songs": play_spotify_liked_songs,
        "play my liked songs": play_spotify_liked_songs,
        "spotify liked songs": play_spotify_liked_songs,
        "open liked songs": play_spotify_liked_songs,
    }

    # Inject custom app shortcuts from config.yaml
    if apps_config:
        for keyword, path in apps_config.items():
            phrase = f"open {keyword.lower()}"
            app_path = os.path.expandvars(os.path.expanduser(path))
            # Create a closure that captures app_path correctly
            commands[phrase] = (lambda p: lambda: _open_app(p))(app_path)
            logger.debug("Registered custom app command: '%s' → %s", phrase, app_path)

    return commands
