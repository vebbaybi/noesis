from __future__ import annotations

import ast
from pathlib import Path


SOURCE = Path(__file__).parents[1] / "src" / "noesis_agent"
LAYERS = {
    "domain", "application", "cognition", "memory", "capabilities",
    "interfaces", "integrations", "infrastructure", "runtime", "shared",
}
LEGACY = {
    "api", "audio", "brain", "clients", "commands", "config", "content", "core",
    "knowledge", "media", "models", "moderation", "monitors", "persistence",
    "pipelines", "platforms", "prompts", "publishing", "scheduling", "services",
    "store", "telemetry", "utils",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


def _internal_layer(imported: str) -> str | None:
    parts = imported.split(".")
    return parts[1] if len(parts) > 1 and parts[0] == "noesis_agent" else None


def test_only_canonical_top_level_packages_exist() -> None:
    actual = {path.name for path in SOURCE.iterdir() if path.is_dir() and path.name != "__pycache__"}
    assert actual == LAYERS


def test_domain_is_independent() -> None:
    violations = []
    for path in (SOURCE / "domain").rglob("*.py"):
        for imported in _imports(path):
            layer = _internal_layer(imported)
            if layer and layer not in {"domain", "shared"}:
                violations.append(f"{path.relative_to(SOURCE)} -> {imported}")
    assert not violations, violations


def test_application_does_not_import_concrete_adapters_or_runtime() -> None:
    blocked = {"interfaces", "integrations", "infrastructure", "runtime"}
    violations = []
    for path in (SOURCE / "application").rglob("*.py"):
        for imported in _imports(path):
            if _internal_layer(imported) in blocked:
                violations.append(f"{path.relative_to(SOURCE)} -> {imported}")
    assert not violations, violations


def test_removed_namespaces_cannot_return() -> None:
    violations = []
    for path in SOURCE.rglob("*.py"):
        for imported in _imports(path):
            if _internal_layer(imported) in LEGACY:
                violations.append(f"{path.relative_to(SOURCE)} -> {imported}")
    assert not violations, violations
    assert not [name for name in LEGACY if (SOURCE / name).exists()]


def test_memory_does_not_depend_on_cognition_application_interfaces_or_runtime() -> None:
    blocked = {"cognition", "application", "interfaces", "runtime"}
    violations = []
    for path in (SOURCE / "memory").rglob("*.py"):
        for imported in _imports(path):
            if _internal_layer(imported) in blocked:
                violations.append(f"{path.relative_to(SOURCE)} -> {imported}")
    assert not violations, violations


def test_runner_is_the_only_executable_shim() -> None:
    executable = []
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        if any(isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
               and node.left.id == "__name__" for node in ast.walk(tree)):
            executable.append(path.relative_to(SOURCE).as_posix())
    assert executable == ["runner.py"]
