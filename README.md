# smartDesktop

A local, offline voice automation assistant for developer workflows and desktop control — similar to Siri or Alexa but optimised for power users and developers.

## Overview

```
Microphone → Wake Word (Porcupine) → Speech-to-Text (Faster-Whisper) → Command Parser → Action Executor
```

The assistant runs permanently in the background, listens for a **wake word** (default: *"Jarvis"*), transcribes the following command entirely offline using Faster-Whisper, and executes the matching OS action.

## Features

- 🎙️ **Always-on wake word detection** — ultra-low CPU usage via Porcupine
- 🗣️ **Offline speech recognition** — Faster-Whisper, works without internet
- 🚀 **App launcher** — open Chrome, VS Code, Spotify, Discord, and custom apps
- 🪟 **Window management** — minimise, maximise, snap, swap monitors
- 💻 **Terminal automation** — run git, npm, pytest and custom shell commands
- 📁 **Project navigation** — jump to any project directory and open it in VS Code
- 🔧 **Fully configurable** — all commands and shortcuts defined in `config.yaml`
- 🌍 **Cross-platform** — Windows, macOS, Linux

## Quick Start

### 1. Prerequisites

- Python 3.9+
- A microphone
- A free [Picovoice account](https://console.picovoice.ai/) for a Porcupine access key

### 2. Install dependencies

```bash
cd voice-assistant
pip install -r requirements.txt
```

> **Note:** PyAudio requires `portaudio`. Install it first:
> - Windows: included in the PyAudio wheel
> - macOS: `brew install portaudio`
> - Linux: `sudo apt install portaudio19-dev`

### 3. Configure

Edit `voice-assistant/config.yaml`:

```yaml
wakeword:
  access_key: "YOUR_PORCUPINE_ACCESS_KEY"   # from console.picovoice.ai
  keywords:
    - jarvis
  sensitivity: 0.5

commands:
  apps:
    league: "C:/Riot Games/LeagueClient.exe"
  projects:
    myapp: "~/repos/myapp"
```

### 4. Run

```bash
cd voice-assistant
python main.py
```

List all available commands:

```bash
python main.py --list-commands
```

## Example Commands

| You say | What happens |
|---|---|
| *Jarvis open chrome* | Opens Google Chrome |
| *Jarvis open terminal* | Opens a terminal window |
| *Jarvis open vscode* | Opens VS Code |
| *Jarvis open spotify* | Opens Spotify |
| *Jarvis go to littleguy* | `cd ~/repos/littleguy && code .` |
| *Jarvis git status* | Runs `git status` in a terminal |
| *Jarvis run dev* | Runs `npm run dev` in a terminal |
| *Jarvis run tests* | Runs `pytest` in a terminal |
| *Jarvis snap left* | Snaps active window to the left |
| *Jarvis swap monitors* | Switches to external display |
| *Jarvis minimise window* | Minimises the active window |

## Project Structure

```
voice-assistant/
├── main.py              # Entry point — orchestrates all components
├── config.yaml          # All configuration (wake word, commands, apps)
├── requirements.txt     # Python dependencies
├── wakeword/
│   └── __init__.py      # Porcupine wake word detection
├── speech/
│   └── __init__.py      # Faster-Whisper speech-to-text
├── commands/
│   ├── __init__.py      # CommandParser — registry and dispatch
│   ├── apps.py          # App launcher commands
│   ├── windows.py       # Window management commands
│   └── terminal.py      # Terminal / shell commands
└── models/
    └── README.md        # How to add custom wake word models
```

## Configuration Reference

### `wakeword`

| Key | Description | Default |
|---|---|---|
| `access_key` | Picovoice API key | *required* |
| `keywords` | Wake word list (built-in or custom) | `[jarvis]` |
| `sensitivity` | Detection sensitivity (0.0–1.0) | `0.5` |

### `speech`

| Key | Description | Default |
|---|---|---|
| `model_size` | Whisper model (`tiny`, `base`, `small`, `medium`, `large`) | `base` |
| `language` | Language code (`en`, `fr`, …) or `null` for auto | `en` |
| `device` | Inference device (`cpu`, `cuda`, `auto`) | `auto` |
| `compute_type` | Quantisation (`int8`, `float16`, `float32`) | `int8` |
| `max_record_seconds` | Max recording time per command | `10` |
| `silence_threshold` | RMS below which audio is silent | `500` |
| `silence_duration` | Seconds of silence to end recording | `1.5` |

### `commands`

| Key | Description |
|---|---|
| `prefix` | Wake word to strip from transcripts (`jarvis`) |
| `apps` | Custom app shortcuts (`name: path`) |
| `projects` | Project directory shortcuts (`name: path`) |
| `macros` | Multi-step command sequences |

## Advanced: Adding Custom Commands

Open `commands/apps.py` and add a new handler:

```python
def open_league() -> bool:
    return _open_app("C:/Riot Games/LeagueClient.exe")
```

Then register it in `build_app_commands()`:

```python
"open league": open_league,
```

Or simply add an entry to `config.yaml`:

```yaml
commands:
  apps:
    league: "C:/Riot Games/LeagueClient.exe"
```

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.9+ |
| Wake word | [Porcupine](https://github.com/Picovoice/porcupine) |
| Speech-to-text | [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) |
| Audio capture | PyAudio |
| Desktop automation | PyAutoGUI |
| Window management | pygetwindow |
| Shell commands | subprocess |
| Configuration | PyYAML |
