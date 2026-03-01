"""Audio capture via sounddevice + PipeWire."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd

if TYPE_CHECKING:
    from yapper.config import AudioConfig

log = logging.getLogger(__name__)


class AudioRecorder:
    """Records audio from the microphone into a numpy buffer."""

    def __init__(self, config: AudioConfig) -> None:
        self._config = config
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._recording = False
        self._max_duration_timer: threading.Timer | None = None
        self._on_max_duration: Callable[[], None] | None = None
        self._on_chunk: Callable[[np.ndarray], None] | None = None

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            log.warning("Audio callback status: %s", status)
        with self._lock:
            if self._recording:
                chunk = indata.copy()
                self._chunks.append(chunk)
                if self._on_chunk is not None:
                    self._on_chunk(chunk)

    def start(
        self,
        on_max_duration: Callable[[], None] | None = None,
        on_chunk: Callable[[np.ndarray], None] | None = None,
    ) -> None:
        """Start recording audio.

        Args:
            on_max_duration: Callback fired when max recording duration is reached.
                             Called from a timer thread — should be thread-safe.
            on_chunk: Callback fired for each audio chunk from the mic.
                      Called from the audio thread — must be fast.
        """
        with self._lock:
            self._chunks.clear()
            self._recording = True

        self._on_max_duration = on_max_duration
        self._on_chunk = on_chunk

        self._stream = sd.InputStream(
            samplerate=self._config.sample_rate,
            channels=self._config.channels,
            dtype="float32",
            device=self._config.device,
            callback=self._callback,
        )
        self._stream.start()

        # Start max duration timer
        if self._config.max_duration > 0:
            self._max_duration_timer = threading.Timer(
                self._config.max_duration, self._on_max_duration_reached
            )
            self._max_duration_timer.daemon = True
            self._max_duration_timer.start()

        log.info("Recording started (max %ds)", self._config.max_duration)

    def _on_max_duration_reached(self) -> None:
        log.warning("Max recording duration (%ds) reached, auto-stopping", self._config.max_duration)
        if self._on_max_duration:
            self._on_max_duration()

    def stop(self) -> np.ndarray:
        """Stop recording and return the audio as a float32 numpy array."""
        if self._max_duration_timer is not None:
            self._max_duration_timer.cancel()
            self._max_duration_timer = None

        with self._lock:
            self._recording = False

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self._chunks:
                log.warning("No audio captured")
                return np.array([], dtype=np.float32)
            audio = np.concatenate(self._chunks, axis=0)
            self._chunks.clear()

        # Flatten to mono 1D array
        if audio.ndim > 1:
            audio = audio[:, 0]

        duration = len(audio) / self._config.sample_rate
        log.info("Recording stopped: %.1fs, %d samples", duration, len(audio))
        return audio

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording
