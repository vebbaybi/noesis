from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel

from noesis_agent.domain.contracts.intelligence import ToolCall

ArgsT = TypeVar("ArgsT", bound=BaseModel)
ResultT = TypeVar("ResultT", bound=BaseModel)


class SideEffect(str, Enum):
    NONE = "none"
    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"


@dataclass(frozen=True, slots=True)
class ToolDefinition(Generic[ArgsT, ResultT]):
    tool_id: str
    purpose: str
    arguments_model: type[ArgsT]
    result_model: type[ResultT]
    required_capability: str
    side_effect: SideEffect
    timeout_seconds: float
    handler: Callable[[ArgsT, str, str], Awaitable[ResultT]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition[BaseModel, BaseModel]] = {}

    def register(self, definition: ToolDefinition[BaseModel, BaseModel]) -> None:
        if definition.tool_id in self._tools:
            raise ValueError(f"Tool already registered: {definition.tool_id}")
        self._tools[definition.tool_id] = definition

    async def execute(self, call: ToolCall, *, tenant_id: str, user_id: str,
                      authorized_capabilities: frozenset[str]) -> str:
        definition = self._tools.get(call.tool_id)
        if definition is None:
            raise ValueError(f"Tool is not allowlisted: {call.tool_id}")
        arguments = definition.arguments_model.model_validate(call.arguments)
        if definition.required_capability not in authorized_capabilities:
            raise PermissionError(f"Capability is not authorized: {definition.required_capability}")
        async with asyncio.timeout(definition.timeout_seconds):
            result = await definition.handler(arguments, tenant_id, user_id)
        return result.model_dump_json()

    def schemas(self) -> list[dict[str, object]]:
        return [{
            "id": item.tool_id, "purpose": item.purpose,
            "arguments": item.arguments_model.model_json_schema(),
            "required_capability": item.required_capability,
            "side_effect": item.side_effect.value,
        } for item in self._tools.values()]
