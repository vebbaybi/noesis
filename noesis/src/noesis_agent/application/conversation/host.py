from __future__ import annotations

import hashlib
import time
from typing import Any

from noesis_agent.cognition.engine import CognitionEngine
from noesis_agent.cognition.providers import CognitionProviderRouter
from noesis_agent.application.ports import TextGenerationProvider
from noesis_agent.domain.contracts.cognition import CognitionRequest
from noesis_agent.domain.contracts.runtime import HostIntent, ResponseMode
from noesis_agent.domain.contracts.persona import HostReplyRequest, HostReplyResponse
from noesis_agent.shared.noesislogger import NoesisLogger


class HostService:
    def __init__(
        self,
        openai_service: TextGenerationProvider,
        *,
        cognition_engine: CognitionEngine,
        cognition_provider: CognitionProviderRouter | None = None,
        default_model: str | None = None,
        cache_ttl_seconds: int = 20,
    ) -> None:
        self.openai = openai_service
        self.engine = cognition_engine
        self.cognition_provider = cognition_provider
        self.default_model = default_model or "gpt-4.1-mini"
        self.cache_ttl_seconds = cache_ttl_seconds
        self.logger = NoesisLogger("noesis.service.host").logger
        self._reply_cache: dict[str, tuple[float, HostReplyResponse]] = {}

    def _cache_key(self, session_id: str, instruction: str, latest_context: str, transcript_tail: str) -> str:
        raw = "|".join([session_id, instruction, latest_context, transcript_tail[-800:]])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _get_cached_reply(self, key: str) -> HostReplyResponse | None:
        cached = self._reply_cache.get(key)
        if not cached:
            return None
        timestamp, response = cached
        if time.time() - timestamp > self.cache_ttl_seconds:
            self._reply_cache.pop(key, None)
            return None
        return response

    def _set_cached_reply(self, key: str, response: HostReplyResponse) -> None:
        self._reply_cache[key] = (time.time(), response)
        if len(self._reply_cache) > 200:
            oldest_key = min(self._reply_cache, key=lambda item: self._reply_cache[item][0])
            self._reply_cache.pop(oldest_key, None)

    def _clean_reply(self, text: str) -> str:
        cleaned = text.strip()
        for prefix in ("NOESIS:", "Host:", "Assistant:"):
            if cleaned.startswith(prefix):
                cleaned = cleaned.split(":", 1)[1].strip()
        return cleaned

    async def generate_reply(
        self,
        payload: HostReplyRequest,
        transcript_tail: str = "",
        session_title: str | None = None,
        session_id: str | None = None,
        room_id: str | None = None,
        current_speaker: str | None = None,
        dry_run: bool = False,
    ) -> HostReplyResponse:
        payload = HostReplyRequest.model_validate(payload.model_dump())
        effective_session_id = session_id or payload.session_id
        latest_context = payload.latest_context or payload.recent_context_summary
        transcript_tail = transcript_tail.strip()

        cognition_context = self.engine.build_context(
            instruction=payload.instruction,
            latest_context=latest_context,
            transcript_tail=transcript_tail,
            session_id=effective_session_id,
        )

        cache_key = self._cache_key(
            effective_session_id,
            payload.instruction,
            latest_context,
            transcript_tail,
        )
        if cached := self._get_cached_reply(cache_key):
            return cached

        system_parts = [
            "You are NOESIS, an advanced live host for X and Discord.",
            "Be sharp, fast, funny when useful, and highly grounded in crypto and Web3.",
            "Never present financial analysis as guaranteed advice.",
            *cognition_context.system_notes,
        ]
        voice_prompt = self.engine.voice_profiles.build_style_prompt(payload.personality if payload.personality != "default" else None)
        if voice_prompt:
            system_parts.append(voice_prompt)

        user_parts = [
            f"Session title: {session_title or 'Untitled NOESIS session'}",
            f"Instruction: {payload.instruction}",
            f"Requested length: {payload.length_preset}",
            f"Current speaker: {current_speaker or payload.current_speaker or 'unknown'}",
        ]
        if latest_context:
            user_parts.append(f"Recent context summary: {latest_context}")
        if transcript_tail:
            user_parts.append(f"Recent transcript:\n{transcript_tail}")
        if cognition_context.recall_hits:
            user_parts.append("Relevant local memory:\n- " + "\n- ".join(cognition_context.recall_hits[:4]))
        if cognition_context.finance.glossary_hits:
            user_parts.append("Finance grounding:\n- " + "\n- ".join(cognition_context.finance.glossary_hits))
        if cognition_context.humor.hooks:
            user_parts.append("Humor guidance:\n- " + "\n- ".join(cognition_context.humor.hooks[:2]))
        user_parts.append("Reply naturally for live delivery. Keep it direct, intelligent, and spoken-word ready.")

        try:
            max_tokens = 220 if payload.length_preset == "short" else 340 if payload.length_preset == "medium" else 520
            if self.cognition_provider is not None:
                cognition_response = await self.cognition_provider.generate(
                    CognitionRequest(
                        session_id=effective_session_id,
                        instruction=payload.instruction,
                        intent=HostIntent.ANSWER_DIRECTLY,
                        response_mode=ResponseMode.SHORT if payload.length_preset == "short" else ResponseMode.DEEP,
                        context="\n\n".join(user_parts),
                        transcript_tail=transcript_tail,
                        memories=cognition_context.recall_hits,
                        local_fallback=f"[OpenAI unavailable] {cognition_context.fallback_reply}",
                        metadata={
                            "system_prompt": "\n".join(system_parts),
                            "model": self.default_model,
                            "temperature": 0.68,
                            "max_tokens": max_tokens,
                            "room_id": room_id,
                            "dry_run": dry_run,
                        },
                    )
                )
                reply_text = cognition_response.text
            elif self.openai.is_enabled():
                reply_text = await self.openai.generate_text(
                    system_prompt="\n".join(system_parts),
                    user_prompt="\n\n".join(user_parts),
                    model=self.default_model,
                    temperature=0.68,
                    max_tokens=max_tokens,
                    room_id=room_id,
                    dry_run=dry_run,
                )
            else:
                reply_text = f"[OpenAI unavailable] {cognition_context.fallback_reply}"
            cleaned = self._clean_reply(reply_text)
        except Exception as exc:
            self.logger.warning("Host generation failed, using local cognition reply", extra={"error": str(exc)})
            cleaned = f"[OpenAI unavailable] {cognition_context.fallback_reply}"

        response = HostReplyResponse(
            text=cleaned,
            speakable_text=cleaned,
            tone_used=cognition_context.policy.style,
            personality_used=cognition_context.humor.style,
            suggested_length_category=payload.length_preset,
            contains_call_to_action="?" in cleaned or "check" in cleaned.lower(),
            should_pin=cognition_context.finance.active and cognition_context.finance.risk_level == "high",
        )
        self._set_cached_reply(cache_key, response)
        return response
