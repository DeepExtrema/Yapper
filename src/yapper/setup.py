"""Interactive setup wizard for Yapper voice dictation."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


# ── Colour / prompt helpers ───────────────────────────────────────────


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m"


def _yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m"


def _red(text: str) -> str:
    return f"\033[31m{text}\033[0m"


def _cyan(text: str) -> str:
    return f"\033[36m{text}\033[0m"


def _dim(text: str) -> str:
    return f"\033[2m{text}\033[0m"


def _header(step: int, total: int, title: str) -> None:
    """Print a step header with a line separator."""
    print()
    print("─" * 60)
    print(_bold(f"  Step {step}/{total}: {title}"))
    print("─" * 60)
    print()


def _prompt_choice(options: list[tuple[str, str]], default: int = 0) -> int:
    """Show a numbered menu and return the selected index.

    *options* is a list of ``(label, description)`` tuples.
    """
    for i, (label, desc) in enumerate(options):
        marker = _cyan("→") if i == default else " "
        idx = _bold(f"[{i + 1}]")
        line = f"  {marker} {idx} {label}"
        if desc:
            line += f"  {_dim(desc)}"
        print(line)

    print()
    while True:
        raw = input(f"  Choose [1-{len(options)}] (default {default + 1}): ").strip()
        if raw == "":
            return default
        try:
            choice = int(raw) - 1
            if 0 <= choice < len(options):
                return choice
        except ValueError:
            pass
        print(_red(f"  Please enter a number between 1 and {len(options)}."))


def _confirm(msg: str, default: bool = True) -> bool:
    """Ask a Y/n (or y/N) confirmation question."""
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"  {msg} [{hint}]: ").strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print(_red("  Please answer y or n."))


# ── Step 1: Audio device ─────────────────────────────────────────────


def _step_audio(step: int, total: int) -> dict:
    _header(step, total, "Audio Input Device")

    try:
        import sounddevice as sd  # noqa: F811
    except ImportError:
        print(_red("  sounddevice is not installed — skipping audio setup."))
        print(_dim("  Install it with: pip install sounddevice"))
        return {"audio": {"device": None}}

    try:
        all_devices = sd.query_devices()
    except Exception as exc:
        print(_red(f"  Could not query audio devices: {exc}"))
        return {"audio": {"device": None}}

    # Filter to input devices
    input_devs: list[tuple[int, dict]] = []
    for idx, dev in enumerate(all_devices):
        if dev["max_input_channels"] > 0:
            input_devs.append((idx, dev))

    if not input_devs:
        print(_yellow("  No input devices found. Using system default."))
        return {"audio": {"device": None}}

    # Build options list
    options: list[tuple[str, str]] = [("System default", "let PipeWire decide")]
    for _idx, dev in input_devs:
        sr = int(dev["default_samplerate"])
        ch = dev["max_input_channels"]
        options.append((dev["name"], f"{ch}ch, {sr} Hz"))

    print("  Select your microphone:\n")
    choice = _prompt_choice(options, default=0)

    if choice == 0:
        device_name: str | None = None
        device_index: int | None = None
        print(f"\n  {_green('✓')} Using system default device.")
    else:
        device_index = input_devs[choice - 1][0]
        device_name = input_devs[choice - 1][1]["name"]
        print(f"\n  {_green('✓')} Selected: {_bold(device_name)}")

    # Offer a test recording
    if _confirm("Test a 2-second recording?", default=True):
        print("  Recording for 2 seconds...")
        try:
            import numpy as np

            audio = sd.rec(
                int(2 * 16000),
                samplerate=16000,
                channels=1,
                dtype="float32",
                device=device_index,
            )
            sd.wait()
            peak = float(np.max(np.abs(audio)))
            if peak < 0.01:
                print(_yellow(f"  Peak level: {peak:.4f} — very quiet, check your mic!"))
            elif peak > 0.95:
                print(_yellow(f"  Peak level: {peak:.4f} — very loud, consider lowering gain."))
            else:
                print(_green(f"  Peak level: {peak:.4f} — looks good!"))
        except Exception as exc:
            print(_red(f"  Recording test failed: {exc}"))
            print(_dim("  You can still continue — the device may work at runtime."))

    return {"audio": {"device": device_name}}


# ── Step 2: Model & GPU ──────────────────────────────────────────────


_MODEL_OPTIONS: list[tuple[str, str, str]] = [
    # (model_name, label, description)
    ("tiny.en", "tiny.en", "~75 MB, fastest, lower accuracy"),
    ("small.en", "small.en", "~500 MB, good balance (recommended)"),
    ("medium.en", "medium.en", "~1.5 GB, better accuracy, slower"),
    ("large-v3", "large-v3", "~3 GB, best accuracy, multilingual"),
]


def _step_model(step: int, total: int, gpu: str) -> dict:
    _header(step, total, "Transcription Model")

    options = [(label, desc) for _, label, desc in _MODEL_OPTIONS]
    print("  Choose a Whisper model:\n")
    choice = _prompt_choice(options, default=1)  # default = small.en
    model = _MODEL_OPTIONS[choice][0]
    print(f"\n  {_green('✓')} Model: {_bold(model)}")

    device = "cpu"
    compute_type = "int8"

    if gpu in ("cuda", "rocm"):
        print(f"\n  GPU detected: {_bold(gpu)}")
        if _confirm("Enable GPU acceleration?", default=True):
            device = "cuda"  # CTranslate2 uses 'cuda' for both CUDA and ROCm/HIP
            compute_type = "float16"
            if gpu == "rocm":
                print(_yellow("  Note: ROCm support requires CTranslate2 built with HIP."))
                print(_dim("  If transcription fails, re-run setup and choose CPU."))
            print(f"  {_green('✓')} GPU acceleration enabled (device=cuda, {compute_type})")
        else:
            print(f"  {_dim('Using CPU (int8)')}")
    else:
        print(f"\n  {_dim('No GPU detected — using CPU (int8)')}")

    return {
        "transcriber": {
            "model": model,
            "device": device,
            "compute_type": compute_type,
        }
    }


# ── Step 3: Keybind ──────────────────────────────────────────────────


def _detect_with_wev(is_mouse: bool) -> tuple[str, str] | None:
    """Launch wev to detect a key or mouse button press.

    Returns ``(key_or_button, 'mouse'|'keyboard')`` or ``None`` on failure.
    """
    if not shutil.which("wev"):
        print(_yellow("  wev is not installed — cannot auto-detect."))
        return None

    filter_arg = "wl_pointer:button" if is_mouse else "wl_keyboard:key"
    kind = "mouse button" if is_mouse else "key"
    print(f"  Press the {kind} you want to use (in the wev window)...")
    print(_dim("  A small window will open — press your key there, then close it."))

    try:
        result = subprocess.run(
            ["wev", "-f", filter_arg],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        print(_yellow("  wev timed out — using default."))
        return None
    except Exception as exc:
        print(_red(f"  Failed to run wev: {exc}"))
        return None

    if is_mouse:
        # Look for button number: "button: 274" etc.
        match = re.search(r"button:\s*(\d+)", output)
        if match:
            return (match.group(1), "mouse")
    else:
        # Look for sym: Insert, sym: F12, etc.
        match = re.search(r"sym:\s+(\S+)", output)
        if match:
            return (match.group(1), "keyboard")

    print(_yellow("  Could not detect key from wev output."))
    return None


def _keybind_hyprland() -> dict:
    """Configure keybind for Hyprland."""
    print("  Hyprland supports mouse and keyboard binds.\n")

    options = [
        ("Default (Insert key)", ""),
        ("Detect with wev (keyboard)", "press a key in the wev window"),
        ("Detect with wev (mouse)", "press a mouse button in the wev window"),
        ("Enter manually", "type the Hyprland bind string"),
    ]
    choice = _prompt_choice(options, default=0)

    bind_key = "Insert"
    bind_type = "keyboard"

    if choice == 0:
        pass  # keep Insert default
    elif choice == 1:
        result = _detect_with_wev(is_mouse=False)
        if result:
            bind_key, bind_type = result
            print(f"  Detected: {_bold(bind_key)}")
    elif choice == 2:
        result = _detect_with_wev(is_mouse=True)
        if result:
            bind_key, bind_type = result
            print(f"  Detected mouse button: {_bold(bind_key)}")
    elif choice == 3:
        raw = input("  Enter key name (e.g. Insert, F12, XF86Launch1): ").strip()
        if raw and re.match(r"^[a-zA-Z0-9_]+$", raw):
            bind_key = raw
        elif raw:
            print(_red("  Invalid key name (alphanumeric and underscores only). Using default (Insert)."))


    # Determine yapper-ctl path
    ctl = shutil.which("yapper-ctl") or "yapper-ctl"

    # Build the Hyprland config lines
    if bind_type == "mouse":
        bind_line = f"bind = , mouse:{bind_key}, exec, {ctl} toggle"
    else:
        bind_line = f"bind = , {bind_key}, exec, {ctl} toggle"

    conf_content = f"# Yapper voice dictation keybind\n{bind_line}\n"
    print(f"\n  Generated config:\n  {_dim(bind_line)}")

    hypr_dir = Path.home() / ".config" / "hypr"
    yapper_conf = hypr_dir / "yapper.conf"

    if _confirm(f"Write to {yapper_conf}?", default=True):
        try:
            hypr_dir.mkdir(parents=True, exist_ok=True)
            yapper_conf.write_text(conf_content)
            print(f"  {_green('✓')} Wrote {yapper_conf}")
        except OSError as exc:
            print(_red(f"  Failed to write config: {exc}"))
            print(_dim(f"  Add this line to your Hyprland config manually:\n  {bind_line}"))
            return {"keybind": bind_key}

        # Offer to source from main hyprland.conf
        hyprland_conf = hypr_dir / "hyprland.conf"
        source_line = "source = ~/.config/hypr/yapper.conf"
        already_sourced = False

        if hyprland_conf.exists():
            try:
                content = hyprland_conf.read_text()
                if "yapper.conf" in content:
                    already_sourced = True
                    print(f"  {_dim('yapper.conf is already sourced in hyprland.conf')}")
            except OSError:
                pass

        if not already_sourced and _confirm(
            f"Add '{source_line}' to hyprland.conf?", default=True
        ):
            try:
                with open(hyprland_conf, "a") as f:
                    f.write(f"\n{source_line}\n")
                print(f"  {_green('✓')} Updated {hyprland_conf}")
            except OSError as exc:
                print(_red(f"  Could not update hyprland.conf: {exc}"))
                print(_dim(f"  Add this line manually:\n  {source_line}"))
    else:
        print(_dim(f"  Add this to your Hyprland config:\n  {bind_line}"))

    return {"keybind": bind_key}


def _keybind_gnome() -> dict:
    """Configure keybind for GNOME."""
    raw = input("  Enter keybind (default <Super>v): ").strip()
    keybind = raw if raw else "<Super>v"

    print(f"  Configuring GNOME keybind: {_bold(keybind)}")

    # Find yapper-ctl
    ctl = shutil.which("yapper-ctl") or "yapper-ctl"

    # GNOME custom keybindings via gsettings
    schema = "org.gnome.settings-daemon.plugins.media-keys"
    custom_schema = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
    base_path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
    slot_path = f"{base_path}/yapper/"

    try:
        # Get existing custom keybindings
        result = subprocess.run(
            ["gsettings", "get", schema, "custom-keybindings"],
            capture_output=True,
            text=True,
        )
        existing = result.stdout.strip()

        # Add our slot if not present
        if "yapper" not in existing:
            if existing in ("@as []", "[]"):
                new_list = f"['{slot_path}']"
            else:
                # Strip trailing ] and add ours
                new_list = existing.rstrip("]").rstrip() + f", '{slot_path}']"
            subprocess.run(
                ["gsettings", "set", schema, "custom-keybindings", new_list],
                check=True,
            )

        # Set name, command, binding
        subprocess.run(
            ["gsettings", "set", f"{custom_schema}:{slot_path}", "name", "Yapper Toggle"],
            check=True,
        )
        subprocess.run(
            ["gsettings", "set", f"{custom_schema}:{slot_path}", "command", f"{ctl} toggle"],
            check=True,
        )
        subprocess.run(
            ["gsettings", "set", f"{custom_schema}:{slot_path}", "binding", keybind],
            check=True,
        )
        print(f"  {_green('✓')} GNOME keybind configured: {keybind} → {ctl} toggle")
    except FileNotFoundError:
        print(_yellow("  gsettings not found — configure keybind manually."))
        print(_dim(f"  Set a custom shortcut to run: {ctl} toggle"))
    except subprocess.CalledProcessError as exc:
        print(_red(f"  gsettings failed: {exc}"))
        print(_dim(f"  Set a custom shortcut manually to run: {ctl} toggle"))

    return {"keybind": keybind}


def _keybind_cinnamon() -> dict:
    """Configure keybind for Cinnamon."""
    raw = input("  Enter keybind (default <Super>v): ").strip()
    keybind = raw if raw else "<Super>v"

    ctl = shutil.which("yapper-ctl") or "yapper-ctl"

    print(f"\n  {_yellow('Cinnamon keybind must be configured manually:')}")
    print(f"  1. Open System Settings → Keyboard → Shortcuts")
    print(f"  2. Add a custom shortcut:")
    print(f"     Name: Yapper Toggle")
    print(f"     Command: {ctl} toggle")
    print(f"     Keybind: {keybind}")
    print()

    return {"keybind": keybind}


def _keybind_manual(desktop: str) -> dict:
    """Provide generic keybind instructions for unknown desktops."""
    ctl = shutil.which("yapper-ctl") or "yapper-ctl"

    print(f"  Desktop: {_bold(desktop)}")
    print(f"\n  {_yellow('Configure a keybind manually in your desktop settings:')}")
    print(f"  Command: {ctl} toggle")
    print(f"\n  This will toggle recording on/off.")
    print()

    return {"keybind": "manual"}


def _step_keybind(
    step: int,
    total: int,
    desktop: str,
    display: str,
    pkg_mgr: str,
) -> dict:
    _header(step, total, "Keybind Configuration")

    print(f"  Desktop: {_bold(desktop)}  |  Display: {_bold(display)}\n")

    if desktop == "hyprland":
        return _keybind_hyprland()
    elif desktop == "gnome":
        return _keybind_gnome()
    elif desktop == "cinnamon":
        return _keybind_cinnamon()
    else:
        return _keybind_manual(desktop)


# ── Step 4: Config file ──────────────────────────────────────────────


def _toml_escape(s: str) -> str:
    """Escape a string for use as a TOML quoted value."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _build_toml(config: dict) -> str:
    """Build a minimal TOML string from the collected config dict."""
    lines: list[str] = ["# Yapper configuration — generated by setup wizard", ""]

    # audio section
    audio = config.get("audio", {})
    if audio:
        lines.append("[audio]")
        if audio.get("device") is not None:
            lines.append(f'device = "{_toml_escape(audio["device"])}"')
        else:
            lines.append("# device = (system default)")
        lines.append("")

    # transcriber section
    transcriber = config.get("transcriber", {})
    if transcriber:
        lines.append("[transcriber]")
        for key in ("model", "device", "compute_type"):
            if key in transcriber:
                lines.append(f'{key} = "{_toml_escape(transcriber[key])}"')
        lines.append("")

    return "\n".join(lines) + "\n"


