from __future__ import annotations

from datetime import datetime, timezone

from noesis_agent.domain.contracts.runtime import TopicPlan
from noesis_agent.domain.contracts.session import SessionState
from noesis_agent.shared.noesislogger import NoesisLogger


class TopicPlanningService:
    """Manages the live topic queue for a NOESIS session."""

    def __init__(self) -> None:
        self.logger = NoesisLogger("noesis.service.topic_planning").logger

    def create_topic_queue(self, topics: list[str | TopicPlan]) -> list[TopicPlan]:
        queue: list[TopicPlan] = []
        for index, topic in enumerate(topics, start=1):
            if isinstance(topic, TopicPlan):
                queue.append(topic.model_copy(update={"priority": topic.priority or index}))
            else:
                title = str(topic).strip()
                if title:
                    queue.append(TopicPlan(title=title, priority=index))
        return queue

    def add_topic(
        self,
        state: SessionState,
        title: str,
        *,
        angle: str = "",
        priority: int | None = None,
        duration_goal_minutes: int | None = None,
    ) -> TopicPlan:
        topic = TopicPlan(
            title=title.strip(),
            angle=angle.strip(),
            priority=priority or len(state.session.topic_plan) + 1,
            duration_goal_minutes=duration_goal_minutes,
        )
        state.session.topic_plan.append(topic)
        self.logger.info("Topic added", extra={"session_id": state.session_id, "topic": topic.title})
        return topic

    def remove_topic(self, state: SessionState, title: str) -> bool:
        normalized = title.strip().lower()
        before = len(state.session.topic_plan)
        state.session.topic_plan = [topic for topic in state.session.topic_plan if topic.title.lower() != normalized]
        if state.current_topic_index is not None and state.current_topic_index >= len(state.session.topic_plan):
            state.current_topic_index = None
        return len(state.session.topic_plan) != before

    def mark_active(self, state: SessionState, title: str) -> TopicPlan:
        topic = self._find_or_add(state, title)
        now = datetime.now(timezone.utc)
        for index, candidate in enumerate(state.session.topic_plan):
            if candidate.title == topic.title:
                candidate.status = "active"
                candidate.started_at = candidate.started_at or now
                state.current_topic_index = index
                state.session.room_state.active_topic = candidate.title
                topic = candidate
            elif candidate.status == "active":
                candidate.status = "queued"
        return topic

    def mark_completed(self, state: SessionState, title: str | None = None) -> TopicPlan | None:
        topic = self._current_or_named(state, title)
        if topic is None:
            return None
        topic.status = "done"
        topic.ended_at = datetime.now(timezone.utc)
        if state.session.room_state.active_topic == topic.title:
            state.session.room_state.active_topic = None
        return topic

    def park_topic(self, state: SessionState, title: str | None = None) -> TopicPlan | None:
        topic = self._current_or_named(state, title)
        if topic is None:
            return None
        topic.status = "parked"
        if state.session.room_state.active_topic == topic.title:
            state.session.room_state.active_topic = None
        return topic

    def resume_parked_topic(self, state: SessionState, title: str) -> TopicPlan:
        topic = self._find_or_add(state, title)
        if topic.status != "parked":
            topic.notes.append("Resumed from queue rather than parked state.")
        return self.mark_active(state, topic.title)

    def next_topic(self, state: SessionState) -> TopicPlan | None:
        queued = [topic for topic in state.session.topic_plan if topic.status == "queued"]
        if not queued:
            return None
        queued.sort(key=lambda topic: (topic.priority, topic.title.lower()))
        return self.mark_active(state, queued[0].title)

    def suggest_fallback_topic(self, state: SessionState) -> TopicPlan:
        completed_titles = {topic.title.lower() for topic in state.session.topic_plan}
        candidates = [
            "Audience questions and fast takes",
            "Risk check and what would change our minds",
            "Best signal from the session so far",
        ]
        for title in candidates:
            if title.lower() not in completed_titles:
                return self.add_topic(state, title, angle="silence recovery", priority=99)
        return self.add_topic(state, "Open floor: strongest unresolved question", angle="fallback", priority=100)

    def generate_transition(self, previous_topic: str | None, next_topic: str) -> str:
        previous = (previous_topic or "that thread").strip()
        target = next_topic.strip()
        return f"Let's park {previous} there and move into {target}; the useful question now is what changes the room's read."

    def _find_or_add(self, state: SessionState, title: str) -> TopicPlan:
        normalized = title.strip().lower()
        for topic in state.session.topic_plan:
            if topic.title.lower() == normalized:
                return topic
        return self.add_topic(state, title)

    def _current_or_named(self, state: SessionState, title: str | None) -> TopicPlan | None:
        if title:
            normalized = title.strip().lower()
            return next((topic for topic in state.session.topic_plan if topic.title.lower() == normalized), None)
        if state.current_topic_index is not None and 0 <= state.current_topic_index < len(state.session.topic_plan):
            return state.session.topic_plan[state.current_topic_index]
        active = state.session.room_state.active_topic
        if active:
            return next((topic for topic in state.session.topic_plan if topic.title == active), None)
        return None


__all__ = ["TopicPlanningService"]
