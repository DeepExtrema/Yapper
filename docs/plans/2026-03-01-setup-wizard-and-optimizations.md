# Setup Wizard & Pipeline Optimizations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an interactive `yapper setup` wizard for easy first-time installation across multiple Linux desktops, and optimize the transcription pipeline for lower latency and better text quality.

**Architecture:** Three new modules (`platform.py` for desktop detection, `formatter.py` for text cleanup, `setup.py` for the wizard) plus modifications to `context.py`, `injector.py`, `config.py`, and `main.py` for cross-desktop support and latency optimizations.

**Tech Stack:** Python 3.12+ stdlib only (subprocess, os, shutil). No new pip dependencies.

---

### Task 1: Platform Detection Module

**Files:**
- Create: `src/yapper/platform.py`
- Test: `tests/test_platform.py`

**Step 1: Write the failing tests**

```python
"""Tests for platform detection."""

import os
from unittest.mock import patch

from yapper.platform import detect_desktop, detect_display_server, detect_package_manager, detect_gpu


def test_detect_hyprland():
    with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "Hyprland"}, clear=False):
        assert detect_desktop() == "hyprland"


def test_detect_gnome():
    with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "GNOME"}, clear=False):
        assert detect_desktop() == "gnome"


def test_detect_cinnamon():
    with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "X-Cinnamon"}, clear=False):
        assert detect_desktop() == "cinnamon"


def test_detect_kde():
    with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE"}, clear=False):
        assert detect_desktop() == "kde"


def test_detect_unknown_desktop():
    with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "SomethingElse"}, clear=False):
        assert detect_desktop() == "unknown"


def test_detect_wayland():
    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-1"}, clear=False):
        assert detect_display_server() == "wayland"


def test_detect_x11():
    env = {"DISPLAY": ":0"}
    with patch.dict(os.environ, env, clear=False):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WAYLAND_DISPLAY", None)
            assert detect_display_server() == "x11"


def test_detect_pacman():
    with patch("yapper.platform.shutil.which") as mock:
        mock.side_effect = lambda cmd: "/usr/bin/pacman" if cmd == "pacman" else None
        assert detect_package_manager() == "pacman"


def test_detect_apt():
    with patch("yapper.platform.shutil.which") as mock:
        mock.side_effect = lambda cmd: "/usr/bin/apt" if cmd == "apt" else None
        assert detect_package_manager() == "apt"


def test_detect_gpu_no_gpu():
    with patch("yapper.platform.shutil.which", return_value=None):
        with patch("yapper.platform.Path.exists", return_value=False):
            assert detect_gpu() == "cpu"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_platform.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write the implementation**

```python
"""Platform detection for cross-desktop support."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def detect_desktop() -> str:
    """Detect the current desktop environment."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "hyprland" in desktop:
        return "hyprland"
    if "gnome" in desktop:
        return "gnome"
    if "cinnamon" in desktop or "x-cinnamon" in desktop:
        return "cinnamon"
    if "kde" in desktop:
        return "kde"
    if "sway" in desktop:
        return "sway"
    return "unknown"


def detect_display_server() -> str:
    """Detect whether running Wayland or X11."""
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def detect_package_manager() -> str:
    """Detect the system package manager."""
    for pm in ("pacman", "apt", "dnf", "zypper"):
        if shutil.which(pm):
            return pm
    return "unknown"


def detect_gpu() -> str:
    """Detect GPU acceleration availability."""
    if shutil.which("nvidia-smi"):
        return "cuda"
    if shutil.which("rocm-smi") or Path("/opt/rocm").exists():
        return "rocm"
    return "cpu"


