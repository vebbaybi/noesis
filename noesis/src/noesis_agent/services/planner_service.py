from __future__ import annotations

from noesis_agent.clients.openai_client import OpenAIService
from noesis_agent.models.schemas import EpisodePlan, EpisodePlanRequest
from noesis_agent.utils.noesislogger import NoesisLogger


class PlannerService:
    def __init__(self, openai_service: OpenAIService) -> None:
        self.openai = openai_service
        self.logger = NoesisLogger("noesis.service.planner").logger

    async def create_plan(self, payload: EpisodePlanRequest) -> EpisodePlan:
        payload = EpisodePlanRequest.model_validate(payload.model_dump())
        duration_per_topic = max(5, payload.duration_minutes // max(len(payload.topics), 1))
        rundown: list[dict[str, object]] = []
        current_minute = 0
        for topic in payload.topics:
            block_duration = topic.duration_goal_minutes or duration_per_topic
            rundown.append(
                {
                    "segment": topic.title,
                    "angle": topic.angle,
                    "priority": topic.priority,
                    "start_minute": current_minute,
                    "duration_minutes": block_duration,
                }
            )
            current_minute += block_duration

        opening_script = (
            f"Welcome to {payload.show_title}. "
            f"Today we are cutting through the noise on {', '.join(topic.title for topic in payload.topics[:3])}. "
            "We will keep it sharp, grounded, and useful."
        )
        closing_script = (
            "That is the room. Keep the signal, drop the cope, and follow the evidence before the narrative."
        )

        plan = EpisodePlan(
            show_title=payload.show_title,
            platform=payload.platform,
            objective=payload.objective,
            target_audience=payload.target_audience,
            topics=payload.topics,
            duration_minutes=payload.duration_minutes,
            preferred_start_time=payload.preferred_start_time,
            hosts=payload.hosts,
            guests=payload.guests,
            tags=payload.tags,
            rundown=rundown,
            opening_script=opening_script,
            closing_script=closing_script,
        )

        if self.openai.is_enabled():
            self.logger.info("Planner is using deterministic structure with optional API support available")
        return plan
