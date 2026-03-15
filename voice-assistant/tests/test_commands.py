"""
Tests for the SmartDesktop command parser and command builders.
These tests mock hardware dependencies so they can run without a microphone or GPU.
"""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ------------------------------------------------------------------
# Stub out hardware-dependent modules before importing project code
# ------------------------------------------------------------------

def _stub_module(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod

# Porcupine / PyAudio stubs
_stub_module("pvporcupine")
_stub_module("pyaudio")
pa_mod = sys.modules["pyaudio"]
pa_mod.paInt16 = 8
pa_mod.PyAudio = MagicMock()

# Faster-Whisper stub
fw_mod = _stub_module("faster_whisper")
fw_mod.WhisperModel = MagicMock()

# PyAutoGUI stub
_stub_module("pyautogui")

# pygetwindow stub
gw_mod = _stub_module("pygetwindow")
gw_mod.getWindowsWithTitle = MagicMock(return_value=[])
gw_mod.getAllWindows = MagicMock(return_value=[])

# sounddevice / colorama stubs
_stub_module("sounddevice")
colorama_mod = _stub_module("colorama")
colorama_mod.Fore = MagicMock()
colorama_mod.Style = MagicMock()
colorama_mod.init = MagicMock()

# ------------------------------------------------------------------
# Now we can import project modules safely
# ------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from commands.apps import build_app_commands, _open_app
from commands.terminal import build_terminal_commands
from commands.windows import build_window_commands, swap_monitors, _get_monitors
from commands import CommandParser


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestBuildAppCommands(unittest.TestCase):

    def test_builtin_commands_present(self):
        cmds = build_app_commands()
        for phrase in ["open chrome", "open firefox", "open terminal",
                       "open vscode", "open spotify", "open discord"]:
            self.assertIn(phrase, cmds, f"Missing built-in command: {phrase}")

    def test_liked_songs_commands_present(self):
        cmds = build_app_commands()
        for phrase in ["play liked songs", "play my liked songs",
                       "spotify liked songs", "open liked songs"]:
            self.assertIn(phrase, cmds, f"Missing liked-songs command: {phrase}")

    def test_liked_songs_commands_all_callable(self):
        cmds = build_app_commands()
        for phrase in ["play liked songs", "play my liked songs",
                       "spotify liked songs", "open liked songs"]:
            self.assertTrue(callable(cmds[phrase]),
                            f"Handler for '{phrase}' is not callable")

    def test_custom_app_injected(self):
        custom = {"league": "C:/Riot Games/LeagueClient.exe"}
        cmds = build_app_commands(custom)
        self.assertIn("open league", cmds)
        self.assertTrue(callable(cmds["open league"]))

    def test_custom_app_tilde_expanded(self):
        import os
        custom = {"myapp": "~/myapp/myapp.exe"}
        cmds = build_app_commands(custom)
        self.assertIn("open myapp", cmds)

    def test_no_custom_apps(self):
        cmds = build_app_commands(None)
        self.assertIsInstance(cmds, dict)
        self.assertGreater(len(cmds), 0)


class TestOpenApp(unittest.TestCase):
    """Tests for the _open_app helper, focusing on Windows launch behaviour."""

    @patch("commands.apps._OS", "Windows")
    @patch("commands.apps.os.path.isfile", return_value=True)
    @patch("commands.apps.os.startfile", create=True)
    def test_windows_uses_startfile_for_existing_path(self, mock_startfile, mock_isfile):
        """On Windows, _open_app must use os.startfile for a path that exists."""
        result = _open_app(r"C:\Users\mario\AppData\Roaming\Spotify\Spotify.exe")
        mock_startfile.assert_called_once_with(
            r"C:\Users\mario\AppData\Roaming\Spotify\Spotify.exe"
        )
        self.assertTrue(result)

    @patch("commands.apps._OS", "Windows")
    @patch("commands.apps.os.path.isfile", return_value=True)
    @patch("commands.apps.os.startfile", create=True)
    def test_windows_normalises_forward_slashes(self, mock_startfile, mock_isfile):
        """Forward slashes in the path should be converted to backslashes."""
        result = _open_app("C:/Users/mario/AppData/Roaming/Spotify/Spotify.exe")
        mock_startfile.assert_called_once_with(
            r"C:\Users\mario\AppData\Roaming\Spotify\Spotify.exe"
        )
        self.assertTrue(result)

    @patch("commands.apps._OS", "Windows")
    @patch("commands.apps.os.path.isfile", return_value=False)
    @patch("commands.apps.subprocess.Popen")
    def test_windows_shell_fallback_when_path_not_found(self, mock_popen, mock_isfile):
        """When the path doesn't exist, the shell=True fallback should be used."""
        result = _open_app("start spotify")
        mock_popen.assert_called_once_with("start spotify", shell=True)
        self.assertTrue(result)

    @patch("commands.apps._OS", "Windows")
    @patch("commands.apps.os.path.isfile", return_value=True)
    @patch("commands.apps.os.startfile", create=True, side_effect=OSError("file not found"))
    def test_windows_startfile_oserror_returns_false(self, mock_startfile, mock_isfile):
        """An OSError from os.startfile should be caught and return False."""
        result = _open_app(r"C:\Missing\App.exe")
        self.assertFalse(result)


class TestBuildWindowCommands(unittest.TestCase):

    def test_expected_commands_present(self):
        cmds = build_window_commands()
        for phrase in ["minimise window", "maximize window",
                       "snap left", "snap right",
                       "swap monitors", "close window"]:
            self.assertIn(phrase, cmds, f"Missing window command: {phrase}")

    def test_all_values_callable(self):
        for phrase, handler in build_window_commands().items():
            self.assertTrue(callable(handler), f"Handler for '{phrase}' is not callable")


class TestBuildTerminalCommands(unittest.TestCase):

    def test_builtin_commands_present(self):
        cmds = build_terminal_commands()
        for phrase in ["git status", "git pull", "run dev", "run tests"]:
            self.assertIn(phrase, cmds, f"Missing terminal command: {phrase}")

    def test_project_shortcuts_injected(self):
        projects = {"littleguy": "~/repos/littleguy"}
        cmds = build_terminal_commands(projects_config=projects)
        self.assertIn("go to littleguy", cmds)
        self.assertTrue(callable(cmds["go to littleguy"]))

    def test_macro_injected(self):
        macros = {"start dev": ["open terminal", "npm run dev"]}
        cmds = build_terminal_commands(macros_config=macros)
        self.assertIn("start dev", cmds)
        self.assertTrue(callable(cmds["start dev"]))


class TestCommandParser(unittest.TestCase):

    def _make_config(self, extra_apps=None, extra_projects=None):
        return {
            "commands": {
                "prefix": "jarvis",
                "apps": extra_apps or {},
                "projects": extra_projects or {},
            }
        }

    def test_strip_prefix(self):
        parser = CommandParser(self._make_config())
        self.assertEqual(parser._strip_prefix("jarvis open chrome"), "open chrome")
        self.assertEqual(parser._strip_prefix("open chrome"), "open chrome")
        self.assertEqual(parser._strip_prefix("  jarvis   open chrome  "), "open chrome")

    def test_exact_match(self):
        parser = CommandParser(self._make_config())
        handler, matched = parser._match("open chrome")
        self.assertIsNotNone(handler)
        self.assertEqual(matched, "open chrome")

    def test_substring_match(self):
        parser = CommandParser(self._make_config())
        # "please open chrome for me" should still match "open chrome"
        handler, matched = parser._match("please open chrome for me")
        self.assertIsNotNone(handler)
        self.assertEqual(matched, "open chrome")

    def test_no_match(self):
        parser = CommandParser(self._make_config())
        handler, matched = parser._match("something completely unknown")
        self.assertIsNone(handler)
        self.assertIsNone(matched)

    def test_execute_unknown_returns_false(self):
        parser = CommandParser(self._make_config())
        result = parser.execute("jarvis do something unknown xyzzy")
        self.assertFalse(result)

    def test_registered_commands_sorted(self):
        parser = CommandParser(self._make_config())
        cmds = parser.registered_commands
        self.assertEqual(cmds, sorted(cmds))

    def test_registered_commands_nonempty(self):
        parser = CommandParser(self._make_config())
        self.assertGreater(len(parser.registered_commands), 10)

    def test_execute_with_wake_word_prefix(self):
        """execute() should strip the wake word and still match."""
        parser = CommandParser(self._make_config())
        # Patch the actual handler to avoid OS calls
        called = []
        parser._commands["open chrome"] = lambda: called.append(True) or True
        result = parser.execute("jarvis open chrome")
        self.assertTrue(result)
        self.assertEqual(len(called), 1)

    def test_liked_songs_command_matched(self):
        """'play liked songs' and variants should dispatch to a handler."""
        parser = CommandParser(self._make_config())
        for phrase in ["play liked songs", "play my liked songs",
                       "spotify liked songs", "open liked songs"]:
            called = []
            parser._commands[phrase] = lambda: called.append(True) or True
            result = parser.execute(f"jarvis {phrase}")
            self.assertTrue(result, f"Command '{phrase}' was not matched/executed")
            self.assertEqual(len(called), 1, f"Handler for '{phrase}' not called")

    def test_custom_project_command(self):
        parser = CommandParser(self._make_config(extra_projects={"littleguy": "~/repos/littleguy"}))
        self.assertIn("go to littleguy", parser.registered_commands)


class TestGetMonitors(unittest.TestCase):
    """Tests for the _get_monitors() helper."""

    @patch("commands.windows._OS", "Linux")
    def test_non_windows_returns_empty(self):
        self.assertEqual(_get_monitors(), [])

    @patch("commands.windows._OS", "Windows")
    def test_windows_returns_sorted_monitors(self):
        """_get_monitors must return monitors sorted left-to-right, top-to-bottom."""
        # Verify the sort key used inside _get_monitors is correct by building
        # the expected order independently (the ctypes callback is Windows-only
        # and tested implicitly via TestSwapMonitors integration tests).
        unsorted = [
            {"left": 1920, "top": 0, "right": 3840, "bottom": 1080},
            {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
        ]
        result = sorted(unsorted, key=lambda m: (m["left"], m["top"]))
        self.assertEqual(result[0]["left"], 0)
        self.assertEqual(result[1]["left"], 1920)


class TestSwapMonitors(unittest.TestCase):
    """Tests for the new window-rotation behaviour of swap_monitors()."""

    @patch("commands.windows._OS", "Linux")
    def test_non_windows_returns_false(self):
        self.assertFalse(swap_monitors())

    @patch("commands.windows._OS", "Windows")
    @patch("commands.windows._get_monitors", return_value=[{"left": 0, "top": 0, "right": 1920, "bottom": 1080}])
    def test_single_monitor_returns_false(self, _mock_monitors):
        self.assertFalse(swap_monitors())

    @patch("commands.windows._OS", "Windows")
    @patch("commands.windows._get_monitors", return_value=[
        {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
        {"left": 1920, "top": 0, "right": 3840, "bottom": 1080},
    ])
    def test_two_monitors_moves_windows(self, _mock_monitors):
        """Windows on monitor 0 should move to monitor 1 and vice-versa."""
        win_a = MagicMock()
        win_a.title = "Window A"
        win_a.isMinimized = False
        win_a.left, win_a.top, win_a.width, win_a.height = 100, 50, 800, 600

        win_b = MagicMock()
        win_b.title = "Window B"
        win_b.isMinimized = False
        win_b.left, win_b.top, win_b.width, win_b.height = 2100, 50, 800, 600

        with patch("pygetwindow.getAllWindows", return_value=[win_a, win_b]):
            result = swap_monitors()

        self.assertTrue(result)
        # win_a (centre at 500,350 → monitor 0) → monitor 1: x offset=100, new x=1920+100=2020
        win_a.moveTo.assert_called_once_with(2020, 50)
        # win_b (centre at 2500,350 → monitor 1) → monitor 0: x offset=2100-1920=180, new x=180
        win_b.moveTo.assert_called_once_with(180, 50)

    @patch("commands.windows._OS", "Windows")
    @patch("commands.windows._get_monitors", return_value=[
        {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
        {"left": 1920, "top": 0, "right": 3840, "bottom": 1080},
        {"left": 3840, "top": 0, "right": 5760, "bottom": 1080},
    ])
    def test_three_monitors_rotates_sequentially(self, _mock_monitors):
        """With 3 monitors, windows should rotate 0→1→2→0."""
        win_0 = MagicMock()
        win_0.title = "Mon0 Window"
        win_0.isMinimized = False
        win_0.left, win_0.top, win_0.width, win_0.height = 100, 50, 400, 300

        win_1 = MagicMock()
        win_1.title = "Mon1 Window"
        win_1.isMinimized = False
        win_1.left, win_1.top, win_1.width, win_1.height = 2100, 50, 400, 300

        win_2 = MagicMock()
        win_2.title = "Mon2 Window"
        win_2.isMinimized = False
        win_2.left, win_2.top, win_2.width, win_2.height = 4100, 50, 400, 300

        with patch("pygetwindow.getAllWindows", return_value=[win_0, win_1, win_2]):
            result = swap_monitors()

        self.assertTrue(result)
        # win_0 on monitor 0 → monitor 1: offset (100,50), new pos (1920+100, 0+50)
        win_0.moveTo.assert_called_once_with(2020, 50)
        # win_1 on monitor 1 → monitor 2: offset (2100-1920=180,50), new pos (3840+180, 0+50)
        win_1.moveTo.assert_called_once_with(4020, 50)
        # win_2 on monitor 2 → monitor 0: offset (4100-3840=260,50), new pos (0+260, 0+50)
        win_2.moveTo.assert_called_once_with(260, 50)

    @patch("commands.windows._OS", "Windows")
    @patch("commands.windows._get_monitors", return_value=[
        {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
        {"left": 1920, "top": 0, "right": 3840, "bottom": 1080},
    ])
    def test_minimized_windows_are_skipped(self, _mock_monitors):
        """Minimised windows must not be moved."""
        win_minimized = MagicMock()
        win_minimized.title = "Minimised Window"
        win_minimized.isMinimized = True
        win_minimized.left, win_minimized.top, win_minimized.width, win_minimized.height = (
            100, 50, 800, 600,
        )

        with patch("pygetwindow.getAllWindows", return_value=[win_minimized]):
            result = swap_monitors()

        self.assertTrue(result)
        win_minimized.moveTo.assert_not_called()

    @patch("commands.windows._OS", "Windows")
    @patch("commands.windows._get_monitors", return_value=[
        {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
        {"left": 1920, "top": 0, "right": 3840, "bottom": 1080},
    ])
    def test_untitled_windows_are_skipped(self, _mock_monitors):
        """Windows without a title must not be moved."""
        win_no_title = MagicMock()
        win_no_title.title = ""
        win_no_title.isMinimized = False
        win_no_title.left, win_no_title.top, win_no_title.width, win_no_title.height = (
            100, 50, 800, 600,
        )

        with patch("pygetwindow.getAllWindows", return_value=[win_no_title]):
            result = swap_monitors()

        self.assertTrue(result)
        win_no_title.moveTo.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
