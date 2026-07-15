from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import asdict

from noesis_agent.domain.contracts.mentions import MentionEvent, MentionIntent, MentionResponse
from noesis_agent.cognition.nlu.interpreter import LocalNLP
from noesis_agent.memory.sqlite_memory import MemoryScope, ScopedMemoryStore
from noesis_agent.cognition.intervention import InterventionPolicy, LocalModerationClassifier


class MentionService:
    """Platform-neutral, deterministic mention handling with optional LLM enhancement."""

    def __init__(self, openai_service, *, noesis_name: str = "Noesis", duplicate_limit: int = 1000,
                 local_nlp: LocalNLP | None = None, autonomous_memory=None,
                 observation_mode: str = "mentions_only", intervention_policy=None,
                 moderation_classifier=None, capability_registry=None, intelligence_pipeline=None) -> None:
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
        self.intelligence_pipeline = intelligence_pipeline
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
                                text="I canâ€™t process that many attachments in one request.",
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
            "emotion": interpretation.emotion, "ranked_intents": list(interpretation.ranked_intents),
            "limitations": list(interpretation.limitations),
        }
        moderation = self.moderation_classifier.classify(event.text) if self.moderation_analysis_enabled else None
        moderation_first = moderation is not None and moderation.outcome != "no_action"
        extracted = [] if moderation_first else self.autonomous_memory.extractor.extract(
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
        intent = self._classify(event.text, interpretation.intent)
        if intent is MentionIntent.MODERATION_REPORT:
            text = self._moderation_report_response(event)
            result = self._result(event, "dry_run" if dry_run else "responded", True, intent,
                                  text=text, responder="local-fallback", reason="moderation_context_report")
            return self._finish(result, event, memory_result, moderation, [],
                                provider_reason="not_needed_local_moderation")
        if moderation_first:
            text = ("I understand you're frustrated. Iâ€™m not going to punish anyone automatically, "
                    "but I can classify this as a moderation signal and explain what I can currently "
                    "verify from the recent channel context.")
            result = self._result(event, "dry_run" if dry_run else "responded", True,
                                  MentionIntent.HOSTILE, text=text, responder="local-fallback",
                                  reason="direct_hostility_deescalation")
            return self._finish(result, event, memory_result, moderation, [],
                                provider_reason="memory_retrieval_suppressed_for_moderation")
        if intent is MentionIntent.PROJECT_FACT and memory_result["candidates"]:
            candidate = memory_result["candidates"][0]
            fact = candidate.get("canonical_content") or candidate.get("content")
            persisted = bool(memory_result.get("accepted")) or dry_run
            text = (f"Noted for this scope: {fact} I will treat that as a project fact unless it is corrected later."
                    if persisted else f"I recognized this project fact, but it was not stored: {fact}")
            result = self._result(event, "dry_run" if dry_run else "responded", True, intent,
                                  text=text, responder="local-fallback", reason="project_fact_understood")
            return self._finish(result, event, memory_result, moderation, [],
                                provider_reason="not_needed_local_fact")
        if intent is MentionIntent.CASUAL:
            result = self._result(event, "ignored", False, intent, reason="casual_mention_without_task")
            result.metadata.update(memory=self._memory_metadata(memory_result),
                                   intervention=asdict(intervention),
                                   moderation=asdict(moderation) if moderation else None)
            if "capability_route" in event.metadata:
                result.metadata["capability_route"] = event.metadata["capability_route"]
            return result
        if intent is MentionIntent.FOLLOW_UP_REPAIR:
            fallback = self._fallback(intent, event)
            result = self._result(event, "dry_run" if dry_run else "responded", True, intent,
                                  text=fallback, responder="local-fallback", reason="answer_repair")
            return self._finish(result, event, memory_result, moderation, [],
                                provider_reason="not_needed_local_repair")
        if intent is MentionIntent.HOSTILE:
            text = "I understand you're frustrated. I can acknowledge the criticism and explain what failed without escalating the conversation."
            result = self._result(event, "dry_run" if dry_run else "responded", True, intent,
                                  text=text, responder="local-fallback", reason="criticism_deescalation")
            return self._finish(result, event, memory_result, moderation, [],
                                provider_reason="memory_retrieval_suppressed_for_criticism")
        if intent is MentionIntent.UNCLEAR:
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
        event.metadata["retrieval_diagnostics"] = {
            "query_topics": interpretation.topics,
            "match_count": len(memories),
            "match_reasons": [self._memory_match_reason(event.text, memory) for memory in memories[:5]],
        }

        fallback = self._fallback(intent, event)
        responder = "local-fallback"
        text = fallback
        provider_failed = False
        local_answer_available = bool(
            memories or event.metadata.get("evidence") or event.parent_text or
            event.metadata.get("recent_context") or
            event.metadata.get("capability_route", {}).get("matches")
        )
        if self.intelligence_pipeline is not None and not dry_run:
            from noesis_agent.domain.contracts.intelligence import DirectResponse, IntelligenceRequest

            tenant_id = str(event.metadata.get("guild_id") or event.conversation_id or event.channel_id)
            intelligence = await self.intelligence_pipeline.process(IntelligenceRequest(
                event_id=event.event_id, tenant_id=tenant_id,
                user_id=str(event.user_id or "anonymous"),
                conversation_id=str(event.conversation_id or event.channel_id), text=event.text,
                authorized_capabilities=frozenset(event.metadata.get("authorized_capabilities", [])),
                local_only=bool(event.metadata.get("local_only", False)),
            ))
            if isinstance(intelligence.outcome, DirectResponse):
                text = intelligence.outcome.text
            else:
                text = str(getattr(intelligence.outcome, "question",
                                   getattr(intelligence.outcome, "reason", fallback)))
            responder = intelligence.provider
            result = self._result(event, "responded", True, intent, text=text, responder=responder,
                                  reason="canonical_intelligence_pipeline")
            result.metadata["intelligence"] = intelligence.model_dump(mode="json")
            return self._finish(result, event, memory_result, moderation, memories,
                                provider_reason="canonical_intelligence_pipeline")
        if self.openai.is_enabled() and not local_answer_available:
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
        reason = "provider_failed_local_fallback" if provider_failed else \
                 "local_context_preferred" if local_answer_available else "handled_locally"
        status = "dry_run" if dry_run else ("provider_unavailable" if provider_failed else "responded")
        result = self._result(event, status, True, intent, text=text, responder=responder,
                              reason=reason, missing=missing)
        result.metadata["memory"] = {**self._memory_metadata(memory_result), "retrieved": len(memories)}
        result.metadata["intervention"] = asdict(intervention)
        result.metadata["moderation"] = asdict(moderation) if moderation else None
        if "capability_route" in event.metadata:
            result.metadata["capability_route"] = event.metadata["capability_route"]
        result.metadata["retrieval"] = event.metadata.get("retrieval_diagnostics", {})
        result.metadata["response_plan"] = {"provider": responder, "provider_reason": reason,
                                            "used_recent_context": bool(event.metadata.get("recent_context")),
                                            "recent_context_buffer": event.metadata.get("recent_context_buffer", {}),
                                            "omitted_capability_repair": intent is MentionIntent.FOLLOW_UP_REPAIR,
                                            "compound_capabilities": [item["capability_id"] for item in
                                                event.metadata.get("capability_route", {}).get("matches", [])]}
        return result

    def _finish(self, result, event, memory_result, moderation, memories, *, provider_reason: str):
        result.metadata.update(memory={**self._memory_metadata(memory_result), "retrieved": len(memories)},
                               intervention=event.metadata.get("intervention", {}),
                               moderation=asdict(moderation) if moderation else None,
                               capability_route=event.metadata.get("capability_route", {}),
                               retrieval=event.metadata.get("retrieval_diagnostics", {}),
                               response_plan={
                                   "provider": "local-fallback", "provider_reason": provider_reason,
                                   "used_recent_context": bool(event.metadata.get("recent_context")),
                                   "recent_context_buffer": event.metadata.get("recent_context_buffer", {}),
                                   "omitted_capability_repair": result.intent is MentionIntent.FOLLOW_UP_REPAIR,
                                   "compound_capabilities": [item["capability_id"] for item in
                                       event.metadata.get("capability_route", {}).get("matches", [])],
                               })
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
    def _classify(text: str, model_intent: str | None = None) -> MentionIntent:
        value = text.lower()
        # Conversation repair has precedence over the subject of the missed
        # question.  Otherwise "I also asked how many members" is misrouted as
        # a fresh member-count request and repeats the original failure.
        if re.search(r"\b(you missed|i also asked|but i asked|i asked (?:you )?(?:two|2) questions?|"
                     r"second is|answer the other part|that is not what i asked|no,? i mean|"
                     r"why did you say|well i also asked)\b", value):
            return MentionIntent.FOLLOW_UP_REPAIR
        if (re.search(r"\b(?:the\s+)?(?:version\s+)?(?:release|launch|milestone).*(?:january|february|march|april|may|june|july|august|september|october|november|december)\s*\d{1,2}(?:st|nd|rd|th)?\b", value)
                and "?" not in value):
            return MentionIntent.PROJECT_FACT
        model_mapping = {
            "moderation_report": MentionIntent.MODERATION_REPORT,
            "hostile": MentionIntent.HOSTILE,
            "follow_up_repair": MentionIntent.FOLLOW_UP_REPAIR,
            "project_fact": MentionIntent.PROJECT_FACT,
            "bug_report": MentionIntent.BUG_REPORT,
            "feature_request": MentionIntent.FEATURE_REQUEST,
            "summarize": MentionIntent.SUMMARIZE,
            "explain": MentionIntent.EXPLAIN,
            "greeting": MentionIntent.CASUAL,
            "unclear": MentionIntent.UNCLEAR,
            "discord_owner": MentionIntent.QUESTION,
            "discord_creator": MentionIntent.QUESTION,
            "discord_member_count": MentionIntent.QUESTION,
            "discord_channel": MentionIntent.QUESTION,
            "discord_thread": MentionIntent.QUESTION,
            "package_decision_query": MentionIntent.QUESTION,
            "release_query": MentionIntent.QUESTION,
            "general_question": MentionIntent.QUESTION,
            "memory_write": MentionIntent.PROJECT_FACT,
            "memory_forget": MentionIntent.PROJECT_HELP,
            "help": MentionIntent.QUESTION,
        }
        if model_intent in model_mapping:
            return model_mapping[model_intent]
        if (re.search(r"\b(somebody|someone|that message|this message|this link)\b.*\b(cursing|swearing|harass|abusive|abuse|spam|scam|leaked|token|suspicious|insult)\b", value)
                or re.search(r"\b(?:letting|allows?|quiet while).*(?:curse|cursing|abusive language|insult)", value)
                or re.search(r"\b(?:people|everyone|users?).*(?:cursing|using abusive|insulting)", value)
                or "look at the message above" in value):
            return MentionIntent.MODERATION_REPORT
        if re.search(r"\b(?:the\s+)?(?:version\s+)?(?:release|launch|milestone).*(?:january|february|march|april|may|june|july|august|september|october|november|december)\s*\d{1,2}(?:st|nd|rd|th)?\b", value) and "?" not in value:
            return MentionIntent.PROJECT_FACT
        if any(word in value for word in ("idiot", "stupid", "shut up", "hate you", "complete failure",
                                          "you are useless", "you're useless", "fuck you", "cunt")):
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
        if intent is MentionIntent.FOLLOW_UP_REPAIR:
            answer = MentionService._discord_fact_answer(event)
            missed = "the creator part" if "created" in event.text.lower() else "that part"
            return f"You're right â€” I missed {missed}. " + (answer or "Please repeat the missing part so I can answer it directly.")
        package_answer = MentionService._package_decision_answer(event, memories)
        if package_answer:
            return package_answer
        fact_answer = MentionService._discord_fact_answer(event)
        if fact_answer:
            return fact_answer
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
                return "Current authorized Discord context â€” " + "; ".join(available) + "."
        context = event.parent_text or ""
        if intent is MentionIntent.SUMMARIZE:
            if not context:
                return "Please include the conversation or message you want summarized; I canâ€™t fetch thread history myself."
            return f"Local summary: {context[:700]}"
        if intent is MentionIntent.BUG_REPORT:
            return "Thanks for the bug report. Please share reproduction steps, expected behavior, actual behavior, and any sanitized logs."
        if intent is MentionIntent.FEATURE_REQUEST:
            return "Feature request noted. Please describe the user problem, desired behavior, and how we would verify it works."
        if intent is MentionIntent.CONTRIBUTION_GUIDANCE:
            return "Start with the repository README and test suite. Please share the repository context or issue; I donâ€™t have access beyond what you provide."
        if intent is MentionIntent.EXPLAIN:
            recent = event.metadata.get("recent_context") or []
            if event.parent_text:
                return f"You are referring to: {event.parent_text[:700]}"
            if recent:
                return "From the recent authorized context, the latest relevant message was: " + str(recent[-1].get("text", ""))[:700]
            return "I need the specific message or idea you want explained. Reply to it or quote the relevant part."
        if intent is MentionIntent.PROJECT_HELP:
            return "I can help with the project details you provide here; I donâ€™t have implicit repository or server access."
        return "I do not have enough authorized local context to answer that reliably. Please add the specific detail you want me to use."

    @staticmethod
    def _discord_fact_answer(event: MentionEvent) -> str | None:
        evidence = event.metadata.get("evidence") or []
        if not evidence:
            return None
        facts = evidence[0].get("facts", {})
        lower = event.text.lower()
        model_intent = (event.metadata.get("local_interpretation") or {}).get("intent")
        clauses = []
        asks_owner = model_intent == "discord_owner" or bool(re.search(r"\b(owns this server|server owner|runs this guild|who owns|who runs)\b", lower))
        asks_creator = model_intent == "discord_creator" or bool(re.search(r"\b(who created|original creator|server creator|who made)\b", lower))
        asks_members = model_intent == "discord_member_count" or bool(re.search(r"\b(how many members|member count|how many people are here)\b", lower))
        asks_created_at = bool(re.search(r"\b(when (?:was )?(?:it|this server) (?:made|created)|how old is this server)\b", lower))
        asks_channel = model_intent == "discord_channel" or bool(re.search(r"\b(what|which) channel|channel is this\b", lower))
        asks_thread = model_intent == "discord_thread" or bool(re.search(r"\b(is this|current) (?:a )?thread|thread is this\b", lower))
        if asks_members and asks_creator:
            count = facts.get("member_count")
            clauses.append(f"this server currently has {count} member{'s' if count != 1 else ''}" if count is not None
                           else "the current member count is unavailable")
        if asks_owner:
            owner = facts.get("guild_owner_display_name")
            owner_id = facts.get("guild_owner_id")
            clauses.append(f"the current server owner is {owner}" if owner else
                           f"the current server owner ID is {owner_id}" if owner_id else
                           "I cannot identify the current server owner from this authorized context")
        if asks_members and not asks_creator:
            count = facts.get("member_count")
            clauses.append(f"this server currently has {count} member{'s' if count != 1 else ''}" if count is not None
                           else "the current member count is unavailable")
        if asks_creator:
            owner = facts.get("guild_owner_display_name")
            if owner:
                clauses.append(f"the current server owner is {owner}, but Discord does not reliably expose whether that person originally created the server")
            else:
                clauses.append("Discord does not reliably expose the original server creator through the available guild context")
        if asks_created_at:
            created = facts.get("guild_created_at")
            clauses.append(f"Discord reports the server creation time as {created}" if created else
                           "the server creation time is unavailable in the current guild context")
        if asks_channel:
            name = facts.get("channel_name")
            clauses.append(f"this is #{name}" if name else "the channel name is unavailable")
        if asks_thread:
            clauses.append("this is a thread" if facts.get("is_thread") else "this is not a thread")
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0][0].upper() + clauses[0][1:] + "."
        first = clauses[0][0].upper() + clauses[0][1:]
        if asks_creator:
            return first + ". " + ". ".join(
                clause[0].upper() + clause[1:] for clause in clauses[1:]) + "."
        return first + ", and " + ", and ".join(clauses[1:]) + "."

    def _moderation_report_response(self, event: MentionEvent) -> str:
        recent = list(event.metadata.get("recent_context") or [])[-12:]
        signals = []
        for item in reversed(recent):
            stored = item.get("moderation") or {}
            if stored and stored.get("outcome") != "no_action":
                signals.append(stored)
                continue
            signal = self.moderation_classifier.classify(str(item.get("text", "")))
            if signal is not None and signal.outcome != "no_action":
                signals.append(asdict(signal))
        if not signals:
            return "I understand this as a moderation concern, but I cannot verify a harmful recent message from the bounded authorized context available to me."
        signal = max(signals, key=lambda value: float(value.get("severity", 0)))
        category = str(signal.get("category") or "")
        target = str(signal.get("target_status") or "")
        if category == "targeted_insult" or target == "targeted":
            summary = "hostile profanity directed at Noesis"
        elif "profanity" in category:
            summary = "broad hostile profanity"
        else:
            summary = str(signal.get("safe_summary") or "a moderation concern").lower().removesuffix(" was observed.").rstrip(".")
        return (f"I see the recent message you're referring to. It contains {summary}. "
                "I can treat it as a moderation signal or summarize it for a human moderator, but I will not punish, delete, mute, or ban anyone automatically under the default policy.")

    @staticmethod
    def _package_decision_answer(event: MentionEvent, memories) -> str | None:
        lower = event.text.lower()
        packages = [name for name in ("pandas", "numpy", "matplotlib", "postgresql", "mysql", "sqlite")
                    if name in lower]
        model_intent = (event.metadata.get("local_interpretation") or {}).get("intent")
        if not packages or ("?" not in event.text and model_intent != "package_decision_query"):
            return None
        confirmed = set()
        for memory in memories:
            if memory.memory_type != "decision" or ScopedMemoryStore._question_shaped(memory.content):
                continue
            confirmed.update(name for name in packages if name in memory.content.lower())
        recent_text = " ".join(str(item.get("text", "")) for item in
                               (event.metadata.get("recent_context") or [])[-8:]).lower()
        discussed = [name for name in ("pandas", "numpy", "matplotlib", "postgresql", "mysql", "sqlite")
                     if name in recent_text]
        unresolved = [name for name in packages if name not in confirmed and name not in discussed]
        if not unresolved:
            unresolved = [name for name in packages if name not in confirmed]
        if not unresolved:
            return None
        main = ", ".join(name.title() if name != "numpy" else "NumPy" for name in unresolved)
        context = ""
        if discussed:
            labels = [name.title() if name != "numpy" else "NumPy" for name in discussed]
            context = " From the recent context, I only see discussion that " + " and ".join(labels) + \
                      " are being considered or agreed for V1."
        return f"I do not have a confirmed decision that {main} is part of V1.{context} " \
               f"{main} is still a question, not a confirmed decision."

    @staticmethod
    def _memory_match_reason(query: str, memory) -> str:
        lower = query.lower()
        if getattr(memory, "subject", None) == "release" and re.search(r"release|date|launch", lower):
            return "release_topic_and_subject"
        if getattr(memory, "subject", None) == "database" and re.search(r"database|mysql|postgres|storage", lower):
            return "database_topic_and_subject"
        return "scoped_lexical_match"

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
