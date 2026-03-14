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

from commands.apps import build_app_commands
from commands.terminal import build_terminal_commands
from commands.windows import build_window_commands
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

    def test_custom_project_command(self):
        parser = CommandParser(self._make_config(extra_projects={"littleguy": "~/repos/littleguy"}))
        self.assertIn("go to littleguy", parser.registered_commands)


if __name__ == "__main__":
    unittest.main(verbosity=2)
