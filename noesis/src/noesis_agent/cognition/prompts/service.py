"""
Prompt management and retrieval for the NOESIS agent.

This service is intentionally thin: prompt assets live in `noesis_agent.infrastructure.config`
and this module turns them into prompt builders used by runtime services.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from noesis_agent.infrastructure.config import DEFAULT_INLINE_TEMPLATES, DEFAULT_PENTAGON_FALLBACK, deep_merge_dicts, settings
from noesis_agent.shared.noesislogger import get_noesis_logger

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency guard
    yaml = None


logger = get_noesis_logger(__name__)


class PromptConfig:
    _instance = None
    _config: Dict[str, Any] = {}
    _yaml_assets: Dict[str, Any] = {}
    _prompt_modules: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.reload()
        return cls._instance

    def reload(self) -> None:
        self._load_assets()
        self._load_prompt_modules()

    def _load_assets(self) -> None:
        config = deep_merge_dicts(DEFAULT_PENTAGON_FALLBACK, {})

        if settings.feature_flags.enable_pentagon_prompts:
            config = deep_merge_dicts(config, self._load_json_file(settings.pentagon_path))

        for name, template in DEFAULT_INLINE_TEMPLATES.items():
            config.setdefault("prompt_templates", {})
            config["prompt_templates"].setdefault(name, {"system": template})

        yaml_assets: dict[str, Any] = {}
        if settings.feature_flags.enable_prompt_yaml_overlays:
            yaml_assets = self._load_yaml_file(settings.prompts_yaml_path)
            config["tones"] = deep_merge_dicts(config.get("tones", {}), yaml_assets.get("tone_overrides", {}))

        self._config = config
        self._yaml_assets = yaml_assets
        logger.audit(
            "Loaded NOESIS prompt assets",
            pentagon_path=str(settings.pentagon_path),
            prompts_yaml_path=str(settings.prompts_yaml_path),
            yaml_overlay=bool(yaml_assets),
            runtime_profile=settings.runtime_profile.name,
        )

    def _load_json_file(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.warning("Prompt JSON asset missing", path=str(path))
            return {}
        except json.JSONDecodeError as exc:
            logger.error("Invalid prompt JSON asset", path=str(path), exc_info=exc)
            return {}

    def _load_yaml_file(self, path: Path) -> dict[str, Any]:
        if yaml is None:
            logger.warning("PyYAML not installed; prompts.yaml overlay disabled")
            return {}
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return payload if isinstance(payload, dict) else {}
        except FileNotFoundError:
            logger.warning("Prompt YAML asset missing", path=str(path))
            return {}
        except Exception as exc:
            logger.error("Invalid prompt YAML asset", path=str(path), exc_info=exc)
            return {}

    def _load_prompt_modules(self) -> None:
        try:
            from noesis_agent.cognition.prompts import (
                cohost_prompts,
                guest_prompts,
                host_prompts,
                moderation_prompts,
                postproduction_prompts,
                research_prompts,
                system_identity,
            )

            self._prompt_modules = {
                "host": host_prompts,
                "cohost": cohost_prompts,
                "guest": guest_prompts,
                "moderator": moderation_prompts,
                "research": research_prompts,
                "postproduction": postproduction_prompts,
                "system": system_identity,
            }
        except ImportError as exc:  # pragma: no cover - defensive
            logger.error("Failed to load prompt modules", exc_info=exc)
            self._prompt_modules = {}

    def get_identity(self) -> str:
        return self._config.get("identity", {}).get("base_persona", "")

    def get_name(self) -> str:
        return self._config.get("identity", {}).get("name", settings.noesis_name)

    def get_company(self) -> str:
        return self._config.get("identity", {}).get("company", settings.company_name)

    def get_tone(self, name: str) -> str:
        tones = self._config.get("tones", {})
        return tones.get(name, tones.get("professional_host", "clear, direct, and sharp"))

    def get_length_instruction(self, length: str) -> str:
        lengths = self._config.get("lengths", {})
        return lengths.get(length, lengths.get("short", "Reply in 1-3 sentences."))

    def get_template(self, name: str) -> Optional[str]:
        template = self._config.get("prompt_templates", {}).get(name)
        if isinstance(template, dict):
            return template.get("system") or template.get("template")
        if isinstance(template, str):
            return template
        inline = DEFAULT_INLINE_TEMPLATES.get(name)
        return str(inline) if inline else None

    def list_templates(self) -> List[str]:
        return sorted(self._config.get("prompt_templates", {}).keys())

    def list_tones(self) -> List[str]:
        return sorted(self._config.get("tones", {}).keys())

    def get_chaotic_personality(self, context: str = "") -> str:
        if not context.strip():
            return "default"

        lowered = context.lower()
        for rule in self._config.get("personality_selection_rules", []):
            keywords = [str(keyword).lower() for keyword in rule.get("if_keywords", [])]
            if any(keyword in lowered for keyword in keywords):
                return str(rule.get("then", "default"))

        heuristics = {
            "rookie_roaster": ["rookie", "newbie", "first nft", "how do i", "new to"],
            "savage_shill_slayer": ["shill", "promo", "sponsored", "rug", "scam", "dev wallet"],
            "nft_flip_king": ["nft", "mint", "floor", "collection", "jpeg"],
            "moonboy": ["pump", "moon", "100x", "send it", "rocket"],
            "whale_energy": ["profit", "win", "diamond hands", "gains"],
            "macro_doomer": ["dump", "crash", "bear", "fud", "recession"],
            "yield_chad": ["yield", "apy", "restaking", "airdrop", "points"],
            "reg_warlord": ["sec", "regulation", "cftc", "etf", "mica"],
        }
        for personality, keywords in heuristics.items():
            if any(keyword in lowered for keyword in keywords):
                return personality
        return "default"

    def select_tone(self, context: str = "", role: str = "host") -> str:
        lowered = context.lower()
        fallback = "professional_host"

        for rule in self._config.get("tone_selection_rules", []):
            if "else" in rule:
                fallback = str(rule.get("else") or fallback)
                continue

            condition = str(rule.get("if", "")).lower()
            matches = re.findall(r"'([^']+)'|\"([^\"]+)\"", condition)
            phrases = [left or right for left, right in matches]
            if phrases and any(phrase.lower() in lowered for phrase in phrases):
                return str(rule.get("then", fallback))

        role_defaults = {
            "host": "professional_host",
            "moderator": "calm_deescalation",
            "research": "analytical",
        }
        return role_defaults.get(role.lower(), fallback)

    def rookie_callout(self, context: str, target: str = "the rookie") -> str:
        template = self.get_template("call_out_rookies") or self.get_template("light_roast") or (
            "{identity}\nWelcome {target} to Web3. Light roast, clear guidance, quick recovery."
        )
        return self._render_template(
            template_name="call_out_rookies",
            template=template,
            tone="roast_light",
            length="short",
            context=context,
            target=target,
        )

    def do_a_callout_rookies(self, context: str, target: Optional[str] = None) -> str:
        return self.rookie_callout(context=context, target=target or "that beautiful rookie in the chat")

    def _build_format_args(self, *, tone: str, length: str, context: str, **kwargs: Any) -> dict[str, Any]:
        fragments = self._yaml_assets.get("identity_fragments", {})
        format_args = {
            "identity": self.get_identity(),
            "agent_name": self.get_name(),
            "company": self.get_company(),
            "tone": self.get_tone(tone),
            "length": self.get_length_instruction(length),
            "personality": self.get_chaotic_personality(context),
            "context": context,
            "runtime_profile": settings.runtime_profile.name,
            "runtime_log_level": settings.runtime_profile.log_level,
            **kwargs,
        }
        for key, value in fragments.items():
            format_args[f"fragment_{key}"] = value
        return format_args

    def _apply_overlay(self, template_name: str, rendered: str, format_args: dict[str, Any]) -> str:
        overlay = self._yaml_assets.get("prompt_overlays", {}).get(template_name, {})
        extra_lines = overlay.get("append_system", [])
        if not extra_lines:
            return rendered

        formatted_lines = []
        for line in extra_lines:
            try:
                formatted_lines.append(str(line).format(**format_args))
            except KeyError:
                formatted_lines.append(str(line))
        return rendered.rstrip() + "\n" + "\n".join(formatted_lines)

    def _render_template(
        self,
        *,
        template_name: str,
        template: str,
        tone: str,
        length: str,
        context: str,
        **kwargs: Any,
    ) -> str:
        format_args = self._build_format_args(tone=tone, length=length, context=context, **kwargs)
        try:
            rendered = template.format(**format_args)
        except KeyError as exc:
            logger.warning("Prompt template missing placeholder", template_name=template_name, missing=str(exc))
            rendered = template
        return self._apply_overlay(template_name, rendered, format_args)

    def _build_base_prompt(
        self,
        template_name: str,
        *,
        tone: Optional[str] = None,
        length: str = "short",
        context: str = "",
        fallback_template: str | None = None,
        role: str = "host",
        **kwargs: Any,
    ) -> str:
        template = self.get_template(template_name) or fallback_template or self.get_template("host_reply") or "{identity}"
        selected_tone = tone or self.select_tone(context, role=role)
        return self._render_template(
            template_name=template_name,
            template=template,
            tone=selected_tone,
            length=length,
            context=context,
            **kwargs,
        )

    def build_episode_planner_prompt(
        self,
        topic: str = "",
        tone: Optional[str] = None,
        duration: str = "60 min",
        guests: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "planner",
            tone=tone,
            length="long",
            context=topic,
            topic=topic,
            duration=duration,
            guests=", ".join(guests or []),
            role="host",
            **kwargs,
        )

    def build_host_reply_prompt(
        self,
        context: str = "",
        topic: str = "",
        audience_signal: str = "",
        tone: Optional[str] = None,
        length: str = "short",
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "host_reply",
            tone=tone,
            length=length,
            context=context,
            topic=topic,
            audience_signal=audience_signal,
            role="host",
            **kwargs,
        )

    def build_host_opening_prompt(
        self,
        topic: str = "",
        context: str = "",
        tone: Optional[str] = None,
        length: str = "short",
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "host_opening",
            tone=tone,
            length=length,
            context=context,
            topic=topic,
            role="host",
            **kwargs,
        )

    def build_host_transition_prompt(
        self,
        from_topic: str = "",
        to_topic: str = "",
        context: str = "",
        tone: Optional[str] = None,
        length: str = "short",
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "host_transition",
            tone=tone,
            length=length,
            context=context,
            from_topic=from_topic,
            to_topic=to_topic,
            role="host",
            **kwargs,
        )

    def build_summary_prompt(
        self,
        context: str = "",
        tone: Optional[str] = None,
        length: str = "medium",
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "session_summary",
            tone=tone,
            length=length,
            context=context,
            role="host",
            **kwargs,
        )

    def build_announcement_prompt(
        self,
        context: str = "",
        tone: Optional[str] = None,
        length: str = "medium",
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "session_announcement",
            tone=tone,
            length=length,
            context=context,
            role="host",
            **kwargs,
        )

    def build_nft_hashtag_prompt(
        self,
        context: str = "",
        tone: Optional[str] = None,
        length: str = "short",
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "nft_hashtags",
            tone=tone or "professional_host",
            length=length,
            context=context,
            role="host",
            **kwargs,
        )

    def build_light_roast_prompt(
        self,
        target: str = "someone",
        context: str = "",
        tone: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "light_roast",
            tone=tone or "roast_light",
            length="short",
            context=context,
            target=target,
            role="host",
            **kwargs,
        )

    def build_call_out_shill_prompt(
        self,
        context: str = "",
        tone: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "call_out_shill",
            tone=tone or "skeptical",
            length="short",
            context=context,
            role="host",
            **kwargs,
        )

    def build_guest_reply_prompt(
        self,
        question: str = "",
        topic: str = "",
        expertise: str = "",
        tone: Optional[str] = None,
        length: str = "short",
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "guest_reply",
            tone=tone or "professional_host",
            length=length,
            context=question,
            topic=topic,
            expertise=expertise,
            role="guest",
            **kwargs,
        )

    def build_moderation_redirect_prompt(
        self,
        context: str = "",
        offending_behavior: str = "",
        tone: Optional[str] = None,
        urgency: str = "normal",
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "moderation_redirect",
            tone=tone or "calm_deescalation",
            length="short",
            context=context,
            offending_behavior=offending_behavior,
            urgency=urgency,
            role="moderator",
            **kwargs,
        )

    def build_research_topic_scan_prompt(
        self,
        topic: str = "",
        depth: str = "brief",
        tone: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "research_scan",
            tone=tone or "analytical",
            length="medium",
            context=topic,
            topic=topic,
            depth=depth,
            role="research",
            **kwargs,
        )

    def build_postproduction_show_notes_prompt(
        self,
        session_content: str = "",
        session_title: str = "",
        tone: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        return self._build_base_prompt(
            "show_notes",
            tone=tone or "professional_host",
            length="long",
            context=session_content,
            session_title=session_title,
            role="postproduction",
            **kwargs,
        )

    def get_prompt_module(self, module_name: str) -> Any:
        return self._prompt_modules.get(module_name)

    def get_role_prompt_builder(self, role: str) -> Optional[Any]:
        return self._prompt_modules.get(role)

    def build_role_prompt(self, role: str, template_key: str, **kwargs: Any) -> Optional[str]:
        module = self.get_role_prompt_builder(role)
        if module is None:
            return None
        builder_name = f"build_{template_key}"
        builder = getattr(module, builder_name, None)
        if callable(builder):
            return builder(**kwargs)
        return None

    def validate_prompt(self, prompt: str, required_sections: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
        if not required_sections:
            return True, []
        missing = [section for section in required_sections if section.lower() not in prompt.lower()]
        return not missing, missing

    def get_prompt_metrics(self) -> Dict[str, Any]:
        return {
            "templates_loaded": len(self.list_templates()),
            "tones_available": len(self.list_tones()),
            "yaml_overlay_enabled": bool(self._yaml_assets),
            "runtime_profile": settings.runtime_profile.name,
            "feature_flags": settings.feature_flags.as_dict(),
        }


_prompt_config = PromptConfig()

get_identity = _prompt_config.get_identity
get_name = _prompt_config.get_name
get_company = _prompt_config.get_company
get_tone = _prompt_config.get_tone
get_length_instruction = _prompt_config.get_length_instruction
get_template = _prompt_config.get_template
list_templates = _prompt_config.list_templates
list_tones = _prompt_config.list_tones
get_chaotic_personality = _prompt_config.get_chaotic_personality
select_tone = _prompt_config.select_tone
rookie_callout = _prompt_config.rookie_callout
do_a_callout_rookies = _prompt_config.do_a_callout_rookies
build_episode_planner_prompt = _prompt_config.build_episode_planner_prompt
build_host_reply_prompt = _prompt_config.build_host_reply_prompt
build_host_opening_prompt = _prompt_config.build_host_opening_prompt
build_host_transition_prompt = _prompt_config.build_host_transition_prompt
build_summary_prompt = _prompt_config.build_summary_prompt
build_announcement_prompt = _prompt_config.build_announcement_prompt
build_nft_hashtag_prompt = _prompt_config.build_nft_hashtag_prompt
build_light_roast_prompt = _prompt_config.build_light_roast_prompt
build_call_out_shill_prompt = _prompt_config.build_call_out_shill_prompt
build_guest_reply_prompt = _prompt_config.build_guest_reply_prompt
build_moderation_redirect_prompt = _prompt_config.build_moderation_redirect_prompt
build_research_topic_scan_prompt = _prompt_config.build_research_topic_scan_prompt
build_postproduction_show_notes_prompt = _prompt_config.build_postproduction_show_notes_prompt
get_prompt_module = _prompt_config.get_prompt_module
get_role_prompt_builder = _prompt_config.get_role_prompt_builder
build_role_prompt = _prompt_config.build_role_prompt
validate_prompt = _prompt_config.validate_prompt
get_prompt_metrics = _prompt_config.get_prompt_metrics
prompt_config = _prompt_config


__all__ = [
    "PromptConfig",
    "build_announcement_prompt",
    "build_call_out_shill_prompt",
    "build_episode_planner_prompt",
    "build_guest_reply_prompt",
    "build_host_opening_prompt",
    "build_host_reply_prompt",
    "build_host_transition_prompt",
    "build_light_roast_prompt",
    "build_moderation_redirect_prompt",
    "build_nft_hashtag_prompt",
    "build_postproduction_show_notes_prompt",
    "build_research_topic_scan_prompt",
    "build_role_prompt",
    "build_summary_prompt",
    "do_a_callout_rookies",
    "get_chaotic_personality",
    "get_company",
    "get_identity",
    "get_length_instruction",
    "get_name",
    "get_prompt_metrics",
    "get_prompt_module",
    "get_role_prompt_builder",
    "get_template",
    "get_tone",
    "list_templates",
    "list_tones",
    "prompt_config",
    "rookie_callout",
    "select_tone",
    "validate_prompt",
]
