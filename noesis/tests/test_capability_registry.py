import importlib
from pathlib import Path

from noesis_agent.cognition.capabilities import CapabilityRegistry


def registry() -> CapabilityRegistry:
    path = Path("../assets/users_request.md")
    assert path.is_file()
    return CapabilityRegistry(path)


def test_catalogue_requirements_map_to_grouped_stable_capabilities() -> None:
    value = registry()
    ids = [item.capability_id for item in value.capabilities]
    assert len(ids) == len(set(ids))
    assert 20 <= len(ids) < len(value.requirements)
    assert len(value.requirements) > 400
    assert all(trace.capability_id in ids for trace in value.requirements)
    assert value.summary()["requirement_total"] == len(value.requirements)


def test_implemented_capabilities_reference_importable_real_handlers() -> None:
    for capability in registry().capabilities:
        if capability.implementation_state not in {"implemented_tested", "implemented_live_validation_required"}:
            continue
        assert capability.handler_ids
        for handler in capability.handler_ids:
            module_name, attribute = handler.rsplit(".", 1)
            assert hasattr(importlib.import_module(module_name), attribute)


def test_planned_and_blocked_capabilities_are_not_presented_as_working() -> None:
    for capability in registry().capabilities:
        if capability.implementation_state in {"planned", "blocked_credentials", "blocked_platform"}:
            assert capability.validation_state != "offline_tested"
            assert capability.operator_status != "implemented tested"
