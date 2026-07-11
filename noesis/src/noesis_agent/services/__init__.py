"""Service package exports."""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "ServiceContainer",
    "container",
    "get_container",
    "HostService",
    "HostDecisionService",
    "HostRuntimeService",
    "LiveSessionService",
    "OutputRouter",
    "PostShowArtifactService",
    "PlannerService",
    "PlatformService",
    "PublisherService",
    "SessionService",
    "SocialService",
    "SummaryService",
    "TopicPlanningService",
]


def __getattr__(name: str):
    module_map = {
        "ServiceContainer": (".container", "ServiceContainer"),
        "container": (".container", "container"),
        "get_container": (".container", "get_container"),
        "HostService": (".host_service", "HostService"),
        "HostDecisionService": (".host_decision_service", "HostDecisionService"),
        "HostRuntimeService": (".host_runtime_service", "HostRuntimeService"),
        "LiveSessionService": (".live_session_service", "LiveSessionService"),
        "OutputRouter": (".output_router", "OutputRouter"),
        "PostShowArtifactService": (".post_show_service", "PostShowArtifactService"),
        "PlannerService": (".planner_service", "PlannerService"),
        "PlatformService": (".platform_service", "PlatformService"),
        "PublisherService": (".publisher_service", "PublisherService"),
        "SessionService": (".session_service", "SessionService"),
        "SocialService": (".social_service", "SocialService"),
        "SummaryService": (".summary_service", "SummaryService"),
        "TopicPlanningService": (".topic_planning_service", "TopicPlanningService"),
    }
    if name not in module_map:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = module_map[name]
    module = import_module(module_name, package=__name__)
    return getattr(module, attr_name)