def suggest_install_cmd(package_manager: str, packages: list[str]) -> str:
    """Return the install command for the given package manager."""
    pkg_str = " ".join(packages)
    match package_manager:
        case "pacman":
            return f"sudo pacman -S {pkg_str}"
        case "apt":
            return f"sudo apt install {pkg_str}"
        case "dnf":
            return f"sudo dnf install {pkg_str}"
        case "zypper":
            return f"sudo zypper install {pkg_str}"
        case _:
            return f"Install: {pkg_str}"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_platform.py -v`
Expected: PASS

**Step 5: Commit**

```
git add src/yapper/platform.py tests/test_platform.py
git commit -m "feat: add platform detection module for cross-desktop support"
```

---

### Task 2: Text Formatter Module

**Files:**
- Create: `src/yapper/formatter.py`
- Test: `tests/test_formatter.py`
- Modify: `src/yapper/config.py:76-83` (add FormatterConfig)

**Step 1: Write the failing tests**

```python
"""Tests for text formatter."""

from yapper.formatter import format_text


def test_capitalize_first_letter():
    assert format_text("hello world") == "Hello world"


def test_capitalize_after_period():
    assert format_text("first sentence. second sentence") == "First sentence. Second sentence"


def test_clean_double_spaces():
    assert format_text("hello  world") == "Hello world"


def test_trim_whitespace():
    assert format_text("  hello world  ") == "Hello world"


def test_no_space_before_period():
    assert format_text("hello .") == "Hello."


def test_no_space_before_comma():
    assert format_text("hello , world") == "Hello, world"


def test_space_after_period():
    assert format_text("hello.world") == "Hello. World"


def test_empty_string():
    assert format_text("") == ""


def test_already_formatted():
    assert format_text("Hello world.") == "Hello world."


def test_multiple_sentences():
    assert format_text("one. two. three.") == "One. Two. Three."


def test_question_mark():
    assert format_text("is this working? yes it is") == "Is this working? Yes it is"


def test_exclamation():
    assert format_text("wow! that works") == "Wow! That works"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_formatter.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write the implementation**

```python
"""Lightweight text formatter for post-transcription cleanup."""

from __future__ import annotations

import re


def format_text(text: str) -> str:
    """Clean up transcribed text: capitalize, fix spacing, normalize punctuation."""
    if not text:
        return text

    text = text.strip()

    # Clean double+ spaces
    text = re.sub(r" {2,}", " ", text)

    # Remove space before punctuation
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)

    # Ensure space after sentence-ending punctuation if followed by a letter
    text = re.sub(r"([.!?])([A-Za-z])", r"\1 \2", text)

    # Capitalize first character
    if text:
        text = text[0].upper() + text[1:]

    # Capitalize after sentence-ending punctuation
    text = re.sub(r"([.!?])\s+([a-z])", lambda m: m.group(1) + " " + m.group(2).upper(), text)

    return text
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_formatter.py -v`
Expected: PASS

**Step 5: Add FormatterConfig to config.py**

Add after `StreamingConfig` (after line 83 of `src/yapper/config.py`):

```python
@dataclass
class FormatterConfig:
    enabled: bool = True
```

Add `formatter: FormatterConfig = field(default_factory=FormatterConfig)` to the `Config` class.

Add `FormatterConfig` to the isinstance tuple in `_apply_dict`.

**Step 6: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All pass

**Step 7: Commit**

```
git add src/yapper/formatter.py tests/test_formatter.py src/yapper/config.py
git commit -m "feat: add text formatter for post-transcription cleanup"
```

---

### Task 3: Cross-Desktop Window Context Detection

**Files:**
- Modify: `src/yapper/context.py`
- Test: `tests/test_context.py` (add new tests)

**Step 1: Write the failing tests**

Add to `tests/test_context.py`:

```python
import asyncio
from unittest.mock import patch

from yapper.context import get_active_window


def test_x11_fallback_xdotool():
    """When hyprctl fails, try xdotool on X11."""
    async def _test():
        with patch("yapper.context._get_window_hyprland", side_effect=FileNotFoundError):
            with patch("yapper.context._get_window_x11") as mock_x11:
                mock_x11.return_value = ("firefox", "Mozilla Firefox", False)
                ctx = await get_active_window()
                assert ctx.app_class == "firefox"
                assert ctx.mode == "prose"
    asyncio.run(_test())


def test_fallback_returns_default():
    """When all detection methods fail, return default context."""
    async def _test():
        with patch("yapper.context._get_window_hyprland", side_effect=FileNotFoundError):
            with patch("yapper.context._get_window_x11", side_effect=FileNotFoundError):
                ctx = await get_active_window()
                assert ctx.mode == "prose"
                assert ctx.app_class == ""
    asyncio.run(_test())
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_context.py -v`
Expected: FAIL (no `_get_window_hyprland` attribute)

