# CI test-matrix failure diagnosis

## Observed failure

The reported pull-request result showed the `Credential-free default suite` step failing in the
Python 3.10, 3.11, and 3.12 matrix jobs. Installation, `pip check`, and package import succeeded;
`package-smoke` was consequently skipped by its required dependency gate.

The remote tracebacks were not inspected because the repository owner's standing instruction
prohibits interaction with GitHub Actions. Therefore the earlier remote failing test names and
exception types cannot be asserted from the screenshot alone.

## Confirmed root cause

No application or test defect is reproducible in the current working tree. The exact matrix command
passes locally on the available Python 3.10 and 3.12 interpreters with the same credential-free
environment and repository-root `NOESIS_DATA_DIR`. It would be inaccurate to invent a root cause or
change passing behavior without the earlier traceback.

The separate duplicate-run cause is confirmed: `noesis-*` branches matched the workflow's `push`
trigger while their open pull requests also matched `pull_request`.

## Evidence

- Python 3.10 exact matrix command: 172 passed, 2 legitimate optional-dependency skips.
- Python 3.12 exact matrix command: 173 passed, 1 legitimate optional-model skip.
- Architecture tests remain excluded only from the matrix and are executed by `quality`.
- The CI environment explicitly disables Discord, X, live sends, local LLM, and external LLM.
- `NOESIS_DATA_DIR` resolves to a writable repository-root test directory locally.
- The suite did not contact Discord, X, OpenAI, Ollama, Redis, or Qdrant and did not download a
  model during either matrix-equivalent run.

Python 3.11 was not installed locally, so its final result remains dependent on user-run validation.

## Repair

- Removed the `noesis-*` push trigger; feature branches now validate through their pull request
  only, while `main` retains push validation.
- Keyed concurrency by pull-request number or branch ref so obsolete runs for the same logical
  change cancel safely.
- Added repository-root virtual-environment ignore rules. No virtual-environment files are tracked.

No application code or tests were weakened or changed as part of this diagnosis.

## Regression validation

Validation includes the exact matrix test command, full tests, quality tools, architecture tests,
workflow parsing, `actionlint`, package build/check, clean wheel inspection, and repository hygiene.
The next user-triggered CI execution is required to confirm Python 3.11 and the clean Linux runner.

## Rejected hypotheses

- **General Python 3.10 incompatibility:** the exact suite passes locally on Python 3.10.
- **General Python 3.12 incompatibility:** the exact suite passes locally on Python 3.12.
- **Architecture-test duplication:** those two files are excluded from the matrix and run once in
  `quality`.
- **Package installation/import failure:** the reported jobs passed those steps before pytest.
- **A reason to bypass `package-smoke`:** its dependency gate is correct and remains unchanged.
