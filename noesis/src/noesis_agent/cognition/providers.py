from __future__ import annotations

from typing import Protocol

import httpx

from noesis_agent.integrations.llm.openai import OpenAIService
from noesis_agent.infrastructure.config.settings import Settings, settings
from noesis_agent.domain.contracts.cognition import (
    CognitionProviderStatus,
    CognitionRequest,
    CognitionResponse,
    ProviderCapability,
)
from noesis_agent.shared.errors import ConfigurationError, NoesisError
from noesis_agent.shared.noesislogger import NoesisLogger


class CognitionProvider(Protocol):
    name: str

    def capabilities(self) -> list[ProviderCapability]:
        ...

    def status(self) -> CognitionProviderStatus:
        ...

    async def generate(self, request: CognitionRequest) -> CognitionResponse:
        ...


class LocalLLMProvider:
    name = "local"

    def __init__(self, openai_service: OpenAIService, *, model: str | None = None) -> None:
        self.openai_service = openai_service
        self.model = model
        self.logger = NoesisLogger("noesis.cognition.local_provider").logger

    def capabilities(self) -> list[ProviderCapability]:
        return [
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.HOST_RESPONSE,
            ProviderCapability.MEMORY_AWARE,
            ProviderCapability.LOCAL_FALLBACK,
        ]

    def status(self) -> CognitionProviderStatus:
        llm_available = self.openai_service.is_enabled()
        return CognitionProviderStatus(
            provider_name=self.name,
            available=True,
            capabilities=self.capabilities(),
            reason="OpenAI generation available" if llm_available else "Local deterministic fallback available",
        )

    async def generate(self, request: CognitionRequest) -> CognitionResponse:
        if self.openai_service.is_enabled():
            system_prompt = str(
                request.metadata.get(
                    "system_prompt",
                    "You are NOESIS, a live AI host. Reply with concise, grounded, spoken-word-ready analysis.",
                )
            )
            user_prompt = self._build_user_prompt(request)
            text = await self.openai_service.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=str(request.metadata.get("model") or self.model or ""),
                temperature=float(request.metadata.get("temperature", 0.68)),
                max_tokens=int(request.metadata.get("max_tokens", 340)),
            )
            return CognitionResponse(
                request_id=request.request_id,
                provider_name=self.name,
                text=text,
                confidence=0.82,
                capabilities_used=[
                    ProviderCapability.TEXT_GENERATION,
                    ProviderCapability.HOST_RESPONSE,
                    ProviderCapability.MEMORY_AWARE,
                ],
                metadata={"llm_enabled": True},
            )

        fallback = self._local_response(request)
        return CognitionResponse(
            request_id=request.request_id,
            provider_name="local-fallback",
            text=fallback,
            confidence=0.48,
            used_fallback=True,
            capabilities_used=[ProviderCapability.LOCAL_FALLBACK, ProviderCapability.HOST_RESPONSE],
            metadata={"llm_enabled": False},
        )

    def _build_user_prompt(self, request: CognitionRequest) -> str:
        parts = [
            f"Intent: {request.intent.value}",
            f"Response mode: {request.response_mode.value}",
            f"Instruction: {request.instruction}",
        ]
        if request.context:
            parts.append(f"Context:\n{request.context}")
        if request.transcript_tail:
            parts.append(f"Recent transcript:\n{request.transcript_tail}")
        if request.memories:
            parts.append("Relevant memory:\n- " + "\n- ".join(request.memories[:8]))
        return "\n\n".join(parts)

    def _local_response(self, request: CognitionRequest) -> str:
        if request.local_fallback:
            return request.local_fallback.strip()

        context = request.context or request.transcript_tail
        context_hint = context.strip().splitlines()[-1][:240] if context.strip() else "the room is waiting for direction"
        if request.intent.value == "ask_follow_up":
            return f"[OpenAI unavailable] Quick follow-up: what matters most here, the opportunity, the risk, or the next move?"
        if request.intent.value in {"summarize", "close_show"}:
            return f"[OpenAI unavailable] Quick recap: {context_hint}. The clean move is to name the signal, frame the risk, and tee up the next decision."
        if request.intent.value == "moderate":
            return "[OpenAI unavailable] Let us tighten the stack: one point at a time, keep it useful, then hand the mic back."
        return f"[OpenAI unavailable] {context_hint}. My read: keep the take grounded, separate signal from hype, and do not overstate certainty."


