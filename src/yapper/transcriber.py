"""Speech-to-text via faster-whisper."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from yapper.config import TranscriberConfig

log = logging.getLogger(__name__)

# Lazy-loaded to avoid slow import at startup
_model = None


def _get_model(config: TranscriberConfig):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        log.info(
            "Loading whisper model %s (compute=%s, threads=%d)",
            config.model,
            config.compute_type,
            config.cpu_threads,
        )
        _model = WhisperModel(
            config.model,
            device=config.device,
            compute_type=config.compute_type,
            cpu_threads=config.cpu_threads,
        )
        log.info("Whisper model loaded")
    return _model


class Transcriber:
    """Wraps faster-whisper for speech-to-text."""

    def __init__(self, config: TranscriberConfig) -> None:
        self._config = config

    def load_model(self) -> None:
        """Pre-load the model (call at startup to avoid first-use latency)."""
        _get_model(self._config)

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio array to text.

        Args:
            audio: float32 numpy array at 16kHz mono.

        Returns:
            Transcribed text string, or empty string if nothing detected.
        """
        if len(audio) == 0:
            return ""

        model = _get_model(self._config)

        segments, info = model.transcribe(
            audio,
            beam_size=self._config.beam_size,
            language=self._config.language,
            vad_filter=self._config.vad_filter,
        )

        text = " ".join(segment.text.strip() for segment in segments)
        text = text.strip()

        if text:
            log.info(
                "Transcribed (%.1fs audio, prob=%.2f): %s",
                info.duration,
                info.language_probability,
                text[:100],
            )
        else:
            log.info("No speech detected in %.1fs audio", info.duration)

        return text
