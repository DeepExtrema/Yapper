"""LLM post-processing via llama-server HTTP API."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from yapper.config import ProcessorConfig
    from yapper.context import WindowContext

log = logging.getLogger(__name__)

_SYSTEM_PROMPTS: dict[str, str] = {
    "prose": (
        "Fix grammar, punctuation, and spelling in the following dictated text. "
        "Keep the original meaning and tone. Output only the corrected text, nothing else."
    ),
    "code": (
        "Fix grammar and punctuation in the following dictated text, which is a code comment "
        "or documentation. Preserve technical terminology exactly. Output only the corrected text."
    ),
    "chat": (
        "Lightly fix spelling in the following casual dictated message. "
        "Keep the informal tone and don't over-correct. Output only the fixed text."
    ),
    "email": (
        "Fix grammar, punctuation, and spelling in the following dictated email text. "
        "Make it professional but natural. Output only the corrected text."
    ),
    "terminal": (
        "Fix grammar and spelling in the following dictated text. "
        "Output only the corrected text."
    ),
}

_HEALTH_CACHE_TTL = 30.0


class Processor:
    """Post-process transcribed text using an LLM."""

    def __init__(self, config: ProcessorConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_url,
            timeout=httpx.Timeout(connect=2.0, read=config.timeout, write=5.0, pool=5.0),
        )
        self._healthy: bool | None = None
        self._health_checked_at: float = 0.0

    async def _check_health(self) -> bool:
        """Quick health check against llama-server, cached for 30s."""
        now = time.monotonic()
        if self._healthy is not None and (now - self._health_checked_at) < _HEALTH_CACHE_TTL:
            return self._healthy

        try:
            resp = await self._client.get("/health", timeout=httpx.Timeout(1.0))
            self._healthy = resp.status_code == 200
        except (httpx.HTTPError, OSError):
            self._healthy = False

        self._health_checked_at = now
        if not self._healthy:
            log.warning("LLM server unavailable, will skip processing")
        return self._healthy

    async def process(self, text: str, context: WindowContext) -> str:
        """Process text through the LLM for grammar/spelling correction.

        Returns original text if processing fails or is disabled.
        """
        if not self._config.enabled:
            return text

        if len(text) < self._config.min_text_length:
            log.debug("Text too short for LLM (%d chars), skipping", len(text))
            return text

        if not await self._check_health():
            return text

        system_prompt = _SYSTEM_PROMPTS.get(context.mode, _SYSTEM_PROMPTS["prose"])

        try:
            response = await asyncio.wait_for(
                self._client.post(
                    "/v1/chat/completions",
                    json={
                        "model": self._config.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text},
                        ],
                        "temperature": self._config.temperature,
                        "max_tokens": self._config.max_tokens,
                    },
                ),
                timeout=self._config.timeout + 5.0,
            )
            response.raise_for_status()
            data = response.json()

            result = data["choices"][0]["message"]["content"].strip()
            if result:
                log.info("LLM processed: %r → %r", text[:60], result[:60])
                return result

            log.warning("LLM returned empty response, using original")
            return text

        except (asyncio.TimeoutError, httpx.TimeoutException):
            log.warning("LLM request timed out, using original text")
            return text
        except (httpx.HTTPError, KeyError, IndexError) as e:
            log.warning("LLM processing failed (%s), using original text", e)
            return text

    async def close(self) -> None:
        await self._client.aclose()