def _step_config(step: int, total: int, config: dict) -> None:
    _header(step, total, "Write Configuration File")

    toml_content = _build_toml(config)

    print("  Preview:\n")
    for line in toml_content.splitlines():
        print(f"    {_dim(line)}")
    print()

    config_dir = Path.home() / ".config" / "yapper"
    config_file = config_dir / "config.toml"

    if config_file.exists():
        if not _confirm(f"{config_file} already exists. Overwrite?", default=False):
            print(_dim("  Skipping config write."))
            return

    if _confirm(f"Write config to {config_file}?", default=True):
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file.write_text(toml_content)
            print(f"  {_green('✓')} Config written to {config_file}")
        except OSError as exc:
            print(_red(f"  Failed to write config: {exc}"))
            print(_dim("  You can create the file manually with the content above."))
    else:
        print(_dim("  Skipped."))


# ── Step 5: Systemd service ──────────────────────────────────────────


_SERVICE_TEMPLATE = """\
[Unit]
Description=Yapper voice dictation daemon
After=graphical-session.target pipewire.service
Requires=graphical-session.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=3
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin

[Install]
WantedBy=default.target
"""


def _step_service(step: int, total: int, desktop: str) -> None:
    _header(step, total, "Systemd User Service")

    yapper_bin = shutil.which("yapper")
    if not yapper_bin:
        print(_yellow("  'yapper' not found in PATH."))
        print(_dim("  Make sure yapper is installed (e.g. pipx install . or uv pip install .)."))
        print(_dim("  You can set up the service later by re-running: yapper setup"))
        return

    print(f"  Yapper binary: {_bold(yapper_bin)}")

    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_file = service_dir / "yapper.service"

    # Check for bundled service file first
    bundled = Path(__file__).resolve().parent.parent.parent / "systemd" / "yapper.service"
    if bundled.exists():
        print(f"  Found bundled service file: {_dim(str(bundled))}")
        service_content = bundled.read_text()
    else:
        print(_dim("  Generating service file..."))
        service_content = _SERVICE_TEMPLATE.format(exec_start=yapper_bin)

    print(f"\n  Service file preview:\n")
    for line in service_content.strip().splitlines():
        print(f"    {_dim(line)}")
    print()

    if not _confirm(f"Install service to {service_file}?", default=True):
        print(_dim("  Skipped service installation."))
        return

    try:
        service_dir.mkdir(parents=True, exist_ok=True)
        service_file.write_text(service_content)
        print(f"  {_green('✓')} Service file written to {service_file}")
    except OSError as exc:
        print(_red(f"  Failed to write service file: {exc}"))
        return

    # Reload and enable
    if _confirm("Enable and start yapper service now?", default=True):
        try:
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["systemctl", "--user", "enable", "--now", "yapper"],
                check=True,
                capture_output=True,
            )
            print(f"  {_green('✓')} Service enabled and started.")
        except FileNotFoundError:
            print(_yellow("  systemctl not found — enable the service manually."))
            return
        except subprocess.CalledProcessError as exc:
            print(_red(f"  systemctl failed: {exc}"))
            print(_dim("  Try manually: systemctl --user enable --now yapper"))
            return

        # Verify it's running
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", "yapper"],
                capture_output=True,
                text=True,
            )
            status = result.stdout.strip()
            if status == "active":
                print(f"  {_green('✓')} Yapper daemon is running!")
            else:
                print(_yellow(f"  Service status: {status}"))
                print(_dim("  Check logs with: journalctl --user -u yapper -f"))
        except Exception:
            pass

        # Reload Hyprland if applicable
        if desktop == "hyprland" and shutil.which("hyprctl"):
            if _confirm("Reload Hyprland config to activate keybind?", default=True):
                try:
                    subprocess.run(
                        ["hyprctl", "reload"],
                        check=True,
                        capture_output=True,
                    )
                    print(f"  {_green('✓')} Hyprland reloaded.")
                except subprocess.CalledProcessError as exc:
                    print(_yellow(f"  hyprctl reload failed: {exc}"))
                except FileNotFoundError:
                    pass
    else:
        print(_dim("  You can start it later with:"))
        print(_dim("    systemctl --user daemon-reload"))
        print(_dim("    systemctl --user enable --now yapper"))


