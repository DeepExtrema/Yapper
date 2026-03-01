"""Tests for platform detection module."""

from unittest.mock import patch

from yapper.platform import (
    detect_desktop,
    detect_display_server,
    detect_gpu,
    detect_package_manager,
    suggest_install_cmd,
)


# --- detect_desktop ---


@patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "Hyprland"}, clear=False)
def test_detect_desktop_hyprland():
    assert detect_desktop() == "hyprland"


@patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "GNOME"}, clear=False)
def test_detect_desktop_gnome():
    assert detect_desktop() == "gnome"


@patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "X-Cinnamon"}, clear=False)
def test_detect_desktop_cinnamon():
    assert detect_desktop() == "cinnamon"


@patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "KDE"}, clear=False)
def test_detect_desktop_kde():
    assert detect_desktop() == "kde"


@patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "sway"}, clear=False)
def test_detect_desktop_sway():
    assert detect_desktop() == "sway"


@patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "SomethingElse"}, clear=False)
def test_detect_desktop_unknown():
    assert detect_desktop() == "unknown"


@patch.dict("os.environ", {}, clear=True)
def test_detect_desktop_unset():
    assert detect_desktop() == "unknown"


# --- detect_display_server ---


@patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0"}, clear=False)
def test_detect_display_server_wayland():
    assert detect_display_server() == "wayland"


@patch.dict("os.environ", {"DISPLAY": ":0"}, clear=False)
def test_detect_display_server_x11():
    # Remove WAYLAND_DISPLAY if present to isolate X11
    with patch.dict("os.environ", {}, clear=False) as env:
        env.pop("WAYLAND_DISPLAY", None)
        assert detect_display_server() == "x11"


@patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}, clear=False)
def test_detect_display_server_prefers_wayland():
    assert detect_display_server() == "wayland"


@patch.dict("os.environ", {}, clear=True)
def test_detect_display_server_unknown():
    assert detect_display_server() == "unknown"


# --- detect_package_manager ---


@patch("yapper.platform.shutil.which")
def test_detect_package_manager_pacman(mock_which):
    mock_which.side_effect = lambda cmd: "/usr/bin/pacman" if cmd == "pacman" else None
    assert detect_package_manager() == "pacman"


@patch("yapper.platform.shutil.which")
def test_detect_package_manager_apt(mock_which):
    mock_which.side_effect = lambda cmd: "/usr/bin/apt" if cmd == "apt" else None
    assert detect_package_manager() == "apt"


@patch("yapper.platform.shutil.which")
def test_detect_package_manager_dnf(mock_which):
    mock_which.side_effect = lambda cmd: "/usr/bin/dnf" if cmd == "dnf" else None
    assert detect_package_manager() == "dnf"


@patch("yapper.platform.shutil.which")
def test_detect_package_manager_zypper(mock_which):
    mock_which.side_effect = lambda cmd: "/usr/bin/zypper" if cmd == "zypper" else None
    assert detect_package_manager() == "zypper"


@patch("yapper.platform.shutil.which")
def test_detect_package_manager_unknown(mock_which):
    mock_which.return_value = None
    assert detect_package_manager() == "unknown"


# --- detect_gpu ---


@patch("yapper.platform.shutil.which")
def test_detect_gpu_cuda(mock_which):
    mock_which.side_effect = lambda cmd: "/usr/bin/nvidia-smi" if cmd == "nvidia-smi" else None
    assert detect_gpu() == "cuda"


@patch("yapper.platform.Path.is_dir", return_value=True)
@patch("yapper.platform.shutil.which")
def test_detect_gpu_rocm_via_smi(mock_which, _mock_dir):
    def which_side(cmd):
        if cmd == "nvidia-smi":
            return None
        if cmd == "rocm-smi":
            return "/usr/bin/rocm-smi"
        return None
    mock_which.side_effect = which_side
    assert detect_gpu() == "rocm"


@patch("yapper.platform.Path.is_dir", return_value=True)
@patch("yapper.platform.shutil.which")
def test_detect_gpu_rocm_via_path(mock_which, mock_dir):
    mock_which.return_value = None
    assert detect_gpu() == "rocm"


@patch("yapper.platform.Path.is_dir", return_value=False)
@patch("yapper.platform.shutil.which")
def test_detect_gpu_cpu(mock_which, _mock_dir):
    mock_which.return_value = None
    assert detect_gpu() == "cpu"


# --- suggest_install_cmd ---


def test_suggest_install_cmd_pacman():
    result = suggest_install_cmd("pacman", ["python", "git"])
    assert result == "sudo pacman -S python git"


def test_suggest_install_cmd_apt():
    result = suggest_install_cmd("apt", ["python3", "git"])
    assert result == "sudo apt install python3 git"


def test_suggest_install_cmd_dnf():
    result = suggest_install_cmd("dnf", ["python3", "git"])
    assert result == "sudo dnf install python3 git"


def test_suggest_install_cmd_zypper():
    result = suggest_install_cmd("zypper", ["python3", "git"])
    assert result == "sudo zypper install python3 git"


def test_suggest_install_cmd_unknown():
    result = suggest_install_cmd("unknown", ["python3"])
    assert result is None
