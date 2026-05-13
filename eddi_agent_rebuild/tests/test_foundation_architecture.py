from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import noesis_agent


def test_every_noesis_module_imports() -> None:
    failures: list[str] = []
    for module in pkgutil.walk_packages(noesis_agent.__path__, prefix="noesis_agent."):
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # pragma: no cover - assertion payload
            failures.append(f"{module.name}: {type(exc).__name__}: {exc}")

    assert failures == []


def test_lower_layers_do_not_import_service_or_entrypoint_layers() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "noesis_agent"
    restricted = {
        "clients": {"noesis_agent.services", "noesis_agent.commands", "noesis_agent.api", "noesis_agent.runner"},
        "cognition": {"noesis_agent.services", "noesis_agent.commands", "noesis_agent.api", "noesis_agent.runner"},
        "models": {"noesis_agent.services", "noesis_agent.clients", "noesis_agent.api", "noesis_agent.runner"},
        "config": {"noesis_agent.services", "noesis_agent.clients", "noesis_agent.api", "noesis_agent.runner"},
    }

    violations: list[str] = []
    for layer, blocked_prefixes in restricted.items():
        for path in sorted((source_root / layer).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                imports: list[str] = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
                elif isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                for module_name in imports:
                    if any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in blocked_prefixes):
                        violations.append(f"{path.relative_to(source_root)} imports {module_name}")

    assert violations == []


def test_no_legacy_top_level_internal_imports_remain() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "noesis_agent"
    internal_roots = {
        "api",
        "audio",
        "brain",
        "clients",
        "cognition",
        "commands",
        "config",
        "content",
        "core",
        "knowledge",
        "media",
        "memory",
        "models",
        "moderation",
        "monitors",
        "pipelines",
        "platforms",
        "prompts",
        "scheduling",
        "services",
        "store",
        "telemetry",
        "utils",
    }
    violations: list[str] = []

    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if node.module.split(".")[0] in internal_roots and not node.module.startswith("noesis_agent."):
                    violations.append(f"{path.relative_to(source_root)} imports {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in internal_roots and not alias.name.startswith("noesis_agent."):
                        violations.append(f"{path.relative_to(source_root)} imports {alias.name}")

    assert violations == []