# ── Main entry point ─────────────────────────────────────────────────


def run_setup() -> None:
    """Run the interactive Yapper setup wizard."""
    total_steps = 5

    # Welcome banner
    print()
    print(_bold("  ╔══════════════════════════════════════╗"))
    print(_bold("  ║       Yapper Setup Wizard            ║"))
    print(_bold("  ║   Local voice dictation for Linux    ║"))
    print(_bold("  ╚══════════════════════════════════════╝"))
    print()

    # Detect platform
    from yapper.platform import (
        detect_desktop,
        detect_display_server,
        detect_gpu,
        detect_package_manager,
    )

    desktop = detect_desktop()
    display = detect_display_server()
    pkg_mgr = detect_package_manager()
    gpu = detect_gpu()

    print(f"  {_bold('Detected environment:')}")
    print(f"    Desktop:         {_cyan(desktop)}")
    print(f"    Display server:  {_cyan(display)}")
    print(f"    Package manager: {_cyan(pkg_mgr)}")
    print(f"    GPU:             {_cyan(gpu)}")
    print()

    if not _confirm("Continue with setup?", default=True):
        print(_dim("\n  Setup cancelled.\n"))
        return

    # Collect configuration from each step
    config: dict = {}

    # Step 1: Audio device
    try:
        result = _step_audio(1, total_steps)
        config.update(result)
    except (KeyboardInterrupt, EOFError):
        print(_dim("\n\n  Setup cancelled.\n"))
        return
    except Exception as exc:
        print(_red(f"\n  Audio step failed: {exc}"))
        print(_dim("  Continuing with defaults..."))
        config["audio"] = {"device": None}

    # Step 2: Model selection
    try:
        result = _step_model(2, total_steps, gpu)
        config.update(result)
    except (KeyboardInterrupt, EOFError):
        print(_dim("\n\n  Setup cancelled.\n"))
        return
    except Exception as exc:
        print(_red(f"\n  Model step failed: {exc}"))
        print(_dim("  Continuing with defaults..."))
        config["transcriber"] = {"model": "small.en", "device": "cpu", "compute_type": "int8"}

    # Step 3: Keybind
    try:
        result = _step_keybind(3, total_steps, desktop, display, pkg_mgr)
        config.update(result)
    except (KeyboardInterrupt, EOFError):
        print(_dim("\n\n  Setup cancelled.\n"))
        return
    except Exception as exc:
        print(_red(f"\n  Keybind step failed: {exc}"))
        print(_dim("  Continuing..."))

    # Step 4: Write config file
    try:
        _step_config(4, total_steps, config)
    except (KeyboardInterrupt, EOFError):
        print(_dim("\n\n  Setup cancelled.\n"))
        return
    except Exception as exc:
        print(_red(f"\n  Config step failed: {exc}"))

    # Step 5: Systemd service
    try:
        _step_service(5, total_steps, desktop)
    except (KeyboardInterrupt, EOFError):
        print(_dim("\n\n  Setup cancelled.\n"))
        return
    except Exception as exc:
        print(_red(f"\n  Service step failed: {exc}"))

    # Completion summary
    print()
    print("─" * 60)
    print(_bold(_green("  Setup complete!")))
    print("─" * 60)
    print()
    print(f"  {_bold('Summary:')}")
    audio_dev = config.get("audio", {}).get("device") or "system default"
    print(f"    Audio device:  {audio_dev}")
    model = config.get("transcriber", {}).get("model", "small.en")
    device = config.get("transcriber", {}).get("device", "cpu")
    print(f"    Model:         {model} ({device})")
    keybind = config.get("keybind", "not configured")
    print(f"    Keybind:       {keybind}")
    print()
    print(f"  {_dim('Config: ~/.config/yapper/config.toml')}")
    print(f"  {_dim('Logs:   journalctl --user -u yapper -f')}")
    print(f"  {_dim('Manual: yapper-ctl toggle  (to test)')}")
    print()
