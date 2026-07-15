from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from noesis_agent.application.components import PersistentComponentService
from noesis_agent.domain.contracts.components import (
    ComponentAction, ComponentInteraction, ComponentState, ComponentType, PersistentComponent,
)
from noesis_agent.infrastructure.persistence.component_store import JsonComponentRepository
from noesis_agent.infrastructure.persistence.json_store import JsonStore
from noesis_agent.integrations.discord.client import NoesisDiscordBot
from noesis_agent.integrations.discord.components import MemoryCorrectionModal, PersistentActionView, stable_custom_id


def _component(**updates: object) -> PersistentComponent:
    base: dict[str, object] = {
        "component_type": ComponentType.MEMORY_REVIEW, "tenant_id": "guild-1",
        "authorized_user_ids": frozenset({"user-1"}), "operation": "memory.review",
        "resource_id": "memory-1", "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "idempotency_key": "memory-1:review:1",
    }
    base.update(updates)
    return PersistentComponent.model_validate(base)


@pytest.mark.asyncio
async def test_component_survives_restart_and_executes_once(tmp_path) -> None:
    repository = JsonComponentRepository(JsonStore(tmp_path))
    first = PersistentComponentService(repository)
    component = first.create(_component())

    restarted = PersistentComponentService(JsonComponentRepository(JsonStore(tmp_path)))
    calls: list[str] = []

    async def handler(item: PersistentComponent, action: ComponentAction) -> str:
        calls.append(f"{item.resource_id}:{action.value}")
        return "memory retained"

    restarted.register_handler("memory.review", handler)
    interaction = ComponentInteraction(component_id=component.component_id, tenant_id="guild-1",
                                       user_id="user-1", action=ComponentAction.RETAIN)
    result = await restarted.resolve(interaction)
    duplicate = await restarted.resolve(interaction)
    assert result.accepted and result.state is ComponentState.COMPLETED
    assert not duplicate.accepted and duplicate.state is ComponentState.COMPLETED
    assert calls == ["memory-1:retain"]


@pytest.mark.asyncio
@pytest.mark.parametrize("tenant,user,message", [
    ("wrong-guild", "user-1", "another tenant"),
    ("guild-1", "wrong-user", "not authorized"),
])
async def test_component_revalidates_tenant_and_user(tmp_path, tenant: str, user: str, message: str) -> None:
    service = PersistentComponentService(JsonComponentRepository(JsonStore(tmp_path)))
    component = service.create(_component())
    result = await service.resolve(ComponentInteraction(
        component_id=component.component_id, tenant_id=tenant, user_id=user, action=ComponentAction.RETAIN
    ))
    assert not result.accepted and message in result.message


@pytest.mark.asyncio
async def test_expired_and_missing_components_fail_safely(tmp_path) -> None:
    repository = JsonComponentRepository(JsonStore(tmp_path))
    service = PersistentComponentService(repository)
    expired = _component(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    repository.save(expired)
    result = await service.resolve(ComponentInteraction(
        component_id=expired.component_id, tenant_id="guild-1", user_id="user-1",
        action=ComponentAction.REMOVE,
    ))
    missing = await service.resolve(ComponentInteraction(
        component_id="missing", tenant_id="guild-1", user_id="user-1", action=ComponentAction.REMOVE,
    ))
    assert result.state is ComponentState.EXPIRED
    assert missing.state is ComponentState.FAILED


@pytest.mark.asyncio
async def test_stable_custom_ids_and_startup_registration(tmp_path) -> None:
    service = PersistentComponentService(JsonComponentRepository(JsonStore(tmp_path)))
    component = service.create(_component())

    async def callback(command: str, payload: dict[str, str]) -> str:
        return "ok"

    bot = NoesisDiscordBot(callback, component_service=service)
    view = PersistentActionView(component, service)
    custom_ids = [item.custom_id for item in view.children]
    assert bot.persistent_view_count == 1
    assert stable_custom_id(component, ComponentAction.RETAIN) in custom_ids
    assert all(value.startswith("noesis:v1:memory_review:") for value in custom_ids)
    assert len(bot.pending_application_commands) == 9


@pytest.mark.asyncio
async def test_memory_correction_modal_has_stable_bounded_fields() -> None:
    async def callback(command: str, payload: dict[str, str]) -> str:
        return "ok"

    modal = MemoryCorrectionModal(callback, tenant_id="guild-1", user_id="user-1", correlation_id="corr-1")
    assert [item.custom_id for item in modal.children] == [
        "noesis_memory_subject_v1", "noesis_memory_correction_v1", "noesis_memory_reason_v1",
    ]
    assert modal.children[1].max_length == 1500
