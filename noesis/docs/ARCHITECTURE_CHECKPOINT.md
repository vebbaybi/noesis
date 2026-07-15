# Architecture checkpoint classification

This checkpoint records the working tree inherited at commit
`c5f038417b4dcbe2b7e96ed910f03f8d376b2f2b` and its consolidation on
`noesis-architecture-consolidation`.

## Protection baseline

Before finalization, the branch contained a partially staged set of Git-aware renames plus a large
unstaged tree. No reset, checkout, blanket restore, clean, or stash operation was used. The staged
renames were intermediate destinations from the architecture migration; explicit path staging is used
to make the checkpoint index match the verified final tree.

## Classification

| Classification | Files or groups | Checkpoint treatment |
| --- | --- | --- |
| Pre-existing user-owned work | Existing local-first cognition, autonomous/scoped memory, Discord mention handling, operator UI, optional audio hardening, provider routing, and their tests | Preserved in full and included because these changes predated the consolidation and are inseparably used by the verified architecture |
| Architecture migration | All moves and import updates under `src/noesis_agent`; removal of legacy roots; canonical `application`, `domain`, `capabilities`, `interfaces`, `integrations`, `infrastructure`, `runtime`, and `shared` roots; runtime bootstrap and console entry point | Included |
| Architecture documentation | `README.md`, `docs/ARCHITECTURE.md`, `docs/ARCHITECTURE_MIGRATION.md`, `docs/DEPENDENCY_RULES.md`, updated runbook/audit, and this checkpoint file | Included |
| Architecture verification | Updated tests, architecture boundary tests, `pyproject.toml`, requirements, and GitHub Actions workflows | Included |
| Ambiguous but required | `assets/users_request.md`, which was already untracked before consolidation and is consumed by the capability catalogue/runtime tests | Preserved and included; excluding it would leave the verified capability catalogue incomplete |
| Generated cache/build output | `.venv`, `__pycache__`, `.pyc`, `.pytest_cache`, `.noesis_data`, logs, `build`, `dist`, and egg-info | Ignored and excluded |
| Dependency/environment artifact | The local Python 3.12 `.venv` and installed editable wheel metadata | Ignored and excluded |

No user-owned file was discarded. Where pre-existing feature work and architectural relocation share a
file, the complete final file is included rather than attempting a destructive history reconstruction.

## Python baseline decision

The reproducible local gate uses Python 3.12.4 because Python 3.11 is not installed on this machine.
`requires-python = ">=3.10"` is retained: the code and existing CI still support Python 3.10, while CI
now explicitly validates 3.10, 3.11, and 3.12. The minimum is not raised until a future dependency
actually requires 3.11+.

## External safety

Verification is credential-free. Discord construction does not connect, and no Discord, X, OpenAI, or
other external API call is performed. Optional heavyweight audio/full extras are not installed.
