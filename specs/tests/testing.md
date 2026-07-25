---
size: small
modified_date: 2026-05-10
implemented_git_tag: d45343d
---

# Unit and integration testing of all python functions

## Current state

There are no tests. Every change in code or configuration could be catastrophic.

## Target state

### Requirements

- **Framework:** pytest with custom markers (`unit`, `integration`, `network`).
- **Unit tests:** Every non-trivial function and method across all 5 Python files has at least one passing unit test.
- **Integration tests:** Each of the 4 workflow action scripts (`validate.py`, `font_acquirer.py`, `image_acquirer.py`, `build.py`) has a passing integration test that runs the action end-to-end.
- **Test data:** A minimal but valid set of input files lives in `data/testdata/` and is committed to git. No test reads from the real `data/` directory.
- **Network isolation:** All tests pass without an internet connection. Network calls are mocked for unit and integration tests.
- **Network smoke tests:** Optional `network`-marked tests may make real network calls (e.g., against Google Fonts API). These are skipped by default and opt-in only.
- **Test infrastructure:** All test files, fixtures, and configuration live inside `tests/`. No changes to the project root aside from adding a `[tool.pytest.ini_options]` section to `pyproject.toml`.
- **`theme_constants.py`:** Unit tests only — it is a shared utilities module, not a workflow action. No integration test.

### Constraints

- Tests must not depend on the real `data/` directory — only `data/testdata/`.
- Tests must not make real network calls (except `network`-marked smoke tests).
- Test infrastructure must not leak into source code — no test-only imports or branches in production code.
- The existing build pipeline (`validate → fonts → images → build`) must remain untouched. Tests validate the code as it is.

### Acceptance criteria

1. `poetry run pytest -m "not network"` exits with code 0.
2. Every function in the 5 Python files (except trivial getters/setters and dunder methods) has at least one unit test.
3. Each of the 4 workflow actions has an integration test that runs it against `data/testdata/` and completes without error.
4. All tests pass when run on a machine with no internet connection.
5. `network`-marked tests are skipped unless `--network` is explicitly passed.
