from __future__ import annotations

import time
from typing import Any

from noesis_agent.config.settings import settings
from noesis_agent.utils.errors import OpenAIAPIError, handle_noesis_error
from noesis_agent.utils.noesislogger import get_noesis_logger
from noesis_agent.utils.retry import RetryConfig, with_retry


logger = get_noesis_logger(__name__)


class OpenAIService:
    def __init__(self):
        self.client = None
        self._client_error_type: type[BaseException] = Exception

        if not settings.openai_api_key:
            logger.warning("No OpenAI API key configured; OpenAI features disabled")
            return

        try:
            from openai import AsyncOpenAI, OpenAIError

            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self._client_error_type = OpenAIError
            logger.info("OpenAI client initialized")
        except Exception as exc:
            self.client = None
            logger.warning("OpenAI SDK unavailable; API features disabled", error=str(exc))

    def is_enabled(self) -> bool:
        return self.client is not None

    @handle_noesis_error
    @with_retry(RetryConfig(max_retries=2, retry_on=(OpenAIAPIError,), reraise=False))
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 800,
        **_ignored: Any,
    ) -> str:
        if not self.is_enabled():
            logger.warning("OpenAI called while disabled")
            return "[OpenAI unavailable]"

        start = time.perf_counter()

        try:
            response = await self.client.chat.completions.create(
                model=model or settings.default_model or "gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content.strip()

            latency_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.info(
                "OpenAI text generation complete",
                extra={
                    "model": response.model,
                    "tokens_prompt": response.usage.prompt_tokens if response.usage else None,
                    "tokens_completion": response.usage.completion_tokens if response.usage else None,
                    "latency_ms": latency_ms,
                },
            )

            return content

        except Exception as exc:
            if self._client_error_type is not Exception and isinstance(exc, self._client_error_type):
                raise OpenAIAPIError(str(exc)) from exc
            raise

    async def create_realtime_session(
        self,
        instructions: str,
        voice: str = "alloy",
        modalities: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self.is_enabled():
            return {"error": "OpenAI not configured"}

        config = {
            "model": settings.realtime_model or "gpt-4o-realtime-preview",
            "modalities": modalities or ["text", "audio"],
            "instructions": instructions,
            "voice": voice,
            "turn_detection": {"type": "server_vad"},
        }

        logger.info("Realtime session config prepared", extra={"voice": voice})
        return {"session_config": config}
