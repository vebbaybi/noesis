from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Outcome = Literal["ignore", "observe_only", "create_memory_candidate", "record_moderation_signal",
                  "notify_moderators", "respond_without_mention", "respond_to_mention",
                  "ask_for_clarification", "defer_due_to_missing_permission"]


@dataclass(frozen=True, slots=True)
class ModerationSignal:
    category: str
    severity: float
    confidence: float
    target_status: str
    outcome: str
    safe_summary: str


@dataclass(frozen=True, slots=True)
class InterventionDecision:
    outcome: Outcome
    should_respond: bool
    should_remember: bool
    should_moderate: bool
    use_humor: bool
    reason: str


class LocalModerationClassifier:
    _SECRET = re.compile(r"(?i)(api[_ -]?key|token|password|secret)\s*[:=]|\b(?:sk-|ghp_|xox[baprs]-)[A-Za-z0-9_-]{8,}")
    _THREAT = re.compile(r"(?i)\b(?:kill|hurt|attack|doxx?)\s+(?:you|him|her|them)\b")
    _TARGETED = re.compile(r"(?i)(?:\b(?:you|he|she|they)\s+(?:are|is)\s+(?:an?\s+)?(?:idiot|stupid|trash|worthless|useless|(?:complete\s+)?failure|cunt)\b|\b(?:you\b.{0,80}|being\s+(?:an?\s+)?)cunt\b|\bfuck\s+you\b)")
    _PROFANITY = re.compile(r"(?i)\b(?:fuck(?:ing|ed|er|s)?|shit(?:ty)?|damn|cunt)\b")
    _SCAM = re.compile(r"(?i)\b(?:guaranteed returns?|send .* receive|double your|seed phrase|wallet verification)\b")
    _HATE = re.compile(r"(?i)\b(?:all|those)\s+(?:women|men|muslims|jews|christians|gay|trans|black|white)\s+(?:are|should)\b")
    _SEXUAL = re.compile(r"(?i)\b(?:send nudes|sexual favors?|sleep with me|show me your body)\b")
    _SPAM = re.compile(r"(?i)(?:\b(?:buy now|limited offer|free money)\b.*){2,}|(.)\1{12,}")
    _MALICIOUS_LINK = re.compile(r"(?i)https?://[^\s]*(?:discord-?nitro|wallet-?verify|airdrop-?claim|login-?secure)[^\s]*")
    _IMPERSONATION = re.compile(r"(?i)\b(?:official support|admin here|i am the moderator)\b.*\b(?:dm|send|verify)\b")
    _RAID = re.compile(r"(?i)\b(?:raid this|mass spam|everyone flood|brigade)\b")
    _RULE = re.compile(r"(?i)\b(?:evade the rules|ignore moderators?|bypass moderation)\b")
    _FRUSTRATION = re.compile(r"(?i)\b(?:this sucks|i am frustrated|so annoying|what a mess)\b")

    def classify(self, text: str) -> ModerationSignal | None:
        quoted = bool(re.search(r"(?:^|\s)[>\"].+(?:[\"']|$)", text))
        banter = bool(re.search(r"(?i)\b(?:lol|lmao|jk|just kidding|my friend)\b|[😂🤣]", text))
        if self._SECRET.search(text):
            return ModerationSignal("credential_exposure", 1.0, .99, "not_applicable",
                                    "urgent_human_escalation", "Possible credential exposure detected; content redacted.")
        if quoted and any(pattern.search(text) for pattern in (self._THREAT, self._TARGETED, self._HATE,
                                                               self._SEXUAL, self._PROFANITY)):
            return ModerationSignal("quoted_content", .05, .7, "quoted", "no_action",
                                    "Potentially harmful wording appears to be quoted context.")
        if self._THREAT.search(text):
            return ModerationSignal("threat", .95, .9, "targeted", "urgent_human_escalation",
                                    "A possible targeted threat requires human review.")
        if self._HATE.search(text):
            return ModerationSignal("hate_or_identity_attack", .9, .82, "identity_group",
                                    "urgent_human_escalation", "A possible identity-based attack requires human review.")
        if self._SEXUAL.search(text):
            return ModerationSignal("sexual_harassment", .85, .85, "targeted",
                                    "private_moderator_signal", "Possible sexual harassment requires moderator review.")
        if self._MALICIOUS_LINK.search(text):
            return ModerationSignal("malicious_link", .9, .8, "community",
                                    "private_moderator_signal", "A link matched high-risk credential or wallet patterns.")
        if self._IMPERSONATION.search(text):
            return ModerationSignal("impersonation", .8, .75, "community",
                                    "private_moderator_signal", "Possible staff impersonation requires verification.")
        if self._RAID.search(text):
            return ModerationSignal("raid_behavior", .9, .85, "community",
                                    "urgent_human_escalation", "Possible coordinated disruption requires human review.")
        if self._SCAM.search(text):
            return ModerationSignal("scam", .85, .85, "community", "private_moderator_signal",
                                    "A message matched common scam-risk indicators.")
        if self._SPAM.search(text):
            return ModerationSignal("spam", .55, .78, "community", "observe",
                                    "Likely repetitive promotional spam was observed.")
        if self._TARGETED.search(text) and banter:
            return ModerationSignal("friendly_banter", .1, .65, "friendly", "no_action",
                                    "Likely friendly banter; no moderation action recommended.")
        if self._TARGETED.search(text) and not quoted:
            return ModerationSignal("targeted_insult", .65, .82, "targeted", "soft_deescalation",
                                    "A likely targeted insult was detected.")
        if self._RULE.search(text):
            return ModerationSignal("community_rule_violation", .55, .75, "community",
                                    "public_rule_reminder", "A possible deliberate rule violation was detected.")
        if self._FRUSTRATION.search(text):
            return ModerationSignal("non_actionable_frustration", .1, .72, "none", "observe",
                                    "Frustration without a clear target or safety risk was observed.")
        if self._PROFANITY.search(text):
            return ModerationSignal("general_profanity", .2, .75, "none", "observe",
                                    "General profanity without a clear target was observed.")
        return None


