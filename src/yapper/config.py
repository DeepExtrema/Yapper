"""TOML configuration loading with defaults."""

from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


def _config_path() -> Path:
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return xdg / "yapper" / "config.toml"


@dataclass
class AudioConfig:
    device: str | None = None  # None = PipeWire default
    sample_rate: int = 16000
    channels: int = 1
    max_duration: int = 120  # seconds, auto-stop recording after this


@dataclass
class TranscriberConfig:
    model: str = "small.en"
    device: str = "cpu"
    compute_type: str = "int8"
    cpu_threads: int = 8
    beam_size: int = 5
    vad_filter: bool = True
    language: str = "en"


@dataclass
class ProcessorConfig:
    enabled: bool = False
    api_url: str = "http://127.0.0.1:8080"
    model: str = "qwen3-0.6b"
    temperature: float = 0.3
    max_tokens: int = 1024
    min_text_length: int = 10  # skip LLM for very short text
    timeout: float = 10.0


@dataclass
class InjectorConfig:
    method: str = "auto"  # auto | wtype | ydotool | clipboard
    clipboard_threshold: int = 200  # chars before switching to clipboard paste
    clipboard_paste_delay: float = 0.05  # seconds between copy and paste
    typing_delay: int = 0  # ms delay between keystrokes for wtype


@dataclass
class NotificationConfig:
    enabled: bool = True
    timeout: int = 2000  # ms


@dataclass
class DaemonConfig:
    socket_path: str = ""  # empty = $XDG_RUNTIME_DIR/yapper.sock
    debounce_ms: int = 200
    log_level: str = "INFO"


@dataclass
class DictionaryConfig:
    enabled: bool = False
    path: str = ""  # empty = ~/.config/yapper/dictionary.txt


@dataclass
class StreamingConfig:
    enabled: bool = True
    silence_duration_ms: int = 700
    min_speech_duration_ms: int = 250
    speech_threshold: float = 0.5
    speech_pad_ms: int = 100
    skip_llm: bool = True  # skip LLM in streaming for low latency


@dataclass
class Config:
    audio: AudioConfig = field(default_factory=AudioConfig)
    transcriber: TranscriberConfig = field(default_factory=TranscriberConfig)
    processor: ProcessorConfig = field(default_factory=ProcessorConfig)
    injector: InjectorConfig = field(default_factory=InjectorConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    dictionary: DictionaryConfig = field(default_factory=DictionaryConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)

    @property
    def socket_path(self) -> Path:
        if self.daemon.socket_path:
            return Path(self.daemon.socket_path)
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        return Path(runtime_dir) / "yapper.sock"


def _apply_dict(obj: object, data: dict) -> None:
    for key, value in data.items():
        if not hasattr(obj, key):
            log.warning("Unknown config key ignored: %s", key)
            continue
        current = getattr(obj, key)
        if isinstance(current, (AudioConfig, TranscriberConfig, ProcessorConfig,
                                InjectorConfig, NotificationConfig, DaemonConfig,
                                DictionaryConfig, StreamingConfig)) and isinstance(value, dict):
            _apply_dict(current, value)
        else:
            setattr(obj, key, value)


def load_config(path: Path | None = None) -> Config:
    """Load config from TOML file, falling back to defaults."""
    config = Config()
    config_file = path or _config_path()

    if config_file.exists():
        with open(config_file, "rb") as f:
            data = tomllib.load(f)
        _apply_dict(config, data)

    return config
