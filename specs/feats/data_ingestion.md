---
size: small
modified_date: 2026-07-25
implemented_git_tag: specs/feats/data_ingestion.md/implemented
---

# Data Ingestion / Enrichment using opencode

## Introduction

**Why this spec exists:**

Data ingestion and enrichment — turning a raw note into structured JSON files ready for the SSG — is the core value proposition of Resourcery.ssg. Yet it is entirely implicit: the only committed description of the process is a prompt embedded in `README.md` that says "attach your input to an LLM."

This step is:
- **Agentic** — it requires reading input, making categorisation decisions, designing a taxonomy, inferring missing metadata, choosing a visual identity, and writing structured output. This is not a single LLM call; it is a multi-step reasoning process.
- **Untestable** — there is no automated way to know whether a prompt change works without a manual trial.
- **The core promise** — if an agent cannot turn a note into valid output files, nothing downstream matters.

This spec creates:
1. **`data_ingestion.py`** — a reusable CLI module that runs the ingestion/enrichment process via opencode. It is not test code; it is a user-facing tool alongside `validate.py`, `build.py`, etc.
2. **`tests/test_data_ingestion.py`** — an E2E test that exercises `data_ingestion.py` against test fixtures and validates schema compliance.

## Current state

- Data ingestion is described in `README.md` as a manual process: "Attach your input files to your favorite LLM alongside the schemas and add this prompt."
- The prompt is **embedded inside `README.md`** — there is no standalone prompt file. Any automated tool that needs the prompt must either parse it out of the README (fragile) or duplicate it (divergence risk).
- There is **no pipeline code** — only the prompt. The `.pyc` bytecode in `__pycache__/` is a discarded prototype, not committed source.
- There is no reusable script that automates the ingestion process.
- There is no automated test that exercises this path end-to-end.
- The project has `unit`, `integration`, and `network` test markers, but no marker for agent-based / E2E tests.

## Target state

Two additions to the project:

### 1. `data_ingestion.py` — standalone ingestion tool

A CLI script (same pattern as `validate.py`, `build.py`, etc.) that automates data ingestion by orchestrating opencode as the agent.

**Inputs:**

| Argument | Description |
|----------|-------------|
| `--note` (required) | Path to the raw markdown file listing links |
| `--site-prompt` (required) | Path to a short text describing the site's purpose and target audience |
| `--schemas` (required) | Path to the schemas directory (`links.schema.json`, `site.config.schema.json`, `design.schema.json`) |
| `--prompt` (required) | Path to the ingestion prompt file (the instruction given to the agent) |
| `--model` (required) | Model name to use (e.g., `gpt-4o`, `claude-sonnet-4-20250514`) |
| `--output` (optional, default `data/`) | Directory to write the output files into |
| `--agent` (optional, default a built-in minimal agent definition) | Path to an opencode agent definition file |

**Behaviour:**
1. Creates a temporary workspace.
2. Copies the note, site prompt, and schemas into it.
3. Runs opencode with:
   - `OPENCODE_DISABLE_PROJECT_CONFIG=1`
   - The provided agent definition
   - The provided model
   - The ingestion prompt as the instruction
4. Collects the output files (`links.json`, `site.config.json`, `design.json`) from the workspace.
5. Writes them to `--output`.
6. Cleans up the workspace.
7. Exits with code 0 on success, non-zero on failure.

**Usage:**
```bash
python data_ingestion.py \
  --note my-links.md \
  --site-prompt my-purpose.md \
  --schemas schemas/ \
  --prompt prompts/data-ingestion.md \
  --model gpt-4o
```

**Poetry script entry:** `ingest = "data_ingestion:main"`

### 2. `data/testdata/` additions — test fixtures

Test data for the E2E test:

| Fixture | Location | Content |
|---------|----------|---------|
| Input note | `data/testdata/markdown/notes/` | Small raw markdown files listing ~10 links each, with varying levels of detail (some with URLs, some without, some with descriptions, some without). |
| Site prompt | `data/testdata/markdown/site_prompts/` | Short texts describing the site's purpose and target audience. Paired with notes to form scenarios. |

Notes and site prompts are separate so they can be composed into different scenarios (e.g., a sparse note with a detailed site prompt, a rich note with a concise site prompt).

### 3. `tests/test_data_ingestion.py` — E2E test

Uses `data_ingestion.py` with test fixtures and validates the output.

**What the test does:**
1. Picks a note from `data/testdata/markdown/notes/` and a site prompt from `data/testdata/markdown/site_prompts/`.
2. Calls `data_ingestion.py` (or its underlying function) into a temporary output directory.
3. Validates the output:
   - `links.json`, `site.config.json`, `design.json` exist.
   - Each file validates against its JSON Schema using the same checks as `validate.py`.
   - Cross-validation: every link's `category` exists in `site.config.navigation.categories`, IDs match `^[a-z0-9-]+$`, colors are valid hex codes, etc.
