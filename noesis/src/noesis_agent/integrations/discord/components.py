from __future__ import annotations

from collections.abc import Awaitable, Callable

import discord

from noesis_agent.application.components import PersistentComponentService
from noesis_agent.domain.contracts.components import (
    ComponentAction, ComponentInteraction, ComponentType, PersistentComponent,
)


def stable_custom_id(component: PersistentComponent, action: ComponentAction) -> str:
    return f"noesis:v{component.version}:{component.component_type.value}:{action.value}:{component.component_id}"


class _ActionButton(discord.ui.Button):
    def __init__(self, component: PersistentComponent, action: ComponentAction,
                 service: PersistentComponentService, *, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(label=label, style=style, custom_id=stable_custom_id(component, action))
        self._component = component
        self._action = action
        self._service = service

    async def callback(self, interaction: discord.Interaction) -> None:
        guild_id = str(getattr(interaction, "guild_id", "") or "direct-message")
        user = getattr(interaction, "user", None)
        roles = frozenset(str(role.id) for role in getattr(user, "roles", []) if getattr(role, "id", None))
        outcome = await self._service.resolve(ComponentInteraction(
            component_id=self._component.component_id, tenant_id=guild_id,
            user_id=str(getattr(user, "id", "anonymous")), role_ids=roles, action=self._action,
        ))
        if interaction.response.is_done():
            await interaction.followup.send(outcome.message, ephemeral=True)
        else:
            await interaction.response.send_message(outcome.message, ephemeral=True)


class PersistentActionView(discord.ui.View):
    def __init__(self, component: PersistentComponent, service: PersistentComponentService) -> None:
        super().__init__(timeout=None)
        actions = {
            ComponentType.SIDE_EFFECT_CONFIRMATION: (
                (ComponentAction.CONFIRM, "Confirm", discord.ButtonStyle.danger),
                (ComponentAction.CANCEL, "Cancel", discord.ButtonStyle.secondary),
            ),
            ComponentType.MODERATION_REVIEW: (
                (ComponentAction.APPROVE, "Approve", discord.ButtonStyle.success),
                (ComponentAction.REJECT, "Reject", discord.ButtonStyle.danger),
            ),
            ComponentType.MEMORY_REVIEW: (
                (ComponentAction.RETAIN, "Retain", discord.ButtonStyle.success),
                (ComponentAction.REMOVE, "Remove", discord.ButtonStyle.danger),
            ),
            ComponentType.FAILED_ACTION_RETRY: (
                (ComponentAction.RETRY, "Retry", discord.ButtonStyle.primary),
                (ComponentAction.CANCEL, "Cancel", discord.ButtonStyle.secondary),
            ),
        }[component.component_type]
        for action, label, style in actions:
            self.add_item(_ActionButton(component, action, service, label=label, style=style))


ModalSubmit = Callable[[str, dict[str, str]], Awaitable[str | None]]


class MemoryCorrectionModal(discord.ui.Modal):
    def __init__(self, submit: ModalSubmit, *, tenant_id: str, user_id: str,
                 correlation_id: str) -> None:
        super().__init__(title="Request a memory correction", timeout=300)
        self._submit = submit
        self._tenant_id = tenant_id
        self._user_id = user_id
        self._correlation_id = correlation_id
        self.subject = discord.ui.InputText(label="Subject", custom_id="noesis_memory_subject_v1",
                                            min_length=2, max_length=120, required=True)
        self.correction = discord.ui.InputText(label="Correct information", custom_id="noesis_memory_correction_v1",
                                               style=discord.InputTextStyle.long, min_length=2,
                                               max_length=1500, required=True)
        self.reason = discord.ui.InputText(label="Reason (optional)", custom_id="noesis_memory_reason_v1",
                                           style=discord.InputTextStyle.long, max_length=500, required=False)
        self.add_item(self.subject)
        self.add_item(self.correction)
        self.add_item(self.reason)

    async def callback(self, interaction: discord.Interaction) -> None:
        result = await self._submit("memory_correction", {
            "tenant_id": self._tenant_id, "user_id": self._user_id,
            "subject": str(self.subject.value or "").strip(),
            "correction": str(self.correction.value or "").strip(),
            "reason": str(self.reason.value or "").strip(),
            "correlation_id": self._correlation_id,
        })
        await interaction.response.send_message(result or "Correction submitted for review.", ephemeral=True)


__all__ = ["MemoryCorrectionModal", "PersistentActionView", "stable_custom_id"]
