---
size: small
modified_date: 2026-08-01
implemented_git_tag: specs/refactors/ingest_module_split.md/implemented
---

# Split data_ingestion.py and Extract a Shared opencode Runner

## Introduction

`src/resourcery_ssg/data_ingestion.py` (1151 lines) contains two orchestrators —
`run_ingestion` (single-shot) and `run_multi_step_ingestion` — that duplicate,
nearly verbatim, the entire opencode subprocess plumbing: the binary check, the
command build, the environment setup, the `subprocess.run` call with its
returncode/timeout error translation, and the temp-workspace cleanup. Two
string-composition helpers (`_generate_agent_def`, `_generate_step_agent_def`)
are ~95% duplicated. This duplication is drift-prone: any future change to the
opencode invocation (flags, error text, timeout policy) must be made in
parallel at two sites, and the failure contract of "how opencode is run" is
not testable in isolation.

The goal: extract a **shared opencode runner seam** and a **prompt-composition
module**, leaving `data_ingestion.py` as pure orchestration. This follows the
established DRY-extraction pattern of
[`refactors/entry_point_deduplication.md`](entry_point_deduplication.md)
(implemented) and keeps the entire public API importable, so no consumer
breaks.

## Current state

All line references verified against `src/resourcery_ssg/data_ingestion.py`
at HEAD (1151 lines).

### Module layout

| Function | Lines | Role |
|----------|-------|------|
| `_generate_agent_def(work_dir, schemas_dir)` | 42-68 | Agent-def YAML for single-shot (three output files) |
| `_read_file(path)` | 71-80 | `path.read_text(encoding="utf-8")` |
| `_generate_step_agent_def(work_dir, schemas_dir, step_name, output_file)` | 83-113 | Agent-def YAML for one step (single output file) |
| `_compose_step_instruction(...)` | 116-179 | Step instruction composer (multi-step only) |
| `run_ingestion(...)` | 182-384 | Single-shot orchestrator |
| `_resolve_stage_setting(...)` | 387-401 | Per-stage cascading setting (multi-step only) |
| `build_stage_config(...)` | 404-467 | Stage-config parser (raises `ResourceryError` on unknown key) |
| `run_multi_step_ingestion(...)` | 470-942 | Multi-step orchestrator with retry loop + cross-validation |
| `main()` | 945-1147 | CLI entry point |

### Duplication inventory (orchestrator A → orchestrator B)

| Block | `run_ingestion` | `run_multi_step_ingestion` |
|-------|-----------------|----------------------------|
| `shutil.which` binary check → `FileNotFoundError` ("opencode binary '...' not found on PATH ...") | 224-229 | 523-528 |
| Schema-reading loop (`SCHEMA_FILES`, exists check, read) | 237-244 | 535-542 |
| `env = os.environ.copy()`; `env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"` | 307 | 762 |
| Command build `[bin, "run", "Execute the instructions in the attached file.", "--file", f, "--model", m, "--agent", a, "--auto", "--dir", d]` | 309-318 | 764-773 |
| DEBUG logs (Command / Working directory / Instruction file) | 320-322 | 775-777 |
| `subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=OPENCODE_TIMEOUT)` + returncode≠0 → `RuntimeError` (exit code + stdout + stderr) | 324-340 | 782-798 |
| Output-file existence check | 343-357 (all `REQUIRED_OUTPUTS`, own message) | 800-806 (per-step, own message) |
| `except subprocess.TimeoutExpired` → `RuntimeError` (identical message) | 377-381 | 935-939 |
| `finally:` `shutil.rmtree(tmp_dir_obj, ignore_errors=True)` unless `debug` | 382-384 | 940-942 |

### Agent-def generator duplication

`_generate_agent_def` and `_generate_step_agent_def` share the identical
frontmatter block (name/description aside) and the identical permission block
(read `schemas_dir`, write/edit/bash `work_dir`, webfetch/websearch allow).
They differ only in:

| Aspect | `_generate_agent_def` | `_generate_step_agent_def` |
|--------|-----------------------|----------------------------|
| Agent name | `data-ingestion` | `data-ingestion-{step_name}` |
| Description | `Data ingestion agent` | `generate the output file {output_file}` |
| Body phrasing | "...generate the three output files (links.json, site.config.json, design.json) at the exact absolute **paths** ... produce the output **files**." | "...generate the output file {output_file} at the exact absolute **path** ... produce the output **file**." |

### Consumers (verified)

