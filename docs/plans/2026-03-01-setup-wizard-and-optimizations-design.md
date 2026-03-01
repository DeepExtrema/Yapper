# Setup Wizard & Pipeline Optimizations Design

**Date:** 2026-03-01
**Status:** Approved

## Goals

1. Add a `yapper setup` wizard for easy first-time installation
2. Support multiple Linux desktops beyond Hyprland (GNOME, Cinnamon, KDE, X11)
3. Optimize the transcription-to-injection pipeline for lower latency and better accuracy

## Setup Wizard (`yapper setup`)

### Overview

A new `yapper setup` subcommand that walks users through the full setup in 5 interactive steps using only stdlib (no extra dependencies). Colored terminal output, numbered prompts, clear progress.

### Step 1 — Audio Device Selection

- List devices from `sounddevice.query_devices()` with numbered menu
- Let user pick or accept PipeWire/PulseAudio default
- Test recording for 2 seconds, confirm audio was captured

### Step 2 — Whisper Model Selection

- Present options with trade-off info:
  - `tiny.en` — fastest, lower accuracy
  - `small.en` — balanced (default)
  - `medium.en` — better accuracy, slower
  - `large-v3` — best accuracy, slowest
- Auto-detect ROCm (AMD GPU) or CUDA (NVIDIA) availability
- Suggest GPU device + float16 compute type if available
- Test transcription with a short sample to verify it works

### Step 3 — Keybind Configuration

- Detect desktop environment and display server
- Per-desktop keybind setup:

| Desktop | Method | Push-to-talk support |
|---|---|---|
| Hyprland | `bind`/`bindr` in yapper.conf | Yes (hold-to-record) |
| GNOME (Wayland/X11) | `gsettings` custom keybindings | Toggle only |
| Cinnamon | `dconf` keybindings | Toggle only |
| KDE Plasma | kglobalaccel | Toggle only |
| Fallback | `xbindkeys` | Toggle only |

- For Hyprland: launch `wev` to detect mouse/key, write config
- For X11 desktops: launch `xev` to detect key
- Mouse button detection via wev/xev where supported

### Step 4 — Config Generation

- Write `~/.config/yapper/config.toml` with all chosen settings
- Show config summary for confirmation before writing

### Step 5 — Service Installation

- Copy systemd unit to `~/.config/systemd/user/`
- `systemctl --user daemon-reload && enable --now yapper`
- Verify daemon is running via `yapper-ctl status`
- Reload desktop keybinds (hyprctl reload, etc.)
- Print summary with usage instructions

## Cross-Desktop Support

### Platform Detection (`platform.py`)

Detect:
- **Desktop environment:** `$XDG_CURRENT_DESKTOP`, `$DESKTOP_SESSION`
- **Display server:** `$WAYLAND_DISPLAY` (Wayland) vs `$DISPLAY` (X11)
- **Package manager:** check for `pacman`, `apt`, `dnf`

### Window Context Detection (`context.py`)

Multi-desktop active window detection:
1. Hyprland: `hyprctl activewindow -j` (existing)
2. GNOME/Wayland: `gdbus call` to get focused window
3. X11: `xdotool getactivewindow getwindowclassname`
4. Fallback: return default "prose" context

### Text Injection (`injector.py`)

Expanded method support:

| Method | Display | Notes |
|---|---|---|
| wtype | Wayland | Existing, fastest |
| ydotool | Both | Existing, universal fallback |
| xdotool | X11 | New, with `--clearmodifiers` |
| clipboard (wl-copy) | Wayland | Existing |
| clipboard (xclip/xsel) | X11 | New |

### Package Manager Helpers

Wizard can suggest installing missing tools:
- Arch: `sudo pacman -S wev wtype`
- Ubuntu/Mint: `sudo apt install wev wtype xdotool`
- Fedora: `sudo dnf install wev wtype xdotool`

## Pipeline Optimizations

### Latency Reductions

- **Remove 0.3s injection sleep** for wtype/ydotool direct typing (keep delay only for clipboard paste)
- **Reduce default `silence_duration_ms`** from 700ms to 500ms for faster segment boundaries
- **Dedicated `ThreadPoolExecutor(max_workers=1)`** for transcription to prevent contention with default executor

### AMD GPU Acceleration

- Auto-detect ROCm via `rocm-smi` or `/opt/rocm` presence
- Set `device=cuda`, `compute_type=float16` (CTranslate2 supports ROCm via HIP)
- Wizard tests GPU transcription and falls back to CPU on failure

### Text Formatter (`formatter.py`)

Lightweight post-transcription cleanup that runs before LLM processing:
- Capitalize first letter of sentences
- Clean up double spaces
- Trim leading/trailing whitespace
- Normalize punctuation spacing (no space before period/comma)
- Zero latency cost, runs even when LLM is disabled

### Injection Reliability

- Remove unnecessary delays for direct typing methods
- Keep clipboard paste delay (needed for Ctrl+V timing)
- X11: use `xdotool type --clearmodifiers` to avoid modifier conflicts

## New Files

- `src/yapper/setup.py` — setup wizard (all 5 steps)
- `src/yapper/platform.py` — desktop/display/package manager detection
- `src/yapper/formatter.py` — lightweight text formatter

## Modified Files

- `src/yapper/main.py` — dispatch `yapper setup`, dedicated executor
- `src/yapper/context.py` — multi-desktop window detection
- `src/yapper/injector.py` — xdotool support, remove sleeps, X11 clipboard
- `src/yapper/config.py` — formatter config section

## Constraints

- No new Python dependencies (stdlib + subprocess to system tools)
- `requires-python >= 3.12` unchanged
- Push-to-talk (hold-to-record) only works on Hyprland; other desktops use toggle mode
- Desktop-specific keybind setup is best-effort; wizard prints manual instructions if auto-config fails