**Step 3: Refactor context.py**

Split `get_active_window()` into backend functions:

- `_get_window_hyprland()` - existing hyprctl logic
- `_get_window_x11()` - new xdotool logic
- `get_active_window()` - tries backends in order

See the `_get_window_hyprland`, `_get_window_x11`, and updated `get_active_window` functions from the design doc Task 3 above.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_context.py -v`
Expected: PASS

**Step 5: Commit**

```
git add src/yapper/context.py tests/test_context.py
git commit -m "feat: add cross-desktop window detection (Hyprland + X11)"
```

---

### Task 4: Cross-Desktop Injection (xdotool + xclip)

**Files:**
- Modify: `src/yapper/injector.py`
- Modify: `tests/test_injector.py`

**Step 1: Write the failing tests**

Update `_make_injector` helper to support `has_xdotool` and `has_xclip`, then add:

```python
def test_pick_xdotool_for_x11():
    inj = _make_injector(has_wtype=False, has_ydotool=False, has_xdotool=True)
    ctx = WindowContext(is_xwayland=True)
    assert inj._pick_method("hello", ctx) == "xdotool"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_injector.py -v`
Expected: FAIL

**Step 3: Update injector.py**

Key changes:
1. Add `_has_xdotool` and `_has_xclip` detection in `__init__`
2. Add `_inject_xdotool` method using `xdotool type --clearmodifiers`
3. Update `_pick_method` to include xdotool in fallback chain
4. Remove `await asyncio.sleep(0.3)` from wtype and ydotool paths (lines 47 and 53)
5. Update `_copy_to_clipboard` to fall back to xclip

See the full updated code in the design doc Task 4 above.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_injector.py -v`
Expected: PASS

**Step 5: Commit**

```
git add src/yapper/injector.py tests/test_injector.py
git commit -m "feat: add xdotool/xclip support, remove injection sleep delays"
```

---

### Task 5: Pipeline Optimizations (Executor, VAD, Formatter Integration)

**Files:**
- Modify: `src/yapper/main.py` (add executor, formatter calls)
- Modify: `src/yapper/config.py` (reduce silence_duration_ms default to 500)

**Step 1: Update config defaults**

In `src/yapper/config.py`, change `StreamingConfig.silence_duration_ms` from 700 to 500.

**Step 2: Add dedicated executor and formatter to daemon**

In `src/yapper/main.py`:

1. Add imports: `from concurrent.futures import ThreadPoolExecutor` and `from yapper.formatter import format_text`
2. In `__init__`, add: `self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper")`
3. Replace all `loop.run_in_executor(None, ...)` with `loop.run_in_executor(self._executor, ...)`
4. After `text = self._dictionary.apply(text)` in both `_run_pipeline` and `_segment_worker`, add:
   ```python
   if self._config.formatter.enabled:
       text = format_text(text)
   ```
5. In `_shutdown`, add: `self._executor.shutdown(wait=False)`

**Step 3: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All pass

**Step 4: Commit**

```
git add src/yapper/main.py src/yapper/config.py
git commit -m "feat: dedicated executor, faster VAD defaults, formatter integration"
```

---

### Task 6: Setup Wizard — Core Structure & Entry Point

**Files:**
- Create: `src/yapper/setup.py`
- Modify: `src/yapper/main.py:316-328` (dispatch to setup)

**Step 1: Create wizard with color helpers, prompt utilities, and main `run_setup` function**

See the full `setup.py` code in the design doc Task 6.

Key functions:
- `_bold()`, `_green()`, `_yellow()`, `_red()`, `_cyan()`, `_dim()` — ANSI helpers
- `_header()` — step header display
- `_prompt_choice()` — numbered menu selection
- `_confirm()` — yes/no prompt
- `run_setup()` — main entry point that orchestrates all steps

**Step 2: Update main.py entry point**