4. Reports a clear error on failure — which file is missing or which fields violate the schema.

### 4. `prompts/data-ingestion.md` — standalone prompt file

The ingestion prompt is extracted from `README.md` into a standalone file at `prompts/data-ingestion.md`. The README's "How to practically use this project" section is updated to reference this file instead of embedding the prompt inline.

The prompt itself is not specified by this document — it is carried over from the existing README content, possibly refined. This spec treats the prompt as a mutable input to the test.

### Acceptance criteria

1. `python data_ingestion.py --note ... --site-prompt ... --schemas ... --prompt ... --model gpt-4o` produces valid `links.json`, `site.config.json`, and `design.json` in the output directory.
2. `poetry run data_ingestion` works via the `ingest` script entry.
3. `poetry run pytest -m e2e` runs `test_data_ingestion.py` (and any other E2E tests).
4. **`--model` is required** — the script and test have no default model.
5. Given a ~10-link note, schemas, and a site prompt, the agent produces output files that all pass schema validation.
6. The test validates **schema compliance only** — it does not run `build.py`.
7. On failure, the test produces a clear error — which file is missing/invalid and which fields failed.
8. The test is **opt-in** — requires the `e2e` marker and `--model`; never runs in a default `pytest` invocation.
9. Multiple note/site-prompt pairs can be composed to produce different test scenarios.

### What the test is NOT

- It is **not a unit test** — it tests the whole ingestion/enrichment process end-to-end, not individual functions.
- It is **not a benchmark** — it measures correctness (does the output validate?), not speed or cost.
- It is **not a substitute for pipeline code** — once pipeline code exists (future spec), it will have its own unit tests. This test will remain useful as a regression check that the pipeline behaves as well as the agent.

## Decisions

1. **`--model` is required** — no default. Cost is explicit by design.
2. **Schema validation only** — the test stops after validating output files against the schemas. It does not run `build.py`.
3. **No caching** — E2E tests are expensive and run intentionally when something changes. No automatic skip logic.
4. **`data_ingestion.py` is a user-facing tool** — it lives at the project root alongside `validate.py` and `build.py`, not in `tests/`. It is documented and may be used directly by users who want to script their ingestion.

## Related specs

### Enables
- [specs/tests/testing.md](../tests/testing.md) — this spec adds an `e2e` test marker and a data-ingestion E2E test alongside the existing `unit`, `integration`, `network` markers.

### See also
- `README.md` — references the prompt rather than embedding it.
- `prompts/data-ingestion.md` — the standalone ingestion prompt that `data_ingestion.py` uses.

## Technical details

- The prompt is extracted from `README.md` into `prompts/data-ingestion.md`. The README's "How to practically use this project" section is updated to reference the file (`prompts/data-ingestion.md`) instead of embedding the prompt inline.
- `data_ingestion.py` uses opencode as its backend agent. It must:
  - Construct a temporary directory with the note, site prompt, and symlinked schemas.
  - Run opencode with `OPENCODE_DISABLE_PROJECT_CONFIG=1`, pointing it at the prompt file.
  - Collect the output JSON files and move them to `--output`.
  - Clean up the temporary directory (unless `--debug` is passed to preserve it).
- The agent must have filesystem access (read input + schemas, write output files) and the ability to produce structured JSON output.
- The opencode binary must be available on `PATH` (or configurable via `--opencode-path` / `OPENCODE_BINARY` env var).
- `OPENCODE_DISABLE_PROJECT_CONFIG=1` prevents the agent from loading any project-level opencode configuration that could alter its behaviour.
- The test should clean up its temporary workspace after completion (or on failure, preserve it for debugging).
- The ingestion prompt should reference the schema files by path so the agent can read them. Symlinks from the temp directory to `schemas/` keep the schemas as a single source of truth.
- Notes and site prompts live as separate files so they can be combined in different ways. A site prompt is always required — the agent needs context about purpose and audience to produce a coherent taxonomy and visual identity.
- If `data_ingestion.py` grows enough internal logic to warrant it, its core function (e.g., `run_ingestion(...)`) should be factored out so the test can call it directly without shelling out.

---

> **Note on file paths:** This spec was authored when all Python modules lived in
> the project root. As of spec
> [`refactors/src_layout_package.md`](../refactors/src_layout_package.md), the
> source code has been moved under `src/resourcery_ssg/`. References to
> `data_ingestion.py`, `validate.py`, and `build.py` as root-level files now
> refer to `src/resourcery_ssg/data_ingestion.py`, etc. The behavioural scope of
> this spec is unchanged.
