from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Protocol

from noesis_agent.domain.contracts.components import (
    ComponentAction, ComponentInteraction, ComponentOutcome, ComponentState, PersistentComponent,
)


class ComponentRepository(Protocol):
    def save(self, component: PersistentComponent) -> None: ...
    def get(self, component_id: str) -> PersistentComponent | None: ...
    def pending(self) -> list[PersistentComponent]: ...


ComponentHandler = Callable[[PersistentComponent, ComponentAction], Awaitable[str]]


class PersistentComponentService:
    def __init__(self, repository: ComponentRepository) -> None:
        self._repository = repository
        self._handlers: dict[str, ComponentHandler] = {}

    def register_handler(self, operation: str, handler: ComponentHandler) -> None:
        self._handlers[operation] = handler

    def create(self, component: PersistentComponent) -> PersistentComponent:
        if component.expires_at <= datetime.now(timezone.utc):
            raise ValueError("Persistent component expiry must be in the future")
        self._repository.save(component)
        return component

    def pending(self) -> list[PersistentComponent]:
        now = datetime.now(timezone.utc)
        result: list[PersistentComponent] = []
        for component in self._repository.pending():
            if component.expires_at <= now:
                self._repository.save(component.model_copy(update={"state": ComponentState.EXPIRED}))
            else:
                result.append(component)
        return result

    async def resolve(self, interaction: ComponentInteraction) -> ComponentOutcome:
        component = self._repository.get(interaction.component_id)
        if component is None:
            return ComponentOutcome(component_id=interaction.component_id, accepted=False,
                                    state=ComponentState.FAILED, message="This action is no longer available.")
        if component.state is not ComponentState.PENDING:
            return ComponentOutcome(component_id=component.component_id, accepted=False,
                                    state=component.state, message="This action has already been handled.")
        if component.expires_at <= datetime.now(timezone.utc):
            expired = component.model_copy(update={"state": ComponentState.EXPIRED})
            self._repository.save(expired)
            return ComponentOutcome(component_id=component.component_id, accepted=False,
                                    state=ComponentState.EXPIRED, message="This action has expired.")
        if component.tenant_id != interaction.tenant_id:
            return ComponentOutcome(component_id=component.component_id, accepted=False,
                                    state=component.state, message="This action belongs to another tenant.")
        unrestricted = not component.authorized_user_ids and not component.authorized_role_ids
        user_allowed = interaction.user_id in component.authorized_user_ids
        role_allowed = bool(component.authorized_role_ids & interaction.role_ids)
        if not unrestricted and not user_allowed and not role_allowed:
            return ComponentOutcome(component_id=component.component_id, accepted=False,
                                    state=component.state, message="You are not authorized for this action.")

        terminal = ComponentState.CANCELLED if interaction.action in {
            ComponentAction.CANCEL, ComponentAction.REJECT
        } else ComponentState.COMPLETED
        handler = self._handlers.get(component.operation)
        if handler is None and terminal is ComponentState.COMPLETED:
            return ComponentOutcome(component_id=component.component_id, accepted=False,
                                    state=ComponentState.FAILED, message="The backing operation is unavailable.")
        try:
            audit = "cancelled by authorized user" if handler is None else await handler(component, interaction.action)
        except (ValueError, RuntimeError, OSError) as exc:
            failed = component.model_copy(update={"state": ComponentState.FAILED,
                                                   "audit_result": str(exc)[:500]})
            self._repository.save(failed)
            return ComponentOutcome(component_id=component.component_id, accepted=False,
                                    state=ComponentState.FAILED, message="The approved action failed safely.")
        completed = component.model_copy(update={
            "state": terminal, "completed_at": datetime.now(timezone.utc), "audit_result": audit[:500],
        })
        self._repository.save(completed)
        return ComponentOutcome(component_id=component.component_id, accepted=True,
                                state=terminal, message="Action completed." if terminal is ComponentState.COMPLETED
                                else "Action cancelled.")
