# Dependency rules

Architecture tests parse Python imports into a package graph; they do not grep source text.

Enforced rules:

1. Only the ten documented top-level package roots may exist.
2. Domain cannot import application, cognition, memory, capabilities, interfaces, integrations,
   infrastructure, or runtime.
3. Application cannot import concrete interfaces, integrations, infrastructure, or runtime.
4. No package outside runtime (and the documented runner shim) may import runtime.
5. Removed legacy namespaces cannot be imported or recreated.
6. Memory semantics cannot import an interface or runtime layer.
7. Every module must import successfully, and executable `__main__` handling is limited to the shim.

Run the checks with `python -m pytest -q tests/test_architecture_boundaries.py` or as part of the full
test suite. CI runs the full suite after editable installation.
