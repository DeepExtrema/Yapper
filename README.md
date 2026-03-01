# Yapper

Local voice dictation daemon for Linux. Push-to-talk or toggle-mode voice recording with real-time transcription and smart text injection into focused applications. Works on Hyprland, GNOME, Cinnamon, KDE, and X11.

## Features

- **Local-first** — all processing runs on your machine, no cloud services
- **Real-time streaming** — segment-by-segment transcription via Silero VAD
- **Context-aware** — adapts correction style based on active window (code, chat, email, terminal, prose)
- **Cross-desktop** — Hyprland, GNOME, Cinnamon, KDE, Sway, and X11
- **Multiple injection methods** — wtype, ydotool, xdotool, or clipboard with automatic fallback
- **Optional LLM post-processing** — local grammar/spelling correction via llama-server
- **Custom dictionary** — personal word substitutions
- **Desktop notifications** — recording and processing status feedback
- **Systemd integration** — auto-start on login
- **Setup wizard** — interactive `yapper setup` for easy first-time configuration
- **Text formatter** — automatic capitalization and punctuation cleanup
- **Keybind support** — push-to-talk on Hyprland, toggle mode on all desktops

## Requirements

- Python 3.12+
- PipeWire or PulseAudio (audio capture)
- One of: wtype, ydotool, xdotool (text injection)
- [uv](https://docs.astral.sh/uv/) (recommended package manager)

## Quick Setup

The easiest way to get started is the interactive setup wizard:

```bash
git clone https://github.com/DeepExtrema/Yapper.git
cd Yapper
uv sync
uv run yapper setup
```

The wizard walks you through:
1. Audio device selection and mic test
2. Whisper model selection with GPU auto-detection
3. Keybind configuration for your desktop
4. Config file generation
5. Systemd service installation

### Supported Desktops

| Desktop | Keybind Method | Push-to-talk |
|---|---|---|
| Hyprland | `bind`/`bindr` config | Yes (hold-to-record) |
| GNOME | `gsettings` | Toggle only |
| Cinnamon | Manual setup | Toggle only |
| KDE Plasma | Manual setup | Toggle only |
| X11 (any) | Manual setup | Toggle only |

## Manual Installation

```bash
git clone https://github.com/DeepExtrema/Yapper.git
cd Yapper
uv sync

# Copy default config
mkdir -p ~/.config/yapper
cp config/default.toml ~/.config/yapper/config.toml

# Install systemd service
cp systemd/yapper.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now yapper

# Hyprland: add keybinds
cp hyprland/yapper.conf ~/.config/hypr/yapper.conf
# Then add to hyprland.conf: source = ~/.config/hypr/yapper.conf
```

## Usage

**Push-to-talk (Hyprland):** Hold configured key/button — records while held, transcribes on release.

**Toggle mode (all desktops):** Press configured key — starts/stops recording.

**CLI control:**
```bash
yapper-ctl start    # Begin recording
yapper-ctl stop     # Stop and transcribe
yapper-ctl toggle   # Toggle recording
yapper-ctl status   # Check daemon state
yapper-ctl quit     # Shutdown daemon
```

## Configuration

Edit `~/.config/yapper/config.toml`. See `config/default.toml` for all options.

Key settings:
- **Whisper model** — `transcriber.model` (default: `small.en`)
- **GPU acceleration** — `transcriber.device` = `cuda`
- **LLM correction** — `processor.enabled` = `true` (requires llama-server)
- **Injection method** — `injector.method` (auto, wtype, ydotool, xdotool, clipboard)
- **Text formatter** — `formatter.enabled` (default: `true`)
- **Streaming mode** — `streaming.enabled` (default: `true`)

## Optional: LLM Post-Processing

For grammar/spelling correction using a local LLM:

```bash
cp systemd/yapper-llm.service ~/.config/systemd/user/
systemctl --user enable --now yapper-llm
```

Then set `processor.enabled = true` in your config.

## Architecture

```
Microphone → AudioRecorder → StreamingVAD → Transcriber → Dictionary → Formatter → Processor → Injector → App
```

The daemon communicates with `yapper-ctl` via a Unix socket at `$XDG_RUNTIME_DIR/yapper.sock`.

## License

MIT
