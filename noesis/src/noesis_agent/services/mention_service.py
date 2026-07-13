from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import asdict

from noesis_agent.models.mentions import MentionEvent, MentionIntent, MentionResponse
from noesis_agent.cognition.local_nlp import LocalNLP
from noesis_agent.memory.sqlite_memory import MemoryScope
from noesis_agent.cognition.intervention import InterventionPolicy, LocalModerationClassifier


class MentionService:
    """Platform-neutral, deterministic mention handling with optional LLM enhancement."""

    def __init__(self, openai_service, *, noesis_name: str = "Noesis", duplicate_limit: int = 1000,
                 local_nlp: LocalNLP | None = None, autonomous_memory=None,
                 observation_mode: str = "mentions_only", intervention_policy=None,
                 moderation_classifier=None, capability_registry=None) -> None:
        self.openai = openai_service
        self.noesis_name = noesis_name
        self.duplicate_limit = duplicate_limit
        self._seen: OrderedDict[tuple[str, str], None] = OrderedDict()
        self.local_nlp = local_nlp or LocalNLP()
        self.autonomous_memory = autonomous_memory
        self.observation_mode = observation_mode
        self.intervention_policy = intervention_policy or InterventionPolicy()
        self.moderation_classifier = moderation_classifier or LocalModerationClassifier()
        self.capability_registry = capability_registry
        self.ambient_response_enabled = False
        self.moderation_analysis_enabled = True
        self.metrics = {"messages_observed": 0, "messages_ignored": 0, "mentions_processed": 0,
                        "ambient_interventions": 0, "silent_observations": 0,
                        "duplicate_events": 0, "memory_candidates": 0,
                        "last_safe_intervention": None}

    async def handle(self, event: MentionEvent, *, dry_run: bool = True) -> MentionResponse:
        event_key = (event.platform, event.event_id)
        if event_key in self._seen:
            if not dry_run:
                self.metrics["duplicate_events"] += 1
                self.metrics["messages_ignored"] += 1
            return self._result(event, "ignored", False, MentionIntent.UNCLEAR, reason="duplicate_event")
        self._remember(event_key)

        if not event.text:
            return self._result(event, "needs_clarification", True, MentionIntent.UNCLEAR,
                                text="What would you like Noesis to help with?", reason="empty_message")
        if event.metadata.get("authorization_decision") == "rejected" or event.metadata.get("authorization_reason") in {"missing_guild", "channel_not_allowed"}:
            return self._result(event, "ignored", False, MentionIntent.UNCLEAR, reason="unauthorized")
        if not dry_run:
            self.metrics["messages_observed"] += 1
            if self._is_addressed(event):
                self.metrics["mentions_processed"] += 1
        if len(event.attachments) > 20:
            return self._result(event, "unsupported", True, MentionIntent.UNCLEAR,
                                text="I can’t process that many attachments in one request.",
                                reason="attachment_limit", missing=["attachment_processing"])
        scope = MemoryScope(event.platform, guild_id=event.metadata.get("guild_id"),
                            channel_id=event.channel_id, conversation_id=event.conversation_id,
                            user_id=None, visibility="conversation")
        memory_result = {"candidates": [], "accepted": [], "rejected": [], "decisions": []}
        memory_text = event.text
        if event.parent_text and re.search(r"(?i)\b(done|completed|finished|resolved)\b", event.text):
            memory_text = f"{event.parent_text} Status update: {event.text}"
        observation_mode = event.metadata.get("observation_mode", self.observation_mode)
        interpretation = self.local_nlp.interpret(event.text)
        event.metadata["local_interpretation"] = {
            "language": interpretation.language, "intent": interpretation.intent,
            "confidence": interpretation.intent_confidence, "dialogue_act": interpretation.dialogue_act,
            "topics": interpretation.topics, "sentiment": interpretation.sentiment,
            "emotion": interpretation.emotion, "limitations": list(interpretation.limitations),
        }
        moderation = self.moderation_classifier.classify(event.text) if self.moderation_analysis_enabled else None
        extracted = self.autonomous_memory.extractor.extract(
            memory_text, platform=event.platform, event_id=event.event_id, scope=scope
        ) if self.autonomous_memory is not None else []
        intervention = self.intervention_policy.decide(
            mentioned=self._is_addressed(event), observation_mode=observation_mode,
            has_candidate=bool(extracted), moderation=moderation,
            confidence=interpretation.intent_confidence,
            direct_question=event.text.rstrip().endswith("?"),
            ambient_response_enabled=bool(event.metadata.get("ambient_response_enabled",
                                                              self.ambient_response_enabled)))
        event.metadata["intervention"] = asdict(intervention)
        event.metadata["moderation"] = asdict(moderation) if moderation else None
        if self.capability_registry is not None:
            event.metadata["capability_route"] = self.capability_registry.route(
                platform=event.platform, text=event.text, intent=interpretation.intent)
        if moderation is not None and not dry_run and self.autonomous_memory is not None:
            self.autonomous_memory.record_moderation_outcome(
                alert=intervention.outcome == "notify_moderators", signal=asdict(moderation))
        if dry_run and self.autonomous_memory is not None:
            memory_result["candidates"] = [asdict(candidate) for candidate in extracted]
            memory_result["decisions"] = [asdict(self.autonomous_memory.write_gate.evaluate(
                candidate, authorized=True)) for candidate in extracted]
        elif self.autonomous_memory is not None and intervention.should_remember:
            memory_result = await self.autonomous_memory.process(memory_text, scope=scope,
                                                                  platform=event.platform, event_id=event.event_id)
        if not dry_run:
            self.metrics["memory_candidates"] += len(extracted)
            if not self._is_addressed(event):
                if intervention.should_respond or intervention.should_moderate or intervention.should_remember:
                    self.metrics["ambient_interventions"] += 1
                    self.metrics["last_safe_intervention"] = {
                        "event_id": event.event_id, "outcome": intervention.outcome,
                        "reason": intervention.reason}
                else:
                    self.metrics["silent_observations"] += 1
        if not self._is_addressed(event) and not intervention.should_respond:
            if not dry_run:
                self.metrics["messages_ignored"] += 1
            response = self._result(event, "ignored", False, MentionIntent.UNCLEAR,
                                    reason="ambient_observation" if observation_mode != "mentions_only"
                                    else "not_addressed_to_noesis")
            response.metadata["memory"] = self._memory_metadata(memory_result)
            response.metadata["intervention"] = asdict(intervention)
            response.metadata["moderation"] = asdict(moderation) if moderation else None
            if "capability_route" in event.metadata:
                response.metadata["capability_route"] = event.metadata["capability_route"]
            return response
        intent = self._classify(event.text)
        if intent is MentionIntent.CASUAL:
            result = self._result(event, "ignored", False, intent, reason="casual_mention_without_task")
            result.metadata.update(memory=self._memory_metadata(memory_result),
                                   intervention=asdict(intervention),
                                   moderation=asdict(moderation) if moderation else None)
            if "capability_route" in event.metadata:
                result.metadata["capability_route"] = event.metadata["capability_route"]
            return result
        if intent in {MentionIntent.HOSTILE, MentionIntent.UNCLEAR}:
            text = "I can help, but I need a clear question or task. What would you like me to do?"
            result = self._result(event, "needs_clarification", True, intent, text=text,
                                  reason="unclear_or_hostile")
            result.metadata.update(memory=self._memory_metadata(memory_result),
                                   intervention=asdict(intervention),
                                   moderation=asdict(moderation) if moderation else None)
            if "capability_route" in event.metadata:
                result.metadata["capability_route"] = event.metadata["capability_route"]
            return result

        memories = await self.autonomous_memory.retrieve(event.text, scope) if self.autonomous_memory is not None and not dry_run else []
        event.metadata["retrieved_memories"] = memories
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
        result = self._result(event, status, True, intent, text=text, responder=responder,
                              reason=reason, missing=missing)
        result.metadata["memory"] = {**self._memory_metadata(memory_result), "retrieved": len(memories)}
        result.metadata["intervention"] = asdict(intervention)
        result.metadata["moderation"] = asdict(moderation) if moderation else None
        if "capability_route" in event.metadata:
            result.metadata["capability_route"] = event.metadata["capability_route"]
        return result

    def health(self) -> dict:
        observed = self.metrics["messages_observed"]
        return {**self.metrics,
                "intervention_rate": round(self.metrics["ambient_interventions"] / observed, 4)
                                     if observed else 0.0}

    @staticmethod
    def _memory_metadata(result: dict) -> dict:
        candidates = [{"type": item["candidate_type"], "confidence": item["confidence"],
                       "importance": item["importance"], "actionability": item["actionability"],
                       "future_relevance": item.get("future_relevance"),
                       "novelty": item.get("novelty"), "stability": item.get("stability"),
                       "retention_class": item.get("retention_class"),
                       "subject": item.get("subject"), "predicate": item.get("predicate"),
                       "storage_explanation": item.get("storage_explanation"),
                       "score_breakdown": item.get("score_breakdown", {}),
                       "rejection_reason": item.get("rejection_reason")}
                      for item in result["candidates"][:10]]
        return {"candidate_count": len(result["candidates"]), "candidates": candidates,
                "persisted": len(result["accepted"]),
                "decisions": result.get("decisions", [])[:10],
                "rejected": [{"type": item["candidate_type"], "reason": item["rejection_reason"]}
                             for item in result["rejected"]]}

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
        memories = event.metadata.get("retrieved_memories") or []
        evidence = event.metadata.get("evidence") or []
        if memories:
            remembered = memories[0].content
            if evidence:
                facts = evidence[0].get("facts", {})
                current = facts.get("guild_name") or facts.get("channel_name")
                if current:
                    return f"From authorized memory: {remembered} Current platform context: {current}."
            if any(memory.memory_type == "blocker" for memory in memories):
                return "The current blocker I remember is: " + memories[0].content
            if any(memory.memory_type == "decision" for memory in memories):
                return "The active decision I remember is: " + memories[0].content
            return "From the relevant authorized memory: " + memories[0].content
        if evidence:
            facts = evidence[0].get("facts", {})
            lower = event.text.lower()
            if "created" in lower and "server" in lower:
                owner = facts.get("guild_owner_display_name")
                qualifier = f" The current server owner is {owner}." if owner else ""
                return "Discord does not expose reliable original-creator history, so I cannot confirm who originally created this server." + qualifier
            if any(term in lower for term in ("owns this server", "server owner", "runs this guild")):
                owner = facts.get("guild_owner_display_name") or facts.get("guild_owner_id")
                return f"The current server owner is {owner}." if owner else "I cannot identify the current server owner from the authorized gateway context."
            if any(term in lower for term in ("how many members", "member count", "how many people are here")) and facts.get("member_count") is not None:
                return f"This server currently has {facts['member_count']} members."
            if any(term in lower for term in ("see this channel", "access this channel", "channel have")):
                if facts.get("cached_visible_member_count") is not None:
                    return f"{facts['cached_visible_member_count']} cached members can currently access this channel."
                return "I cannot calculate channel visibility accurately because the member cache is incomplete or channel-permission data is unavailable."
            if any(term in lower for term in ("earlier messages", "channel history", "what happened earlier")):
                return "I cannot read earlier messages because bounded message-history access is not available in this runtime."
            if "what channel" in lower and facts.get("channel_name"):
                guild = f" in the {facts['guild_name']} server" if facts.get("guild_name") else ""
                return f"This is the #{facts['channel_name']} {facts.get('channel_type', 'channel')}{guild}."
            available = [f"{key.replace('_', ' ')}: {value}" for key, value in facts.items()]
            if available:
                return "Current authorized Discord context — " + "; ".join(available) + "."
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

    def _remember(self, event_key: tuple[str, str]) -> None:
        self._seen[event_key] = None
        self._seen.move_to_end(event_key)
        while len(self._seen) > self.duplicate_limit:
            self._seen.popitem(last=False)

    @staticmethod
    def _result(event, status, should_respond, intent, *, text="", responder="none", reason="", missing=None):
        return MentionResponse(event_id=event.event_id, status=status, should_respond=should_respond,
                               intent=intent, text=text, responder=responder, reason=reason,
                               platform=event.platform, missing_capabilities=missing or [],
                               metadata={"conversation_id": event.conversation_id, "channel_id": event.channel_id,
                                         **({"local_interpretation": event.metadata["local_interpretation"]}
                                            if "local_interpretation" in event.metadata else {})})
