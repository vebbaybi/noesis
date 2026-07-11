from __future__ import annotations

import re
from collections import OrderedDict

from noesis_agent.models.mentions import MentionEvent, MentionIntent, MentionResponse


class MentionService:
    """Platform-neutral, deterministic mention handling with optional LLM enhancement."""

    def __init__(self, openai_service, *, noesis_name: str = "Noesis", duplicate_limit: int = 1000) -> None:
        self.openai = openai_service
        self.noesis_name = noesis_name
        self.duplicate_limit = duplicate_limit
        self._seen: OrderedDict[str, None] = OrderedDict()

    async def handle(self, event: MentionEvent, *, dry_run: bool = True) -> MentionResponse:
        if event.event_id in self._seen:
            return self._result(event, "ignored", False, MentionIntent.UNCLEAR, reason="duplicate_event")
        self._remember(event.event_id)

        if not event.text:
            return self._result(event, "needs_clarification", True, MentionIntent.UNCLEAR,
                                text="What would you like Noesis to help with?", reason="empty_message")
        if len(event.attachments) > 20:
            return self._result(event, "unsupported", True, MentionIntent.UNCLEAR,
                                text="I can’t process that many attachments in one request.",
                                reason="attachment_limit", missing=["attachment_processing"])
        if not self._is_addressed(event):
            return self._result(event, "ignored", False, MentionIntent.UNCLEAR, reason="not_addressed_to_noesis")

        intent = self._classify(event.text)
        if intent is MentionIntent.CASUAL:
            return self._result(event, "ignored", False, intent, reason="casual_mention_without_task")
        if intent in {MentionIntent.HOSTILE, MentionIntent.UNCLEAR}:
            text = "I can help, but I need a clear question or task. What would you like me to do?"
            return self._result(event, "needs_clarification", True, intent, text=text, reason="unclear_or_hostile")

        fallback = self._fallback(intent, event)
        responder = "local-fallback"
        text = fallback
        provider_failed = False
        if self.openai.is_enabled():
            try:
                generated = await self.openai.generate_text(
                    system_prompt="You are Noesis. Answer only from supplied context; state limitations honestly. Be concise.",
                    user_prompt=self._prompt(intent, event), max_tokens=420,
                )
                if generated and generated != "[OpenAI unavailable]":
                    text, responder = generated, "openai"
                else:
                    provider_failed = True
            except Exception:
                provider_failed = True

        missing = [] if responder == "openai" else ["configured_llm_provider"]
        reason = "provider_failed_local_fallback" if provider_failed else "handled_locally"
        status = "dry_run" if dry_run else ("provider_unavailable" if provider_failed else "responded")
        return self._result(event, status, True, intent, text=text, responder=responder,
                            reason=reason, missing=missing)

    def _is_addressed(self, event: MentionEvent) -> bool:
        if event.mentioned is not None:
            return event.mentioned or event.is_reply_to_noesis
        return event.is_reply_to_noesis or bool(re.search(rf"(?i)(?:@|\b){re.escape(self.noesis_name)}\b", event.text))

    @staticmethod
    def _classify(text: str) -> MentionIntent:
        value = text.lower()
        if any(word in value for word in ("idiot", "stupid", "shut up", "hate you")):
            return MentionIntent.HOSTILE
        if any(word in value for word in ("bug", "broken", "crash", "error", "doesn't work", "not working")):
            return MentionIntent.BUG_REPORT
        if any(word in value for word in ("feature request", "add support", "could you add", "new feature")):
            return MentionIntent.FEATURE_REQUEST
        if any(word in value for word in ("contribut", "pull request", "good first issue", "development setup")):
            return MentionIntent.CONTRIBUTION_GUIDANCE
        if any(word in value for word in ("summar", "recap", "tl;dr", "tldr")):
            return MentionIntent.SUMMARIZE
        if any(word in value for word in ("explain", "what does", "why does", "how does")):
            return MentionIntent.EXPLAIN
        if any(word in value for word in ("project", "repository", "repo", "codebase")):
            return MentionIntent.PROJECT_HELP
        stripped = re.sub(r"(?i)@?noesis[,:]?", "", value).strip()
        if stripped in {"", "hi", "hello", "hey", "thanks", "thank you"}:
            return MentionIntent.CASUAL
        if "?" in value or any(value.startswith(word) for word in ("what", "when", "where", "who", "can", "do", "is")):
            return MentionIntent.QUESTION
        return MentionIntent.UNCLEAR

    @staticmethod
    def _fallback(intent: MentionIntent, event: MentionEvent) -> str:
        context = event.parent_text or ""
        if intent is MentionIntent.SUMMARIZE:
            if not context:
                return "Please include the conversation or message you want summarized; I can’t fetch thread history myself."
            return f"Local summary: {context[:700]}"
        if intent is MentionIntent.BUG_REPORT:
            return "Thanks for the bug report. Please share reproduction steps, expected behavior, actual behavior, and any sanitized logs."
        if intent is MentionIntent.FEATURE_REQUEST:
            return "Feature request noted. Please describe the user problem, desired behavior, and how we would verify it works."
        if intent is MentionIntent.CONTRIBUTION_GUIDANCE:
            return "Start with the repository README and test suite. Please share the repository context or issue; I don’t have access beyond what you provide."
        if intent is MentionIntent.EXPLAIN:
            return "I can explain it from the context you provide, but no external knowledge provider is configured in this runtime."
        if intent is MentionIntent.PROJECT_HELP:
            return "I can help with the project details you provide here; I don’t have implicit repository or server access."
        return "I can help answer that, but no external knowledge provider is configured. Please provide any needed context."

    @staticmethod
    def _prompt(intent: MentionIntent, event: MentionEvent) -> str:
        return f"Intent: {intent.value}\nMessage: {event.text}\nParent context: {event.parent_text or '[not provided]'}"

    def _remember(self, event_id: str) -> None:
        self._seen[event_id] = None
        self._seen.move_to_end(event_id)
        while len(self._seen) > self.duplicate_limit:
            self._seen.popitem(last=False)

    @staticmethod
    def _result(event, status, should_respond, intent, *, text="", responder="none", reason="", missing=None):
        return MentionResponse(event_id=event.event_id, status=status, should_respond=should_respond,
                               intent=intent, text=text, responder=responder, reason=reason,
                               platform=event.platform, missing_capabilities=missing or [],
                               metadata={"conversation_id": event.conversation_id, "channel_id": event.channel_id})