class InterventionPolicy:
    def decide(self, *, mentioned: bool, observation_mode: str, has_candidate: bool,
               moderation: ModerationSignal | None, confidence: float,
               direct_question: bool = False, ambient_response_enabled: bool = False) -> InterventionDecision:
        if observation_mode == "disabled":
            return InterventionDecision("ignore", False, False, False, False, "observation_disabled")
        if mentioned:
            return InterventionDecision("respond_to_mention", True, has_candidate, moderation is not None,
                                        moderation is None, "explicitly_addressed")
        if observation_mode == "mentions_only":
            return InterventionDecision("ignore", False, False, False, False, "mentions_only")
        if (moderation and moderation.outcome != "no_action" and moderation.severity >= .3
                and observation_mode in {"observe_and_moderate", "full_authorized_assistance"}):
            outcome: Outcome = "notify_moderators" if moderation.severity >= .8 else "record_moderation_signal"
            return InterventionDecision(outcome, False, False, True, False, moderation.category)
        if (ambient_response_enabled and observation_mode == "full_authorized_assistance"
                and direct_question and confidence >= .8):
            return InterventionDecision("respond_without_mention", True, False, False, False,
                                        "authorized_ambient_question")
        if has_candidate and observation_mode in {"observe_and_remember", "full_authorized_assistance"}:
            return InterventionDecision("create_memory_candidate", False, True, False, False,
                                        "actionable_memory")
        return InterventionDecision("observe_only", False, False, False, False,
                                    "no_intervention_condition")


__all__ = ["InterventionDecision", "InterventionPolicy", "LocalModerationClassifier", "ModerationSignal"]
