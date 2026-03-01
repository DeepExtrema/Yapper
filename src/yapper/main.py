"""Yapper daemon — local voice dictation for Linux."""

from __future__ import annotations

import asyncio
import logging
import signal
import time

import numpy as np

from yapper.audio import AudioRecorder
from yapper.config import load_config
from yapper.context import get_active_window
from yapper.dictionary import Dictionary
from yapper.hotkey import HotkeyServer
from yapper.injector import Injector
from yapper.notifications import Notifier
from yapper.processor import Processor
from yapper.transcriber import Transcriber

log = logging.getLogger("yapper")


class YapperDaemon:
    """Main daemon orchestrating all components."""

    def __init__(self) -> None:
        self._config = load_config()
        self._recorder = AudioRecorder(self._config.audio)
        self._transcriber = Transcriber(self._config.transcriber)
        self._processor = Processor(self._config.processor)
        self._injector = Injector(self._config.injector)
        self._notifier = Notifier(self._config.notification)
        self._dictionary = Dictionary(
            path=self._config.dictionary.path,
            enabled=self._config.dictionary.enabled,
        )
        self._server = HotkeyServer(self._config.socket_path, self._handle_command)
        self._processing = False
        self._last_command_time: float = 0

        # Streaming mode state
        self._vad = None
        self._segment_queue: asyncio.Queue[np.ndarray | None] = asyncio.Queue(maxsize=10)
        self._segment_worker_task: asyncio.Task | None = None

    async def _handle_command(self, command: str) -> str:
        now = time.monotonic()
        if now - self._last_command_time < self._config.daemon.debounce_ms / 1000:
            return "debounced"
        self._last_command_time = now

        match command:
            case "start":
                return await self._start_recording()
            case "stop":
                return await self._stop_recording()
            case "toggle":
                if self._recorder.is_recording:
                    return await self._stop_recording()
                else:
                    return await self._start_recording()
            case "status":
                state = "recording" if self._recorder.is_recording else "idle"
                if self._processing:
                    state = "processing"
                return state
            case "quit":
                asyncio.get_event_loop().call_soon(
                    lambda: asyncio.ensure_future(self._shutdown())
                )
                return "shutting down"
            case _:
                return f"unknown command: {command}"

    async def _start_recording(self) -> str:
        if self._recorder.is_recording:
            return "already recording"
        if self._processing:
            return "busy processing"

        def _on_max_duration() -> None:
            """Called from timer thread when max duration reached."""
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(self._stop_recording(), loop)

        if self._config.streaming.enabled and self._vad is not None:
            return await self._start_streaming(on_max_duration=_on_max_duration)

        self._recorder.start(on_max_duration=_on_max_duration)
        await self._notifier.recording_started()
        return "recording"

    async def _start_streaming(self, on_max_duration) -> str:
        """Start recording in streaming mode with VAD segmentation."""
        loop = asyncio.get_event_loop()
        self._vad.reset()

        # Drain any stale items from queue
        while not self._segment_queue.empty():
            try:
                self._segment_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        def _on_chunk(chunk: np.ndarray) -> None:
            """Called from audio thread — run VAD and enqueue segments."""
            segment = self._vad.process_chunk(chunk)
            if segment is not None:
                loop.call_soon_threadsafe(self._segment_queue.put_nowait, segment)

        self._segment_worker_task = asyncio.create_task(self._segment_worker())
        self._recorder.start(on_max_duration=on_max_duration, on_chunk=_on_chunk)
        await self._notifier.streaming_started()
        return "recording"

    async def _segment_worker(self) -> None:
        """Pull speech segments from queue, transcribe, and inject."""
        loop = asyncio.get_event_loop()
        context = await get_active_window()
        skip_llm = self._config.streaming.skip_llm

        while True:
            segment = await self._segment_queue.get()
            if segment is None:
                break

            duration = len(segment) / self._config.audio.sample_rate
            log.info("Streaming: transcribing %.2fs segment", duration)

            transcription_timeout = max(10.0, duration * 3)
            try:
                text = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, self._transcriber.transcribe, segment
                    ),
                    timeout=transcription_timeout,
                )
            except asyncio.TimeoutError:
                log.warning("Streaming segment transcription timed out")
                continue

            if not text:
                continue

            text = self._dictionary.apply(text)

            if not skip_llm:
                text = await self._processor.process(text, context)

            await self._injector.inject(text, context)

    async def _stop_recording(self) -> str:
        if not self._recorder.is_recording:
            return "not recording"

        is_streaming = (
            self._config.streaming.enabled
            and self._vad is not None
            and self._segment_worker_task is not None
        )

        if is_streaming:
            return await self._stop_streaming()

        self._processing = True
        await self._notifier.recording_stopped()

        # Capture audio
        audio = self._recorder.stop()
        if len(audio) == 0:
            self._processing = False
            await self._notifier.error("No audio captured")
            return "no audio"

        # Run pipeline in background so we can respond to client immediately
        asyncio.create_task(self._process_pipeline(audio))
        return "processing"

    async def _stop_streaming(self) -> str:
        """Stop streaming mode: flush VAD, drain queue, cancel worker."""
        self._processing = True
        audio = self._recorder.stop()

        # Flush remaining speech from VAD
        if self._vad is not None:
            remaining = self._vad.flush()
            if remaining is not None:
                try:
                    self._segment_queue.put_nowait(remaining)
                except asyncio.QueueFull:
                    log.warning("Segment queue full, dropping final segment")

        # Signal worker to stop
        try:
            self._segment_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

        # Wait for worker to drain
        if self._segment_worker_task is not None:
            try:
                await asyncio.wait_for(self._segment_worker_task, timeout=15.0)
            except asyncio.TimeoutError:
                log.warning("Segment worker timed out, cancelling")
                self._segment_worker_task.cancel()
            self._segment_worker_task = None

        self._processing = False
        await self._notifier.dictation_ended()
        return "done"

    async def _process_pipeline(self, audio) -> None:
        try:
            await asyncio.wait_for(self._run_pipeline(audio), timeout=90.0)
        except asyncio.TimeoutError:
            log.error("Pipeline timed out after 90s")
            await self._notifier.error("Pipeline timed out")
        except Exception:
            log.exception("Pipeline error")
            await self._notifier.error("Processing failed")
        finally:
            self._processing = False

    async def _run_pipeline(self, audio) -> None:
        # Detect context
        context = await get_active_window()

        # Log audio duration for diagnostics
        duration = len(audio) / self._config.audio.sample_rate
        log.info("Transcribing %.1fs of audio...", duration)

        # Transcribe (CPU-bound, run in executor) with timeout
        loop = asyncio.get_event_loop()
        transcription_timeout = max(10.0, duration * 3)
        try:
            text = await asyncio.wait_for(
                loop.run_in_executor(
                    None, self._transcriber.transcribe, audio
                ),
                timeout=transcription_timeout,
            )
        except asyncio.TimeoutError:
            log.error("Transcription timed out after %.0fs", transcription_timeout)
            await self._notifier.error("Transcription timed out")
            return

        if not text:
            await self._notifier.error("No speech detected")
            return

        # Apply dictionary substitutions
        text = self._dictionary.apply(text)

        # LLM post-processing
        text = await self._processor.process(text, context)

        # Inject text
        await self._injector.inject(text, context)
        await self._notifier.text_injected(text)

    async def _shutdown(self) -> None:
        log.info("Shutting down...")
        if self._recorder.is_recording:
            self._recorder.stop()
        if self._segment_worker_task is not None:
            self._segment_worker_task.cancel()
        await self._server.stop()
        await self._processor.close()
        # Stop the event loop
        asyncio.get_event_loop().stop()

    async def run(self) -> None:
        """Start the daemon."""
        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.ensure_future(self._shutdown()))

        # Pre-load whisper model
        log.info("Loading transcription model...")
        await loop.run_in_executor(None, self._transcriber.load_model)
        log.info("Model loaded")

        # Load VAD model if streaming enabled
        if self._config.streaming.enabled:
            log.info("Loading VAD model for streaming...")
            from yapper.vad import StreamingVAD
            self._vad = StreamingVAD(
                self._config.streaming,
                sample_rate=self._config.audio.sample_rate,
            )
            log.info("VAD model loaded, streaming mode enabled")
        else:
            log.info("Streaming disabled, batch mode only")

        log.info("Daemon ready")

        # Start socket server
        await self._server.start()

        # Run forever
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass


def main() -> None:
    """Entry point for the yapper daemon."""
    config = load_config()

    logging.basicConfig(
        level=getattr(logging, config.daemon.log_level.upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("Yapper starting...")
    daemon = YapperDaemon()
    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
