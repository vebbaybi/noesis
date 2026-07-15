# CI and release-build standard

Noesis separates merge validation from release preparation. Neither workflow deploys software.

## Merge CI

`.github/workflows/noesis-ci.yml` runs for pull requests to `main`, pushes to `main` and
`noesis-*` branches, and manual dispatches. Read-only repository permissions and concurrency
cancellation are set at workflow level.

The job graph is:

```text
quality ----\
tests -------+--> package-smoke
integration -+
container ---/
```

- **quality** (Python 3.12) checks dependency consistency, imports, compilation, scoped Ruff and
  mypy validation, architecture boundaries, workflow YAML, repository hygiene, legacy workflow
  locations, credential-like content, and forbidden cache/artifact files.
- **tests** runs the product test suite on Python 3.10, 3.11, and 3.12. Architecture tests are
  excluded here because `quality` runs them once.
- **integration** uses real Redis and Qdrant service containers and verifies coordination TTL,
  tenant-filtered vector retrieval, real FastEmbed index recovery, and API lifecycle behavior.
- **container-smoke** is the only Docker job. It validates the Compose model, builds and starts the
  non-root image with the CI override, checks runtime permissions, liveness/readiness, Redis and
  Qdrant round trips, restart behavior, diagnostics, and teardown.
- **package-smoke** starts only after all four gates pass. It builds and checks distributions, then
  installs the wheel into a clean environment and verifies imports, packaged UI data, and the
  console entry point.

Artifacts are diagnostic outputs, not releases. Container logs are uploaded only after failures;
distribution artifacts are retained only for successful `main` validation. CI requires no product
credentials and performs no publishing.

## Manual release build

`.github/workflows/noesis-release.yml` is dispatch-only. It accepts an explicit validated ref and
release version, checks that the project version matches, builds and verifies distributions in a
clean environment, builds the non-root image, creates checksums and an SBOM, and can retain those
artifacts for review.

The workflow has read-only repository permissions. It does not create a GitHub Release, upload to
PyPI or GHCR, mutate a tag, or deploy. A human must first select a ref whose CI passed, inspect the
artifacts, and separately authorize any future publication process.

## Diagnosing failures

Start with the failing job's inline log. The container job always prints `docker compose ps --all`,
Noesis logs, and inspected state/health before uploading sanitized logs. See
[CI container failure analysis](CI_CONTAINER_FAILURE.md) for the repaired incident and
[containers](CONTAINERS.md) for local reproduction commands.
