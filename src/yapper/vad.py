"""Real-time Voice Activity Detection using Silero VAD ONNX model."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from yapper.config import StreamingConfig

log = logging.getLogger(__name__)

_NUM_SAMPLES = 512  # 32ms at 16kHz
_CONTEXT_SIZE = 64


class StreamingVAD:
    """Frame-by-frame Silero VAD that maintains LSTM state across calls.

    Unlike faster_whisper's SileroVADModel.__call__ which resets h/c each
    invocation, this wrapper keeps state for true streaming detection.
    """

    def __init__(self, config: StreamingConfig, sample_rate: int = 16000) -> None:
        self._config = config
        self._sample_rate = sample_rate
        self._samples_per_ms = sample_rate // 1000

        # ONNX session — reuse the model bundled with faster-whisper
        self._session = self._load_model()

        # LSTM state persisted across frames
        self._h = np.zeros((1, 1, 128), dtype="float32")
        self._c = np.zeros((1, 1, 128), dtype="float32")
        self._context = np.zeros((1, _CONTEXT_SIZE), dtype="float32")

        # Speech state machine
        self._in_speech = False
        self._speech_buf: list[np.ndarray] = []
        self._silence_samples = 0
        self._speech_samples = 0

        # Incoming audio accumulator (for partial chunks < 512 samples)
        self._pending = np.array([], dtype="float32")

    @staticmethod
    def _load_model():
        import os

        import onnxruntime
        from faster_whisper.utils import get_assets_path

        path = os.path.join(get_assets_path(), "silero_vad_v6.onnx")
        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.enable_cpu_mem_arena = False
        opts.log_severity_level = 4
        return onnxruntime.InferenceSession(
            path, providers=["CPUExecutionProvider"], sess_options=opts,
        )

    def reset(self) -> None:
        """Reset all state for a new recording session."""
        self._h = np.zeros((1, 1, 128), dtype="float32")
        self._c = np.zeros((1, 1, 128), dtype="float32")
        self._context = np.zeros((1, _CONTEXT_SIZE), dtype="float32")
        self._in_speech = False
        self._speech_buf.clear()
        self._silence_samples = 0
        self._speech_samples = 0
        self._pending = np.array([], dtype="float32")

    def _infer_frame(self, frame: np.ndarray) -> float:
        """Run a single 512-sample frame through the model, return speech probability."""
        # Prepend context to frame: shape (1, 576)
        input_data = np.concatenate([self._context, frame.reshape(1, -1)], axis=1)
        # Update context for next frame
        self._context = frame.reshape(1, -1)[..., -_CONTEXT_SIZE:]

        output, self._h, self._c = self._session.run(
            None, {"input": input_data, "h": self._h, "c": self._c},
        )
        return float(output[0])

    def process_chunk(self, chunk: np.ndarray) -> np.ndarray | None:
        """Process an audio chunk, return a speech segment when silence is detected.

        Args:
            chunk: Float32 audio samples (any length).

        Returns:
            Complete speech segment as float32 array, or None if still accumulating.
        """
        # Flatten to 1D
        if chunk.ndim > 1:
            chunk = chunk[:, 0]

        # Accumulate with any leftover from previous call
        if len(self._pending) > 0:
            audio = np.concatenate([self._pending, chunk])
        else:
            audio = chunk

        silence_threshold = self._config.silence_duration_ms * self._samples_per_ms
        min_speech = self._config.min_speech_duration_ms * self._samples_per_ms
        pad_samples = self._config.speech_pad_ms * self._samples_per_ms

        completed_segment = None
        offset = 0

        while offset + _NUM_SAMPLES <= len(audio):
            frame = audio[offset : offset + _NUM_SAMPLES]
            offset += _NUM_SAMPLES
            prob = self._infer_frame(frame)

            if prob >= self._config.speech_threshold:
                # Speech detected
                if not self._in_speech:
                    self._in_speech = True
                    self._silence_samples = 0
                    self._speech_samples = 0
                    # Add padding from before speech start
                    if pad_samples > 0 and len(self._speech_buf) == 0:
                        pad_start = max(0, offset - _NUM_SAMPLES - pad_samples)
                        if pad_start < offset - _NUM_SAMPLES:
                            self._speech_buf.append(audio[pad_start : offset - _NUM_SAMPLES])

                self._speech_buf.append(frame)
                self._speech_samples += _NUM_SAMPLES
                self._silence_samples = 0
            else:
                # Silence
                if self._in_speech:
                    self._speech_buf.append(frame)
                    self._silence_samples += _NUM_SAMPLES

                    if self._silence_samples >= silence_threshold:
                        # Speech segment complete
                        if self._speech_samples >= min_speech:
                            completed_segment = np.concatenate(self._speech_buf)
                            log.debug(
                                "VAD segment: %.2fs speech",
                                len(completed_segment) / self._sample_rate,
                            )
                        else:
                            log.debug("VAD: discarding short speech (%.0fms)", self._speech_samples / self._samples_per_ms)
                        self._speech_buf.clear()
                        self._in_speech = False
                        self._silence_samples = 0
                        self._speech_samples = 0

        # Save leftover samples for next call
        self._pending = audio[offset:] if offset < len(audio) else np.array([], dtype="float32")

        return completed_segment

    def flush(self) -> np.ndarray | None:
        """Flush any remaining speech when recording stops.

        Returns:
            Remaining speech segment, or None if nothing accumulated.
        """
        # Process any remaining pending samples by zero-padding
        if len(self._pending) > 0:
            pad_len = _NUM_SAMPLES - len(self._pending)
            padded = np.concatenate([self._pending, np.zeros(pad_len, dtype="float32")])
            self._pending = np.array([], dtype="float32")
            prob = self._infer_frame(padded)
            if prob >= self._config.speech_threshold and self._in_speech:
                self._speech_buf.append(padded)
                self._speech_samples += _NUM_SAMPLES

        if not self._speech_buf:
            return None

        min_speech = self._config.min_speech_duration_ms * self._samples_per_ms
        if self._speech_samples < min_speech:
            log.debug("VAD flush: discarding short speech (%.0fms)", self._speech_samples / self._samples_per_ms)
            self._speech_buf.clear()
            return None

        segment = np.concatenate(self._speech_buf)
        self._speech_buf.clear()
        self._in_speech = False
        self._silence_samples = 0
        self._speech_samples = 0
        log.debug("VAD flush: %.2fs segment", len(segment) / self._sample_rate)
        return segment
