"""Tests for config loading and merging."""

from pathlib import Path

from yapper.config import Config, _apply_dict, load_config


def test_defaults():
    config = Config()
    assert config.audio.sample_rate == 16000
    assert config.transcriber.model == "small.en"
    assert config.processor.enabled is False
    assert config.injector.method == "auto"
    assert config.streaming.enabled is True


def test_apply_dict_overwrites_flat():
    config = Config()
    _apply_dict(config, {"audio": {"sample_rate": 48000}})
    assert config.audio.sample_rate == 48000


def test_apply_dict_nested():
    config = Config()
    _apply_dict(config, {
        "transcriber": {"model": "large-v3", "beam_size": 3},
        "processor": {"enabled": True},
    })
    assert config.transcriber.model == "large-v3"
    assert config.transcriber.beam_size == 3
    assert config.processor.enabled is True
    # other defaults unchanged
    assert config.transcriber.device == "cpu"


def test_apply_dict_unknown_key_ignored(caplog):
    import logging
    config = Config()
    with caplog.at_level(logging.WARNING):
        _apply_dict(config, {"nonexistent_section": {"foo": "bar"}})
    assert "Unknown config key" in caplog.text


def test_load_config_missing_file():
    config = load_config(Path("/tmp/nonexistent_yapper_config.toml"))
    assert config.audio.sample_rate == 16000  # defaults


def test_load_config_from_file(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('[audio]\nsample_rate = 48000\n[transcriber]\nmodel = "tiny.en"\n')
    config = load_config(p)

    assert config.audio.sample_rate == 48000
    assert config.transcriber.model == "tiny.en"
    assert config.injector.method == "auto"  # default preserved
