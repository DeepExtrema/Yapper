# Yapper

Local voice dictation daemon for Linux (Hyprland/Wayland). Push-to-talk or toggle-mode voice recording with real-time transcription and smart text injection into focused applications.

## Features

- **Local-first** — all processing runs on your machine, no cloud services
- **Real-time streaming** — segment-by-segment transcription via Silero VAD
- **Context-aware** — adapts correction style based on active window (code, chat, email, terminal, prose)
- **Multiple injection methods** — wtype, ydotool, or clipboard with automatic fallback
- **Optional LLM post-processing** — local grammar/spelling correction via llama-server
- **Custom dictionary** — personal word substitutions
- **Desktop notifications** — recording and processing status feedback
- **Systemd integration** — auto-start on login
- **Hyprland keybinds** — native Wayland push-to-talk and toggle mode

## Requirements

- Python 3.12+
- PipeWire (audio capture)
- Hyprland (window context detection)
- One of: wtype, ydotool, or wl-clipboard (text injection)
- [uv](https://docs.astral.sh/uv/) (recommended package manager)

## Installation

```bash
# Clone and install
git clone https://github.com/tekronz/Yapper.git
cd Yapper
uv sync

# Copy default config
mkdir -p ~/.config/yapper
cp config/default.toml ~/.config/yapper/config.toml

# Install systemd service
cp systemd/yapper.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now yapper

# Add Hyprland keybinds
cat hyprland/yapper.conf >> ~/.config/hypr/hyprland.conf
```

## Usage

**Push-to-talk:** Hold `Insert` key — records while held, transcribes on release.

**Toggle mode:** Press `Super+Alt+V` — starts/stops recording.

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
- **Injection method** — `injector.method` (auto, wtype, ydotool, clipboard)
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
Microphone → AudioRecorder → StreamingVAD → Transcriber → Dictionary → Processor → Injector → App
```

The daemon communicates with `yapper-ctl` via a Unix socket at `$XDG_RUNTIME_DIR/yapper.sock`.

## License

MIT