class FutureELKAProvider:
    name = "elka"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        enabled: bool = False,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self._client = client
        self.logger = NoesisLogger("noesis.cognition.elka_provider").logger

    def capabilities(self) -> list[ProviderCapability]:
        return [
            ProviderCapability.ELKA_COGNITION,
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.HOST_RESPONSE,
            ProviderCapability.MEMORY_AWARE,
            ProviderCapability.MODERATION,
        ]

    def status(self) -> CognitionProviderStatus:
        if not self.enabled:
            return CognitionProviderStatus(
                provider_name=self.name,
                available=False,
                capabilities=self.capabilities(),
                reason="ELKA integration is disabled by configuration.",
            )
        if not self.base_url:
            return CognitionProviderStatus(
                provider_name=self.name,
                available=False,
                capabilities=self.capabilities(),
                reason="ELKA_BASE_URL is not configured.",
            )
        return CognitionProviderStatus(
            provider_name=self.name,
            available=True,
            capabilities=self.capabilities(),
            reason="ELKA endpoint configured.",
        )

    async def generate(self, request: CognitionRequest) -> CognitionResponse:
        status = self.status()
        if not status.available:
            raise ConfigurationError(status.reason, missing_key="ELKA_BASE_URL")

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = request.model_dump(mode="json")
        endpoint = f"{self.base_url}/v1/cognition/generate"

        if self._client is not None:
            response = await self._client.post(endpoint, json=payload, headers=headers, timeout=request.timeout_seconds)
        else:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(endpoint, json=payload, headers=headers, timeout=request.timeout_seconds)

        response.raise_for_status()
        data = response.json()
        data.setdefault("request_id", request.request_id)
        data.setdefault("provider_name", self.name)
        data.setdefault("capabilities_used", [ProviderCapability.ELKA_COGNITION.value])
        return CognitionResponse.model_validate(data)


class CognitionProviderRouter:
    def __init__(
        self,
        *,
        local_provider: LocalLLMProvider,
        elka_provider: FutureELKAProvider | None = None,
        preferred_provider: str = "auto",
    ) -> None:
        self.local_provider = local_provider
        self.elka_provider = elka_provider
        self.preferred_provider = preferred_provider
        self.logger = NoesisLogger("noesis.cognition.router").logger

    @classmethod
    def from_settings(cls, openai_service: OpenAIService, runtime_settings: Settings = settings) -> "CognitionProviderRouter":
        local_provider = LocalLLMProvider(openai_service, model=runtime_settings.default_model)
        elka_provider = FutureELKAProvider(
            base_url=runtime_settings.elka_base_url,
            api_key=runtime_settings.elka_api_key,
            enabled=runtime_settings.enable_elka,
            timeout_seconds=runtime_settings.llm_timeout_seconds,
        )
        return cls(
            local_provider=local_provider,
            elka_provider=elka_provider,
            preferred_provider=runtime_settings.cognition_provider,
        )

    def statuses(self) -> list[CognitionProviderStatus]:
        statuses = [self.local_provider.status()]
        if self.elka_provider is not None:
            statuses.insert(0, self.elka_provider.status())
        return statuses

    def primary(self) -> CognitionProvider:
        if self.preferred_provider == "elka":
            if self.elka_provider is None:
                raise ConfigurationError("ELKA provider was selected but no ELKA provider is configured.")
            return self.elka_provider
        if self.preferred_provider == "local":
            return self.local_provider
        if self.elka_provider is not None and self.elka_provider.status().available:
            return self.elka_provider
        return self.local_provider

    async def generate(self, request: CognitionRequest) -> CognitionResponse:
        provider = self.primary()
        try:
            return await provider.generate(request)
        except Exception as exc:
            if provider is self.local_provider:
                raise
            self.logger.warning(
                "Primary cognition provider failed; falling back to local provider",
                exc_info=exc,
                extra={"provider": getattr(provider, "name", "unknown"), "request_id": request.request_id},
            )
            response = await self.local_provider.generate(request)
            response.metadata["fallback_reason"] = str(exc)
            return response


__all__ = [
    "CognitionProvider",
    "CognitionProviderRouter",
    "FutureELKAProvider",
    "LocalLLMProvider",
]