| Consumer | Location | Imported names | Impact |
|----------|----------|----------------|--------|
| `site.py` `_run_ingest()` | 324-328 | `run_ingestion`, `run_multi_step_ingestion`, `build_stage_config` | none — all stay |
| `tests/test_data_ingestion.py` | 13-19 | `run_ingestion`, `run_multi_step_ingestion`, `_resolve_stage_setting`, `build_stage_config`, `main as ingestion_main` | none — all stay |
| `tests/test_data_ingestion.py` | 227-230 | `REQUIRED_OUTPUTS`, `run_multi_step_ingestion` | none |
| `tests/test_data_ingestion.py` | 247-250 | monkeypatches `"resourcery_ssg.data_ingestion.subprocess.run"` | **moves** to the new seam (see Target state) |
| `tests/test_data_ingestion.py` | 524-527 | monkeypatches `"resourcery_ssg.data_ingestion.run_ingestion"` | none — name stays valid |
| `tests/test_site.py` | 142 | `build_stage_config` (via `_patch_ingestion_module`) | none |

No test imports the private helpers (`_compose_step_instruction`,
`_generate_step_agent_def`, `_generate_agent_def`, `_read_file`) — verified by
grep. Nothing imports `OPENCODE_TIMEOUT` or `SCHEMA_FILES` outside the module —
verified by grep.

### Retry loop (stays put)

The retry-with-validation-feedback loop exists **only** in
`run_multi_step_ingestion` (726-884). It uses `DataValidator` (from
`validate.py`, which stays) for per-step schema validation and final
cross-validation, and `io_utils.loads_json` / `JsonLoadError` for the
invalid-JSON retry path (per `entry_point_deduplication.md`).

## Target state

### New module: `src/resourcery_ssg/opencode_runner.py`

The single home for "how opencode is invoked". Small, single-purpose module
(precedent: `io_utils.py`, `errors.py`), using `logutil.get_logger(__name__)`
and the project docstring format (`specs/docs/docstring.md`). It contains:

- `OPENCODE_TIMEOUT = 300` — module constant **moved from
  `data_ingestion.py`** (must move: `data_ingestion` will import this module,
  so the constant cannot stay there without a circular import; no external
  importers exist, verified).
