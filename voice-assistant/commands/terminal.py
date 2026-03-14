"""
SmartDesktop Voice Assistant - Terminal / Shell Commands

Handles voice commands that run terminal operations:
  - Opening a terminal
  - Navigating to project directories
  - Running common developer commands (npm, git, python, etc.)
  - Custom macro sequences
"""

import logging
import os
import platform
import shlex
import subprocess
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_OS = platform.system()


# ---------------------------------------------------------------------------
# Low-level helper
# ---------------------------------------------------------------------------

def _run_in_terminal(command: str, cwd: Optional[str] = None) -> bool:
    """
    Run ``command`` in a new visible terminal window.

    On Windows, opens a new cmd window. On macOS, opens Terminal.app.
    On Linux, tries common terminal emulators.

    Args:
        command: Shell command string to execute.
        cwd: Optional working directory for the command.

    Returns:
        True if the terminal process was started, False otherwise.
    """
    expanded_cwd = os.path.expanduser(cwd) if cwd else None
    try:
        if _OS == "Windows":
            subprocess.Popen(
                f'start cmd /K "{command}"',
                shell=True,
                cwd=expanded_cwd,
            )
        elif _OS == "Darwin":
            # AppleScript to open a new Terminal window and run the command
            script = f'tell application "Terminal" to do script "{command}"'
            subprocess.Popen(["osascript", "-e", script], cwd=expanded_cwd)
        else:
            # Linux: try common terminal emulators in order
            for term in ["gnome-terminal", "xterm", "konsole", "x-terminal-emulator"]:
                if _which(term):
                    subprocess.Popen(
                        [term, "--", "bash", "-c", f"{command}; exec bash"],
                        cwd=expanded_cwd,
                    )
                    break
            else:
                logger.error("No supported terminal emulator found.")
                return False
        logger.info("Ran in terminal: %s (cwd=%s)", command, expanded_cwd)
        return True
    except (OSError, ValueError) as exc:
        logger.error("Failed to run terminal command '%s': %s", command, exc)
        return False


def _which(program: str) -> Optional[str]:
    """Return the full path of ``program`` if it exists on PATH, else None."""
    import shutil
    return shutil.which(program)


def _run_background(command: str, cwd: Optional[str] = None) -> bool:
    """
    Run ``command`` silently in the background (no new terminal window).

    Args:
        command: Shell command string.
        cwd: Optional working directory.

    Returns:
        True if the process was started, False otherwise.
    """
    expanded_cwd = os.path.expanduser(cwd) if cwd else None
    try:
        subprocess.Popen(
            command,
            shell=True,
            cwd=expanded_cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Background command started: %s", command)
        return True
    except (OSError, ValueError) as exc:
        logger.error("Failed to run background command '%s': %s", command, exc)
        return False


# ---------------------------------------------------------------------------
# Built-in terminal command handlers
# ---------------------------------------------------------------------------

def open_terminal_here() -> bool:
    """Open a terminal in the current working directory."""
    return _run_in_terminal("echo Terminal ready")


def git_status() -> bool:
    """Run 'git status' in a new terminal window."""
    return _run_in_terminal("git status")


def git_pull() -> bool:
    """Run 'git pull' in a new terminal window."""
    return _run_in_terminal("git pull")


def run_npm_start() -> bool:
    """Run 'npm start' in a new terminal window."""
    return _run_in_terminal("npm start")


def run_npm_dev() -> bool:
    """Run 'npm run dev' in a new terminal window."""
    return _run_in_terminal("npm run dev")


def run_npm_test() -> bool:
    """Run 'npm test' in a new terminal window."""
    return _run_in_terminal("npm test")


def run_npm_build() -> bool:
    """Run 'npm run build' in a new terminal window."""
    return _run_in_terminal("npm run build")


def run_python_main() -> bool:
    """Run 'python main.py' in a new terminal window."""
    return _run_in_terminal("python main.py")


def run_tests() -> bool:
    """Run pytest in a new terminal window."""
    return _run_in_terminal("pytest")


# ---------------------------------------------------------------------------
# Project navigation
# ---------------------------------------------------------------------------

def go_to_project(path: str) -> bool:
    """
    Open a terminal navigated to ``path`` and launch VS Code there.

    Args:
        path: Filesystem path (may contain ~ or environment variables).

    Returns:
        True if the terminal was opened successfully.
    """
    expanded = os.path.expandvars(os.path.expanduser(path))
    return _run_in_terminal(f"cd {shlex.quote(expanded)} && code .", cwd=expanded)


# ---------------------------------------------------------------------------
# Factory: build command map from config
# ---------------------------------------------------------------------------

def build_terminal_commands(
    projects_config: Optional[Dict[str, str]] = None,
    macros_config: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, callable]:
    """
    Return a mapping of command phrases to terminal command handlers.

    Args:
        projects_config: Dict of {name: path} from config.yaml.
        macros_config: Dict of {phrase: [command, ...]} from config.yaml.

    Returns:
        Dict mapping lowercase command phrase → callable.
    """
    commands: Dict[str, callable] = {
        # Git
        "git status": git_status,
        "git pull": git_pull,
        "show git status": git_status,
        "pull latest": git_pull,
        # npm
        "run start": run_npm_start,
        "start server": run_npm_start,
        "run dev": run_npm_dev,
        "start dev": run_npm_dev,
        "run tests": run_tests,
        "run test": run_tests,
        "npm test": run_npm_test,
        "npm start": run_npm_start,
        "npm dev": run_npm_dev,
        "npm build": run_npm_build,
        "run build": run_npm_build,
        # Python
        "run python": run_python_main,
        "run main": run_python_main,
        # Pytest
        "run pytest": run_tests,
    }

    # Project shortcuts — "go to <name>"
    if projects_config:
        for name, path in projects_config.items():
            phrase = f"go to {name.lower()}"
            commands[phrase] = (lambda p: lambda: go_to_project(p))(path)
            logger.debug("Registered project command: '%s' → %s", phrase, path)

    # Macro sequences — execute a list of shell commands in order
    if macros_config:
        for phrase, steps in macros_config.items():
            def _make_macro(step_list: List[str]) -> callable:
                def _run_macro() -> bool:
                    success = True
                    for step in step_list:
                        success = _run_in_terminal(step) and success
                    return success
                return _run_macro
            commands[phrase.lower()] = _make_macro(steps)
            logger.debug("Registered macro: '%s' (%d steps)", phrase, len(steps))

    return commands
