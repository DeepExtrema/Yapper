"""Platform detection utilities for cross-desktop support."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

_KNOWN_DESKTOPS = {"hyprland", "gnome", "cinnamon", "kde", "sway"}

_INSTALL_COMMANDS: dict[str, str] = {
    "pacman": "sudo pacman -S",
    "apt": "sudo apt install",
    "dnf": "sudo dnf install",
    "zypper": "sudo zypper install",
}


def detect_desktop() -> str:
    """Detect the current desktop environment via $XDG_CURRENT_DESKTOP.

    Returns one of: hyprland, gnome, cinnamon, kde, sway, unknown.
    """
    raw = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

    # XDG_CURRENT_DESKTOP can be colon-separated (e.g. "ubuntu:GNOME")
    for token in raw.split(":"):
        # Handle X-Cinnamon → cinnamon
        normalised = token.strip().removeprefix("x-")
        if normalised in _KNOWN_DESKTOPS:
            return normalised
    return "unknown"


def detect_display_server() -> str:
    """Detect whether running under Wayland, X11, or unknown."""
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def detect_package_manager() -> str:
    """Detect the system package manager (pacman, apt, dnf, zypper, or unknown)."""
    for pm in ("pacman", "apt", "dnf", "zypper"):
        if shutil.which(pm):
            return pm
    return "unknown"


def detect_gpu() -> str:
    """Detect GPU acceleration: cuda, rocm, or cpu."""
    if shutil.which("nvidia-smi"):
        return "cuda"
    if shutil.which("rocm-smi") or Path("/opt/rocm").is_dir():
        return "rocm"
    return "cpu"


_SAFE_PACKAGE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._+\-]*$")


def suggest_install_cmd(package_manager: str, packages: list[str]) -> str | None:
    """Return an install command string, or None if the manager is unknown.

    Package names are validated to contain only safe characters.
    """
    prefix = _INSTALL_COMMANDS.get(package_manager)
    if prefix is None:
        return None
    for pkg in packages:
        if not _SAFE_PACKAGE_RE.match(pkg):
            return None
    return f"{prefix} {' '.join(packages)}"