- `resolve_opencode_bin(opencode_bin: str) -> str` — the `shutil.which`
  check. Returns the resolved binary path; raises `FileNotFoundError` with
  the exact current message ("opencode binary '{opencode_bin}' not found on
  PATH. Use --opencode-path or set PATH accordingly."). Both orchestrators
  call it instead of the duplicated blocks (224-229 / 523-528).
- `run_opencode(instruction_file, model, agent_def_file, work_dir,
  timeout=OPENCODE_TIMEOUT) -> CompletedProcess` — owns, in order:
  1. Environment setup: `os.environ.copy()` +
     `env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"`.
  2. Command build: the exact current argv
     `[bin, "run", "Execute the instructions in the attached file.", "--file",
     str(instruction_file), "--model", model, "--agent", str(agent_def_file),
     "--auto", "--dir", str(work_dir)]`.
  3. The DEBUG logs currently duplicated at 320-322 / 775-777 (Command,
     Working directory, Instruction file).
  4. `subprocess.run(cmd, capture_output=True, text=True, env=env,
     timeout=timeout)`.
  5. `returncode != 0` → `RuntimeError` with the exact current formatting
     ("opencode process failed with exit code {rc}." + stdout/stderr blocks).
  6. `subprocess.TimeoutExpired` → `RuntimeError` with the exact current
     message ("opencode process timed out after {timeout} seconds. Check the
     model and prompt, or increase the timeout.").
- `check_outputs(work_dir, filenames) -> list[str]` — returns the list of
  filenames from `filenames` that do not exist under `work_dir` (empty list
  when all present). Callers keep their own error-message formatting:
  - single-shot (343-357): checks `REQUIRED_OUTPUTS`, keeps its
    "Missing output files: ..." message including `result.stdout`/`stderr`
    context (available from the `CompletedProcess` returned by
    `run_opencode`);
  - multi-step (800-806): checks `[output_file]`, keeps its
    "Step '{step_name}' did not produce output file: ..." message with the
    same stdout/stderr context.

**Error contract:** `RuntimeError` — identical to the orchestrators' current
documented contract (their docstrings already say `RuntimeError: If the
subprocess fails or output files are missing`). Consistent with the
raise/exit convention of the implemented `library_raise_main_exit.md`; the
CLI-visible text and exit codes are byte-identical.

### New module: `src/resourcery_ssg/ingest_prompts.py`

Pure string-composition helpers (no I/O beyond `read_file`), moved from
`data_ingestion.py`. Public names (leading underscore dropped — they are now
the module's public API):

- `generate_agent_def(work_dir, schemas_dir, *, agent_name, description,
  output_phrase)` — the two generators **merged** into one parameterized
  generator. The three differing aspects (name, description, body phrasing —
  see the duplication table) become parameters. **Contract: the two call
  sites must produce output byte-identical to today's** (i.e. the single-shot
  body keeps "the three output files (links.json, site.config.json,
  design.json) ... paths ... files", the step body keeps "the output file
  {output_file} ... path ... file").
- `compose_step_instruction(...)` — moved as-is (current signature and
  behaviour, 116-179).
- `read_file(path) -> str` — moved as-is (71-80).

### `data_ingestion.py` after the split

Keeps its **entire public API** importable: `run_ingestion`,
`run_multi_step_ingestion`, `build_stage_config`, `_resolve_stage_setting`,
`REQUIRED_OUTPUTS`, `main`. Also keeps `SCHEMA_FILES` (module-internal,
schema-reading stays in the orchestrators).

**Stays in the orchestrators** (not extracted — premature abstraction):
- The retry-with-validation-feedback loop (726-884) — single-shot has no
  retry; a generic retry util is not justified.
- The per-stage config plumbing (`_resolve_stage_setting`, stage-config
  resolution, completeness check / auto-expansion, selective execution).
- Cross-validation, output copying, and the per-run log_user progress
  messages.
- The single-shot instruction composition (265-299, inline in
  `run_ingestion`) — structurally different from `compose_step_instruction`;
  not unified.
- The `agent_path` custom-agent flow (write-or-resolve of the agent-def file,
  per orchestrator).

**Removed:** the duplicated blocks in the inventory above (all replaced by
calls to `opencode_runner.*` / `ingest_prompts.*`), the four moved helpers,
the `except subprocess.TimeoutExpired` clauses (the seam now raises
`RuntimeError`), and the imports that move out (`subprocess`, `shutil` —
unless still needed for `copy2`/`rmtree`, which stay).

### `site.py` and other consumers

**Untouched.** All names imported by `site.py:324-328`, `test_site.py:142`
and `test_data_ingestion.py` remain importable from `data_ingestion.py`.

### Test changes (explicitly permitted by the CLEAN BREAK decision)

| Test | Change |
|------|--------|
| `tests/test_data_ingestion.py:247-250` (`test_multi_step_emits_stage_records`) | Patch target moves from `"resourcery_ssg.data_ingestion.subprocess.run"` to `"resourcery_ssg.opencode_runner.subprocess.run"` (recommended — the fake's `cmd`-parsing to find `--dir` keeps working unchanged). Patching `run_opencode` is an acceptable alternative; the existing test structure favours the subprocess level. |
| All other existing tests | No change required (verified import surface above). The `shutil.which` patch at 250 still intercepts: `resolve_opencode_bin` calls `shutil.which` via the module attribute, which the global string-target patch covers. |
| New tests | May target the runner seam (e.g. `resolve_opencode_bin` not-found path, `run_opencode` command-build/returncode-formatting/timeout translation, `check_outputs` happy/missing paths) — the seam is an explicitly better test target because tests can assert on the built command. |

### Acceptance criteria

1. All existing tests pass (pytest unit + integration; e2e unchanged).
2. `run_ingestion` and `run_multi_step_ingestion` contain no
   `shutil.which` call, no `subprocess.run` call, no
   `OPENCODE_DISABLE_PROJECT_CONFIG` assignment, and no
   `except subprocess.TimeoutExpired` — grep-verifiable.
3. `site.py` is byte-unchanged; no import of `data_ingestion` names outside
   the module breaks.
4. The two agent-def call sites produce byte-identical files to today's.
5. CLI behaviour is byte-identical: same messages, same streams, same exit
   codes (including `main()`'s `except (FileNotFoundError, RuntimeError)` →
   `sys.exit(1)` handling, unchanged).

## Decisions

1. **CLEAN BREAK, no re-export shims** (user-approved). Consumers are updated
   in the same change. The only affected consumer is the single test patch
   target above; `site.py` needs no edit at all.
2. **The retry loop stays in `run_multi_step_ingestion`** (user-approved). No
   generic retry util — single-shot has no retry, premature abstraction.
3. **DRY merge of the agent-def generators** (user-approved). One
   parameterized generator; the safety property is byte-identical output at
   both call sites, so the merge is pure dedup with zero behavioural risk.
4. **`OPENCODE_TIMEOUT` moves to `opencode_runner.py`** — required to avoid a
   circular import (`data_ingestion` → `opencode_runner` → `data_ingestion`).
   Verified safe: nothing outside the module references it.
5. **Error contract of the seam is `RuntimeError`** with the exact current
   message texts — preserves the documented contract of both orchestrators
   and the CLI-visible behaviour frozen by the implemented feature specs.
6. **`check_outputs` returns data; callers format errors** — the two
   orchestrators' missing-file messages differ and are both pinned; the seam
   only answers "which of these files are absent".

## Open questions

1. **Merged generator parameterization** — the spec pins the contract
   (byte-identical output, three differing aspects as parameters) but leaves
   the exact parameter names/split (e.g. whether the body phrase is one
   parameter or two: "the three output files (...)" vs "the output file X" +
   plural path/files phrasing) to the planner. No behavioural impact either
   way. *Non-blocking.*
2. **Test patch target** — `opencode_runner.subprocess.run` (recommended,
   minimal diff) vs `opencode_runner.run_opencode`. *Non-blocking;
   recommendation in the spec.*
3. **Multi-step per-step existence check via `check_outputs`** — included in
   the target state (single call site replacing 800-806, message text
   preserved). Flagged in case the user prefers to leave the multi-step
   check inline; the spec assumes the DRY-consistent choice. *Non-blocking.*

## Related specs

### Depends upon
- None. (`DataValidator` stays in `validate.py`; a companion spec
  `specs/refactors/validate_module_split.md` is being drafted in parallel —
  no ordering constraint between the two.)

### Enables
- A future 7-step `orchestrate.py` per
  [`refactors/data_design_split.md`](data_design_split.md) (implemented) —
  caveat: that spec's orchestrator calls an OpenAI-compatible API, not an
  opencode subprocess, so this seam is a *potential* consumer only if that
  design is revisited; do **not** design for it beyond the clean API here.
- [`feats/bookmark_import.md`](../feats/bookmark_import.md) (stub, roadmap
  Phase B) — feeds the pipeline input stage; the clean seam keeps the ingest
  module open for that extension. No constraint.

### Extends
- [refactors/entry_point_deduplication.md](entry_point_deduplication.md)
  (implemented, tag
  `specs/refactors/entry_point_deduplication.md/implemented`) — that spec
  established the shared-helper extraction pattern for this codebase and
  already pulled `build_stage_config` / CLI-override / JSON-loading helpers
  out of the modules; this spec applies the same pattern to
  `data_ingestion.py`'s remaining internal duplication. Implemented specs are
  immutable, so this is a new spec rather than an amendment.
- [feats/data_ingestion.md](../feats/data_ingestion.md),
  [feats/multi_step_ingestion.md](../feats/multi_step_ingestion.md),
  [feats/per_stage_configuration.md](../feats/per_stage_configuration.md)
  (all implemented) — the feature stack that froze `data_ingestion.py`'s
  public API, CLI surface, and error behaviour; this spec preserves all of it
  while restructuring internals.

### Supersedes
- None.

## Technical details

- **Circular-import avoidance:** `data_ingestion.py` imports
  `opencode_runner` and `ingest_prompts`; neither new module may import from
  `data_ingestion`. `OPENCODE_TIMEOUT` therefore lives in `opencode_runner`
  (see Decisions). `REQUIRED_OUTPUTS` / `SCHEMA_FILES` stay in
  `data_ingestion` and are passed as arguments to `check_outputs` where
  needed.
- **Pinned message texts** (byte-identical, do not reword): the binary
  not-found message (224-229), the returncode error (333-340), the timeout
  message (378-381), the single-shot missing-outputs message (349-357), the
  multi-step missing-output message (802-806). The multi-step DEBUG log line
  "Step: {step_name}, attempt: {attempt}/{max}" (778-780) is orchestrator
  context and **stays** in the retry loop; only the Command/Working
  directory/Instruction file lines move into `run_opencode`.
- **Docstrings:** new modules and functions follow `specs/docs/docstring.md`
  (`param:` / `Returns:` / `ExceptionName:` sections, in the strict format);
  `run_opencode` documents `RuntimeError` conditions.
- **Logging:** new modules use `logutil.get_logger(__name__)` (the
  logging-infrastructure refactor, commit `596f1ca`, is the current
  convention); user-facing progress messages (`log_user`) stay in the
  orchestrators.
- **Test seam note:** the existing fake in
  `test_multi_step_emits_stage_records` parses `cmd[cmd.index("--dir") + 1]`
  to locate the work dir and writes an invalid `links.json` there. Patching
  `resourcery_ssg.opencode_runner.subprocess.run` preserves that structure
  exactly; the test's other assertions (INFO/DEBUG records from the retry
  loop) are unaffected because the retry loop stays in the orchestrator.
- **No packaging changes:** both new modules are internal — no new
  `pyproject.toml` scripts or dependencies.
- **Not part of any roadmap** (`roadmaps/discovery_mvp.md` has no entry for
  this work; it is a pure code-quality refactor on the existing pipeline).