In `main()`, add before `config = load_config()`:
```python
import sys
if len(sys.argv) > 1 and sys.argv[1] == "setup":
    from yapper.setup import run_setup
    run_setup()
    return
```

**Step 3: Commit**

```
git add src/yapper/setup.py src/yapper/main.py
git commit -m "feat: add setup wizard core structure with platform detection"
```

---

### Task 7: Setup Wizard — Audio Device Step

**Files:**
- Modify: `src/yapper/setup.py` (add `_step_audio`)

**Step 1: Implement `_step_audio`**

Lists audio devices via sounddevice, lets user pick one, tests 2-second recording, reports peak level. See full code in design doc Task 7.

**Step 2: Commit**

```
git add src/yapper/setup.py
git commit -m "feat: setup wizard step 1 — audio device selection with test"
```

---

### Task 8: Setup Wizard — Model & GPU Step

**Files:**
- Modify: `src/yapper/setup.py` (add `_step_model`)

**Step 1: Implement `_step_model`**

Shows model options with RAM estimates, auto-detects GPU, suggests acceleration. See full code in design doc Task 8.

**Step 2: Commit**

```
git add src/yapper/setup.py
git commit -m "feat: setup wizard step 2 — model selection with GPU detection"
```

---

### Task 9: Setup Wizard — Keybind Step

**Files:**
- Modify: `src/yapper/setup.py` (add `_step_keybind` and desktop-specific helpers)

**Step 1: Implement keybind configuration**

Desktop-specific functions:
- `_keybind_hyprland()` — wev detection, writes yapper.conf, sources in hyprland.conf
- `_keybind_gnome()` — gsettings custom keybinding for toggle
- `_keybind_cinnamon()` — manual instructions for toggle
- `_keybind_manual()` — generic instructions for unsupported desktops
- `_detect_with_wev()` — launches wev, parses button/key code

See full code in design doc Task 9.

**Step 2: Commit**

```
git add src/yapper/setup.py
git commit -m "feat: setup wizard step 3 — keybind config for Hyprland, GNOME, Cinnamon"
```

---

### Task 10: Setup Wizard — Config & Service Steps

**Files:**
- Modify: `src/yapper/setup.py` (add `_step_config` and `_step_service`)

**Step 1: Implement config generation and service installation**

- `_step_config()` — builds TOML content, shows preview, writes to ~/.config/yapper/config.toml
- `_step_service()` — copies systemd unit, enables service, reloads desktop config

See full code in design doc Task 10.

**Step 2: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All pass

**Step 3: Commit**

```
git add src/yapper/setup.py
git commit -m "feat: setup wizard steps 4-5 — config generation and service install"
```

---

### Task 11: Update default.toml and README

**Files:**
- Modify: `config/default.toml`
- Modify: `README.md`

**Step 1: Update default.toml**

Add formatter section:
```toml
[formatter]
enabled = true
```

Change `silence_duration_ms = 700` to `silence_duration_ms = 500`.

**Step 2: Update README**

Add Quick Setup section documenting `yapper setup` and the supported desktops table. Update installation instructions to recommend the wizard.

**Step 3: Commit**

```
git add config/default.toml README.md
git commit -m "docs: update config defaults and README with setup wizard docs"
```

---

### Task 12: Smoke Tests for Setup Wizard

**Files:**
- Create: `tests/test_setup.py`

**Step 1: Write smoke tests**

```python
"""Tests for setup wizard helpers."""

from yapper.setup import _bold, _green, _red, _yellow, _cyan, _dim


def test_ansi_helpers():
    assert "\033[1m" in _bold("test")
    assert "\033[32m" in _green("test")
    assert "\033[31m" in _red("test")
    assert "\033[33m" in _yellow("test")
    assert "\033[36m" in _cyan("test")
    assert "\033[2m" in _dim("test")


def test_bold_contains_text():
    assert "hello" in _bold("hello")
```

**Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All pass

**Step 3: Commit**

```
git add tests/test_setup.py
git commit -m "test: add setup wizard smoke tests"
```

---

### Task 13: Final Integration — Push to GitHub

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All pass

**Step 2: Push**

```
git push
```
