---
size: large
modified_date: 2026-08-01
implemented_git_tag: specs/refactors/logging_infrastructure.md/implemented
---

# Logging Infrastructure for Python CLI and JS Frontend

## Introduction

Resourcery.ssg emits all of its operational output through 177 ad-hoc
`print()` calls spread across 7 Python modules, plus 2 bare `console.warn()`
calls in the frontend. There is no logging system: no levels, no timestamps,
no record of what happened during a run, no way to turn verbosity up or down,
and inconsistent stream usage (some modules print errors to stdout, others to
stderr). Debugging a failed build or an LLM ingestion run requires re-running
with the terminal open and eyeballing interleaved output.

The goal is to replace all ad-hoc output with a proper logging system **in
both languages**: stdlib `logging` on the Python side (zero new dependencies),
a small console-only `logger.js` module on the JS side. Messages gain
structured metadata (timestamp, module, function), levels are configurable per
output sink (console vs. file), and every command writes a per-run log file.
Crucially, user-facing UX messages (step progress, summaries, per-image
progress) are **also** migrated into the logger at a dedicated user-facing
level — nothing stays outside the logger.

This spec deliberately does not touch the failure *mechanism* established by
`library_raise_main_exit.md` (library functions raise `ResourceryError`;
entry points exit 1). It only relocates how messages are *emitted* — which
that spec explicitly deferred to this one.

## Current state

### Python: 177 `print()` calls, no levels, no persistence

| Module | print calls | Typical content | Stream today |
|--------|-------------|-----------------|--------------|
| `data_ingestion.py` | 39 | `⚡ Running single-shot data ingestion...`, `🧩 Starting multi-step...`, `✅ Ingestion complete!`, `📁 Output files: ...`, `⚠️  {err}` warnings, `Error: ...` lines, LLM context lines (`Command: ...`, `Working directory: ...`, `Instruction file: ...`, `Step: ..., attempt: ...`) | mostly stderr |
| `site.py` | 32 | `STEP {n}/{m}: Ingest` headers with `=` separators, `✓ ... passed`, `❌ ... Aborting pipeline.`, `✅ Pipeline complete!`, skip warnings (`⚠️  No 'ingest' section ...`) | stdout / stderr |
| `validate.py` | 27 | per-file result lines, collected validation errors | stdout |
| `image_acquirer.py` | 27 | per-image acquisition progress, `⚠️  Links file not found: ...` | stdout |
| `build.py` | 25 | `🔨 Building static site...`, `✓ index.html rendered (landing page)`, `✅ Build complete!`, `📁 Output directory: ...`, attribution error messages | stdout (errors too) |
| `font_acquirer.py` | 17 | acquisition progress, `⚠️  Some fonts failed — ...` | stdout |
| `js_vendor.py` | 10 | `Error: ...` messages | stderr |
| **Total** | **177** | | inconsistent |

Problems:

1. **No levels.** Nothing distinguishes "progress", "warning", "error", or
   "debug detail" — every message has the same weight and cannot be filtered.
2. **No persistence.** When a run fails, its output is gone. There is no
   log file, no timestamp, no way to answer "what happened on the last run?".
3. **Inconsistent streams.** `build.py` errors go to stdout, `js_vendor.py`
   and `data_ingestion.py` errors go to stderr, `site.py` mixes both. Shell
   users cannot rely on `2>` or `1>` semantics.
4. **No metadata.** A printed message carries no timestamp, module, or
   function; nothing is attributable after the fact.
5. **`data_ingestion.py` is the worst offender**: UX status, warnings, errors,
   and debug context (command lines, working dirs, attempt counters) all
   interleave on the same stream.

### JS: 2 bare `console.warn` calls

| Site | Message |
|------|---------|
| `static/js/modules/modal-manager.js:19` | `⚠️ Modal elements not found` (defensive DOM guard) |
| `static/js/modules/tag-manager.js:111` | `⚠️ Filter header elements not found` (defensive DOM guard) |

Both are defensive "DOM element missing" warnings with no module context, no
level discipline, and no way for tests to assert on them except spying on
`console.warn` directly (`tests/js/unit/tag-manager.test.js:200`).

### Config surface today

`load_resourcery_config()` (`src/resourcery_ssg/config.py`) already
implements the full priority chain (CLI dotted-key overrides → env/.env →
user `--config` → committed `config.yaml`) with `${VAR}` resolution and a
`vars:` section. A new top-level `logging:` section rides this mechanism
unchanged. `site.py` maps CLI flags to config keys via
`ARG_TO_CONFIG_KEY` / `COMMAND_FLAGS` + `build_cli_overrides()`.

Note: `site` already has a `--debug` flag (`store_true`) on the `ingest` and
`all` subparsers — it controls **opencode verbosity** (`ingest.debug`), not
log levels. It is unrelated to this spec and stays as-is.

## Target state

### Principles

1. **All output flows through the logger.** Every one of the 177 `print()`
   calls and the 2 JS `console.warn` calls is migrated. No message is emitted
   outside the logging system.
2. **Levels, both languages:** `DEBUG`, `INFO`, `WARN`, `ERROR`, plus the
   custom user-facing level `INFO_USER` (Python only, see below).
3. **Structured metadata per Python record:** timestamp, module (logger name
   = module path), function name, line number. The console formatter renders
   them; the `INFO_USER` level is the exception (plain text, no metadata).
4. **Configurable thresholds per sink.** Console verbosity and file verbosity
   are independent (`logging.level` vs. `logging.file_level`). E.g. console at
   `INFO` while the file gets `DEBUG`.
5. **Zero new dependencies** (stdlib `logging` only), consistent with the
   project's minimal-deps philosophy.
6. **Log files are per-run, not rotated by the program.** A timestamped file
   per invocation; rotation is an external concern (e.g. `logrotate`).
7. **The failure mechanism is untouched.** Library functions still raise
   `ResourceryError`; entry points still catch and `sys.exit(1)`. The
   logged message text and the exception message stay the same string.

### Python: new module `src/resourcery_ssg/logutil.py`

The module cannot be named `logging.py` (stdlib shadowing hazard).
**Decision (flagged):** name it `logutil.py` — short, unambiguous, and
consistent with the existing `io_utils.py` convention.

Public API:

- `setup_logging(config)` — called **once** by every entry point (`main()`s
  and `site.py` dispatch), immediately after
  `load_resourcery_config()`. Reads the `logging:` config section, attaches
  the console and file handlers described below, and sets the root logger
  level to the minimum of the two thresholds.
- `get_logger(name)` — returns a stdlib logger named after the module
  (`get_logger(__name__)` in every module), attached to the handlers
  configured by `setup_logging`. Works without `setup_logging` (stdlib
  default behavior: unconfigured loggers emit WARNING+ via the lastResort
  handler), so library functions remain usable programmatically.
- `INFO_USER` — module constant, level **25** (above INFO, below WARN).
- `log_user(msg)` or equivalent helper for `INFO_USER` emission — plain text
  UX messages; see below.

#### Levels

| Level | Value | Purpose |
|-------|-------|---------|
| `DEBUG` | 10 | Deep detail: LLM context lines, command echoes, per-item internals |
| `INFO` | 20 | Operational detail that is *not* user-facing UX copy |
| `INFO_USER` | 25 | User-facing UX copy: step progress, summaries, per-image progress |
| `WARN` | 30 | Recoverable problems, retries, skipped steps |
| `ERROR` | 40 | Failures (including every site that raises `ResourceryError`) |

#### Formatter (structured records)

Console and file records use one formatter with the shape:

```
2026-08-01 14:03:22 | INFO  | resourcery_ssg.build:139 build_site | Building static site...
```

i.e. `%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d %(funcName)s | %(message)s`.
The exact separators are at the implementer's discretion, but **all four
fields must be present and stable** (tests assert on them).

#### Stream split

A single, uniform convention replaces today's per-module stream chaos:

| Levels | Stream |
|--------|--------|
| `DEBUG`, `INFO`, `INFO_USER` | **stdout** |
| `WARN`, `ERROR` | **stderr** |

**Decision (flagged):** this is a deliberate behavior change for some
messages — e.g. `build.py` error messages move stdout→stderr, and
`data_ingestion.py` UX copy moves stderr→stdout. The uniform convention wins
over per-site stream preservation (which `library_raise_main_exit.md`
froze only as a stopgap pending this spec). Tests asserting on `capsys`
streams must be updated accordingly (see Test implications).

#### `INFO_USER` (level 25) — the user-facing level

- **Console rendering: plain text only** — no timestamp, no level prefix, no
  module. Exactly what the UX copy looks like today (`✓ index.html
  rendered (landing page)`, `STEP 1/5: Validate`, `📁 Output files: ...`).
- **stdout only.**
- **Never written to log files.** The file handler must filter out level-25
  records regardless of `file_level` (which may be `DEBUG`).
- **Visible whenever the console threshold is `DEBUG` or `INFO`**; hidden when
  the console threshold is `WARN` or `ERROR`.
- All user-facing UX messages migrate here: `site.py` STEP headers and
  `✓/❌/✅` pipeline lines, `build.py` progress lines, `data_ingestion.py`
  status/completion lines, per-image progress in `image_acquirer.py`, etc.

#### Log files

- **Location:** `logging.logs_dir`, default `./logs` (via
  `vars: LOGS_DIR: ./logs`). **Not under `output/`** — `build.py` deletes
  and recreates `output/` on every run, so logs there would be destroyed.
  Relative to CWD, consistent with the existing config convention.
  `logs/` is added to `.gitignore`.
- **Filename:** one timestamped file per run,
  `resourcery-YYYYMMDD-HHMMSS.log` (sortable, no collision between runs).
- **Content:** all records at `file_level` or above, **including** `DEBUG`
  detail, **excluding** `INFO_USER`.
- **No rotation logic in the program.** No `RotatingFileHandler`, no cleanup
  of old runs. External tooling (logrotate) owns rotation.
- **Decision (flagged):** **every command writes a log file** — `validate`,
  `build`, `acquire-fonts`, `acquire-images`, `acquire-js`, `ingest`, and
  each `site` subcommand. Each is a standalone CLI with its own entry point;
  a per-run file is the uniform contract. `site all` writes one file for the
  whole pipeline invocation.
- The logs directory is created on demand (mkdir parents) if missing.

### Config integration

A new top-level `logging:` section in the committed `config.yaml`, flowing
through the **existing** priority chain with zero config.py changes:

```
--log-level DEBUG            (CLI, highest)
  ↓
LOG_LEVEL=DEBUG  (env/.env — via ${VAR} resolution against vars: LOG_LEVEL)
  ↓
user config.yaml logging.level
  ↓
committed config.yaml logging.level (default INFO)
```

Committed default (bundled in the package):

```yaml
vars:
  LOGS_DIR: ./logs
  LOG_LEVEL: INFO
logging:
  level: ${LOG_LEVEL}        # console threshold: DEBUG | INFO | WARN | ERROR
  file_level: DEBUG          # file threshold (INFO_USER never reaches the file)
  logs_dir: ${LOGS_DIR}
```

Notes:

- `vars: LOG_LEVEL` participates in `${VAR}` resolution exactly like the
  existing `STATIC_DIR` etc.: an env var of the same name overrides the
  committed default. `LOG_LEVEL` and `LOGS_DIR` are the two new env vars.
- Level strings (`DEBUG`, `INFO`, ...) contain no `/`, so
  `_resolve_paths()` in `config.py` leaves them as strings; `logs_dir`
  resolves to a `Path` like every other path. No changes to `config.py`
  required.
- Values accepted (case-insensitive): `DEBUG`, `INFO`, `WARN`, `ERROR`.
  `WARNING` is accepted as an alias for `WARN`. `INFO_USER` is not a
  configurable threshold (it is governed by the console threshold, see
  above).

### CLI surface: `--log-level`

| Flag | Config key | Values | Where |
|------|-----------|--------|-------|
| `--log-level` | `logging.level` | `DEBUG`/`INFO`/`WARN`/`ERROR` (case-insensitive) | every command parser **and** every `site` subparser (`build`, `validate`, `acquire-fonts`, `acquire-images`, `acquire-js`, `ingest`, `all`) |

Implementation note: `--log-level` must end up as the dotted-key override
`{"logging.level": value}` in `load_resourcery_config()`. The existing
`build_cli_overrides()` helper is command-scoped (`{command}.{key}`); the
`logging` section needs its own section prefix, so this is a small extension
of the flag-mapping pattern in `site.py` and the standalone `main()`s, not a
change to the priority chain itself.

### Python migration rubric (177 print calls)

Each module's prints are classified with this rubric; the mechanical
per-call classification is the implementer's job:

| Level | Applies to |
|-------|-----------|
| `INFO_USER` | UX progress and results: `🔨 Building...`, `✓ index.html rendered`, `STEP {n}/{m}: ...` headers, `✅ ... complete!`, `📁 Output files: ...`, per-image progress, `• filename` listings, validation summary lines |
| `INFO` | Operational non-UX detail (sparingly; most operational detail is DEBUG) |
| `DEBUG` | LLM context lines (`Command: ...`, `Working directory: ...`, `Instruction file: ...`, `Step: ..., attempt: ...`), command echoes, internals |
| `WARN` | Retry warnings (`⚠️  {err}`, `⚠️  {w}`), skips (`⚠️  No 'ingest' section ...`), warn-and-continue findings (e.g. `image_acquirer` missing-links warning), collected validation **findings** (validate.py's error list) |
| `ERROR` | Fatal-failure messages, including every message that precedes a `ResourceryError` raise (the logged text and the exception text are the same string) |

| Module | Prints | Notable assignments |
|--------|--------|---------------------|
| `data_ingestion.py` | 39 | status/summary → `INFO_USER`; `⚠️` → `WARN`; `Error:` → `ERROR`; command/working-dir/instruction-file/attempt lines → `DEBUG` (see LLM decision below) |
| `site.py` | 32 | STEP headers + `✓/✅` pipeline lines → `INFO_USER`; `❌ ... Aborting pipeline.` → `ERROR`; skip warnings → `WARN` |
| `validate.py` | 27 | per-file/result summary → `INFO_USER`; collected errors/findings → `WARN` |
| `build.py` | 25 | progress/`✓`/`📁` lines → `INFO_USER`; attribution + missing-file failures → `ERROR` (text shared with `ResourceryError`) |
| `image_acquirer.py` | 27 | per-image progress → `INFO_USER`; `⚠️ Links file not found` (bool-return path) → `WARN` |
| `font_acquirer.py` | 17 | progress → `INFO_USER`; download-failure warning → `WARN` |
| `js_vendor.py` | 10 | all `Error: ...` → `ERROR` (stderr) |

Retry warnings honor the format pinned by
`feats/multi_step_ingestion.md` (`  ⚠️  Step {n}/{m} '{name}' failed
validation — retry {a}/{m}`) — now emitted at `WARN` with text preserved.

### Operational INFO/DEBUG record layer

QA of the implemented refactor found a design gap: the 177-print migration
re-classified existing messages into mostly `INFO_USER` (25), `WARN` (30),
and `ERROR` (40). `INFO` gained **zero** emission sites and `DEBUG` only the
`data_ingestion.py` context lines. Consequence: a successful run of most
commands at `--log-level DEBUG` writes a near-empty (or 0-byte) log file,
because level-25 records — the bulk of the output — are hard-excluded from
files by design. This section closes the gap by specifying the
**operational record layer**: new `INFO`/`DEBUG` records that document what
each command actually did. It adds emission sites only; it changes no
existing decision (the 9 flagged decisions in the Decisions section remain
in force).

#### Principles

1. **Every command guarantees a non-empty, useful log file.** A successful
   run of any command (`validate`, `build`, `acquire-fonts`,
   `acquire-images`, `acquire-js`, `ingest`, `site <cmd>`, `site all`) at
   `--log-level DEBUG` must leave a greppable record of what happened —
   paths, counts, phases, timings — even though `INFO_USER` copy never
   reaches the file. A 0-byte log file after a successful run is a defect.
2. **No new UX copy.** `INFO`/`DEBUG` records are for the log file and debug
   consoles. No emojis, no `✓`/`❌`/`📦` decorations, no duplication of
   `INFO_USER` message text. Plain operational prose with concrete data
   (counts, paths, names, durations).
3. **DEBUG = per-item internals; INFO = per-phase operational summary.** A
   phase emits **exactly one** `INFO` record with aggregate counts; its
   per-item detail lives at `DEBUG`. The existing `data_ingestion.py` `DEBUG`
   context lines (command, working directory, instruction file, step/attempt)
   are the style template.
4. **Records must be deterministic and testable.** Timings appear but are
   never asserted by value (presence only). Message text carries only data
   tests can pin: fixture-derived counts, configured paths, resolved names.
   Absolute paths use the same CWD-relative resolution the code already uses,
   so tests can construct them.
5. **Library functions emit records freely; setup is still the entry point's
   job** (unchanged from the API contract above). Records are emitted at the
   data-owning site — a function logs the counts it computed, the path it
   resolved — via `get_logger(__name__)` and plain `logger.info(...)` /
   `logger.debug(...)`. No central reporting module, no record-aggregation
   pass.

#### Emission shape

| Level | Frequency | Shape | Example |
|-------|-----------|-------|---------|
| `INFO` | once per phase, **after** the phase completes | `{Action} {counts} ({details})` | `Rendered 4 templates` |
| `INFO` | once per command, before exit | `Command completed in {s}s` | `Command completed in 3.4s` |
| `DEBUG` | once per item / decision | `{Item}: {action} {data}` | `Rendering index.html from templates/index.html` |

Per-phase `INFO` summaries are emitted only on phase completion: a phase that
fails mid-way leaves its `DEBUG` detail but no misleading summary record
(the failure is already covered by its `WARN`/`ERROR` record).

#### Timings (flagged decision 10)

Elapsed-time records are **included**, via a small `logutil.py` helper — a
`@log_timing` decorator or `timed` context manager wrapping the phase, built
on `time.perf_counter` with one-decimal rounding (`3.4s`). Per-phase elapsed
at `DEBUG`; one per-command elapsed at `INFO` (`Command completed in 3.4s`)
emitted by the entry point after the work, before exit. Rationale: the
per-run log file's support value is answering "how long did each phase
take?"; the cost is trivial; determinism holds because tests assert
presence, never values.

#### Per-module records

**`site.py`**

| Level | Site | Record | Example |
|-------|------|--------|---------|
| `INFO` | dispatch, after config load | `Dispatch: {command} (config {path})` — `{path}` only when a user `--config` was supplied, `(committed defaults)` otherwise | `Dispatch: build (config userdata/tech/config_ui.yaml)` |
| `DEBUG` | `main()`, after resolution | `Config overrides: {sorted dotted key=value pairs}` | `Config overrides: build.output_dir=/tmp/out, logging.level=DEBUG` |
| `DEBUG` | `_run_all()` staging step | `Staging: seeded {source} → {dest} ({n} files)` | `Staging: seeded ./static → output/staging (41 files)` |
| `DEBUG` | `_run_all()` per step | `Step '{name}' completed in {s}s` | `Step 'validate' completed in 0.4s` |

Skip decisions are **not** duplicated at `DEBUG` — the existing `WARN` skip
records (`⚠️  No 'ingest' section ...`) are the single source (flagged
decision 11).

**`build.py`**

| Level | Site | Record | Example |
|-------|------|--------|---------|
| `INFO` | after render phase | `Rendered {n} templates` | `Rendered 4 templates` |
| `INFO` | after copy phase | `Copied {n} files: images {i}, js {j}, fonts {k}` | `Copied 26 files: images 14, js 8, fonts 4` |
| `INFO` | after token generation | `Generated {n} CSS custom properties` | `Generated 63 CSS custom properties` |
| `DEBUG` | per template render | `Rendering {name} from {source}` | `Rendering index.html from templates/index.html` |
| `DEBUG` | per copy batch | `Copied {n} files: {source} → {dest}` | `Copied 8 files: ./static/js → output/js` |
| `DEBUG` | fonts.css decision | `fonts.css: {using generated file {path}|found existing file {path}}` | `fonts.css: using generated file static/css/fonts.css` |
| `DEBUG` | before output-dir clean | `Removed {n} files from {output_dir}` | `Removed 12 files from output/tech` |

**`validate.py`**

| Level | Site | Record | Example |
|-------|------|--------|---------|
| `INFO` | after schema load | `Loaded {n} schemas` | `Loaded 3 schemas` |
| `INFO` | after data load | `Validated {n} data files ({m} links)` | `Validated 3 data files (142 links)` |
| `INFO` | after cross-checks | `Cross-checks passed: {comma-separated names}` | `Cross-checks passed: categories, tags, ids, colors, urls, fonts` |
| `INFO` | at verdict | `{w} warnings, {e} errors collected` | `6 warnings, 0 errors collected` |
| `DEBUG` | per data file | `Loaded {path} ({n} records)` | `Loaded data/links.json (120 records)` |
| `DEBUG` | per cross-check | `Cross-check: {name} start` | `Cross-check: categories start` |
| `DEBUG` | per font availability check | `Font '{name}' availability: {found|missing}` | `Font 'Inter' availability: found` |

**`data_ingestion.py`** (extends its existing `DEBUG` context lines)

| Level | Site | Record | Example |
|-------|------|--------|---------|
| `INFO` | per stage, multi-step run | `Stage '{name}' (model {model}) attempt {a}/{m}` | `Stage 'design' (model opencode-go/hy3) attempt 1/2` |
| `DEBUG` | per stage, before run | `Stage '{name}' resolved config: {keys}` | `Stage 'design' resolved config: model, max_retries` |
| `DEBUG` | on retry | `Retry {a}/{m} for stage '{name}': {reason}` — reason = validation-error summary; **no wait duration** (flagged decision 13) | `Retry 1/3 for stage 'links': schema validation failed` |

The agent-transcript decision (flagged decision 2) is untouched: the
`opencode` subprocess output stays captured, never re-logged.

**`image_acquirer.py`**

| Level | Site | Record | Example |
|-------|------|--------|---------|
| `INFO` | end of run | `Acquired {a}, skipped {s}, failed {f}, total {t}` | `Acquired 8, skipped 3, failed 1, total 12` |
| `DEBUG` | per image | `Image '{name}': using {meta|screenshot|page} source ({url})` | `Image 'acme': using meta source (https://acme.com/og.png)` |

**`font_acquirer.py`**

| Level | Site | Record | Example |
|-------|------|--------|---------|
| `INFO` | end of run | `Downloaded {d} fonts, {c} from cache, {f} failed` | `Downloaded 5 fonts, 2 from cache, 3 failed` |
| `DEBUG` | per font | `Font '{name}': {cache hit {file}|downloading {url}}` | `Font 'Inter': downloading https://fonts.gstatic.com/...woff2` |

**`js_vendor.py`**

| Level | Site | Record | Example |
|-------|------|--------|---------|
| `INFO` | end of run | `Vendor file up to date: nanostores@{version}` / `Downloaded nanostores@{version}` | `Downloaded nanostores@0.11.4` |
| `DEBUG` | before resolution | `Vendor: resolved {package}@{version} from {url}` | `Vendor: resolved nanostores@0.11.4 from https://unpkg.com/nanostores@0.11.4/index.js` |

#### Console visibility of the new INFO records (flagged decision 12)

At the default console threshold (`INFO`), the new `INFO` records **do
appear on stdout**, interleaved with `INFO_USER` copy. This is intended:
they are emoji-free operational prose, informative in a verbose console, and
never UX copy. At `--log-level WARN`/`ERROR` they are hidden with everything
else; `DEBUG` records reach the console only at `--log-level DEBUG` and
reach the log file regardless (default `file_level: DEBUG`).

### JS: `static/js/modules/logger.js`

Console-only by design — browsers have no stdout/stderr/log files, and the
site ships no persistence layer. No `INFO_USER` (the level exists only for
the Python console/file split).

- `export function createLogger(moduleUrl)` — factory, called once per module
  as `const logger = createLogger(import.meta.url)`.
- **Module identity** from `import.meta.url` (basename without `.js`, e.g.
  `tag-manager`) — cheap, standard, no stack parsing.
- **Function name** via `new Error().stack` parsing **only at DEBUG level**
  (stack parsing is non-standard across engines and has measurable cost; it
  is gated behind the DEBUG level so hot paths at INFO+ never pay it).
  Best-effort: parse failure degrades to no function name, never throws.
- **Levels → console mapping:** `debug` → `console.debug`, `info` →
  `console.info`, `warn` → `console.warn`, `error` → `console.error`.
- **Console format:** `[module] message` for all levels; DEBUG additionally
  includes the caller function: `[module:function] message`. Exact
  separators are the implementer's choice but must remain stable for tests.
- The two existing `console.warn` calls migrate:
  - `modal-manager.js:19` → `logger.warn('⚠️ Modal elements not found')`
  - `tag-manager.js:111` → `logger.warn('⚠️ Filter header elements not found')`
- `logger.js` ships as a plain ESM module (no bundler, consistent with the
  existing `modules/` layout); it is imported by any module that logs.

## Decisions (flagged for user veto)

These points were ambiguous enough that a decision was required; each is
recorded so the user can veto:

1. **Module name `logutil.py`** (vs. `log.py`, `logging_utils.py`, ...) —
   chosen for brevity + consistency with `io_utils.py`. The one hard
   constraint (no `logging.py`) is respected.
2. **`data_ingestion.py` LLM output: our context lines → DEBUG, summaries →
   INFO_USER; the agent's own output is untouched.** The `opencode`
   subprocess runs with `capture_output=True` — its transcript is captured
   into the subprocess result and surfaces only inside `RuntimeError`
   messages; it is *not* ours and is not re-logged. The prints we own
   (command, working directory, instruction file, step/attempt) go to
   `DEBUG`, so a DEBUG-level run produces a complete, greppable record in
   the log file, while the console gets the INFO_USER summary. **Not**
   verbatim-INFO.
3. **Log file location `logs/` at project root (CWD), gitignored** — not
   under `output/` (build cleans it). Config-driven via
   `logging.logs_dir` / `LOGS_DIR` with the standard override chain.
4. **Every command writes a log file** — validate, build, acquire-*,
   ingest, and every `site` subcommand, each standalone CLI getting its own
   per-run file. (`site all` → one file for the whole invocation.)
5. **Uniform stream split wins over per-site stream preservation.** Some
   messages change streams vs. today (build errors → stderr; ingestion UX →
   stdout). The split `DEBUG/INFO/INFO_USER → stdout, WARN/ERROR → stderr`
   is applied globally; existing `capsys` assertions flip accordingly.
6. **`INFO_USER` visibility rule:** shown when the console threshold is
   `DEBUG` or `INFO`; plain text; stdout only; never in files. The file
   handler hard-filters level 25.
7. **`--log-level` is a new flag; the existing `site --debug` flag is
   untouched** (it controls opencode verbosity, an unrelated concern).
8. **No rotation, no retention policy in the program** — external tooling
   owns it; per-run timestamped files make that viable.
9. **No JSON/structured-output logging format** in this iteration — the
   requirement is structured *fields* in a human-readable line. A future
   machine-readable format is out of scope.
10. **Elapsed-time records are included** (from the QA follow-up on the
    operational INFO/DEBUG layer). Per-phase at `DEBUG`
    (`Step 'validate' completed in 0.4s`), per-command at `INFO`
    (`Command completed in 3.4s`), via a small `logutil.py` helper
    (decorator or context manager over `time.perf_counter`, one-decimal
    rounding). Tests assert presence only, never values. Veto option: omit
    timings entirely.
11. **Skip decisions are single-sourced at WARN — no DEBUG twin.** The
    existing `WARN` skip records (`⚠️  No 'ingest' section ...`,
    `⚠️  ingest.model not set ...`) already carry the reason; `site.py`
    uses `DEBUG` for staging / per-step elapsed / overrides instead.
12. **New INFO records are stdout-visible at the default console level —
    accepted.** They are emoji-free operational prose, informative on a
    verbose console, and never UX copy. Verified against the test suite:
    all `capsys.readouterr()` assertions are substring-style; the only
    exact-match assertion targets stderr (`tests/test_data_ingestion.py:211`,
    `.err == ""`) and stays green because the new records are INFO→stdout;
    the only absence assertion (`tests/test_site.py:330`,
    `"Aborting pipeline" not in ...out`) is string-specific. No existing
    test requires changes.
13. **Retry-backoff records carry the reason, not the wait duration.** The
    backoff may be config- or state-dependent; a duration in the message
    would be unpinnable by tests (principle 4 of the operational layer).

## Related specs

### Depends upon
- [refactors/path_configurability.md](path_configurability.md) (implemented,
  tag `specs/refactors/path_configurability.md/implemented`) — provides
  `load_resourcery_config()`, the `${VAR}` vars mechanism, and the CLI/env/
  user/committed priority chain that the new `logging:` section rides on
  unchanged. Also established that paths are CWD-relative — `logs/` inherits
  that convention.
- [refactors/library_raise_main_exit.md](library_raise_main_exit.md)
  (implemented, tag `specs/refactors/library_raise_main_exit.md/implemented`)
  — established that library functions raise `ResourceryError` and entry
  points exit. This spec builds on that mechanism: the ERROR record is
  emitted where the message is raised, the exception still carries the same
  text, and the entry-point catch-all behavior is unchanged.

### Extends
- [refactors/library_raise_main_exit.md](library_raise_main_exit.md) — that
  spec deliberately froze all `print()` sites ("Message-printing is frozen,
  not fixed") and explicitly deferred message emission to this one. This
  spec lifts the freeze and relocates emission into the logger, including
  the stream convention (its principle "same stdout/stderr streams" was a
  freeze-with-expiry, now expired).
- [feats/multi_step_ingestion.md](../feats/multi_step_ingestion.md)
  (implemented, tag `specs/feats/multi_step_ingestion.md/implemented`) —
  its retry-warning format (`  ⚠️  Step {n}/{m} '{name}' failed validation —
  retry {a}/{m}`) is preserved at `WARN` level.
- [feats/build_attribution.md](../feats/build_attribution.md) (implemented,
  tag `specs/feats/build_attribution/implemented`) — its error messages
  migrate to `ERROR` with text preserved (shared with the raised
  `ResourceryError`).

### Enables
- Future diagnostics and support workflows: per-run log files make
  bug reports self-contained ("attach `logs/resourcery-....log`").
- Future watch-mode / programmatic orchestration: `get_logger()` works
  without `setup_logging()`, so embedded callers keep sane default output.
- A future machine-readable log format, if ever needed, replaces only the
  formatter.

### Supersedes
- None (the specs above are implemented and remain valid; this spec only
  supersedes their *message-emission* provisions, which they explicitly
  carved out).

### Roadmap
- Not part of [roadmaps/discovery_mvp.md](../../roadmaps/discovery_mvp.md) —
  this is standalone infrastructure work with no roadmap phase.

## Technical details

- **`logutil.py` API shape:** `setup_logging(config)` + `get_logger(name)` +
  `INFO_USER` constant + user-level helper. Entry points call
  `setup_logging(config)` **immediately after** `load_resourcery_config()`
  and before any work; library functions never call `setup_logging()`.
- **Handler layout:**
  - Console: two `StreamHandler`s (stdout for records < `WARN`, stderr for
    `>= WARN`) or one handler with a stream-routing filter — behavior is the
    contract, not the construction. Console threshold = `logging.level`.
  - File: one `FileHandler` at `logs_dir / resourcery-YYYYMMDD-HHMMSS.log`,
    threshold = `logging.file_level`, with a filter that drops level-25
    (`INFO_USER`) records unconditionally.
  - Root logger level = `min(console threshold, file threshold)` so records
    can always reach the more verbose sink.
  - `INFO_USER` console rendering: the console formatter special-cases
    level 25 to emit `message` only (no metadata fields). All other levels
    use the structured formatter.
- **`ERROR` text and `ResourceryError`:** at every raise site, the logged
  message string and the exception message are the same local variable
  (`logger.error(msg)` then `raise ResourceryError(msg)`). The `site.main()`
  catch-all must not print additional error text (unchanged from
  `library_raise_main_exit.md`).
- **`--log-level` wiring:** each standalone `main()` gains the flag; in
  `site.py` the flag applies to all subparsers. The override dict passed to
  `load_resourcery_config()` gains `{"logging.level": value}` — note this
  needs a section prefix outside the command-scoped
  `ARG_TO_CONFIG_KEY`/`COMMAND_FLAGS` mapping (which produces
  `{command}.{key}` keys); a small dedicated mapping for the logging flag is
  the cleanest fit.
- **`--debug` collision:** the existing `site ingest/all --debug` flag
  (opencode verbosity → `ingest.debug`) is **not** repurposed as a log-level
  shortcut. New flag name is `--log-level` only.
- **config.yaml changes:** committed file gains `vars: LOGS_DIR`,
  `vars: LOG_LEVEL`, and the `logging:` section. `config.py` itself needs no
  changes (`${VAR}` resolution, path conversion, and dotted overrides all
  already handle the new section; level strings are not path-like).
- **`.gitignore`:** add `logs/`.
- **JS:** `logger.js` is a plain ESM module in `static/js/modules/`; no
  bundler changes; `build.py`'s static copy already ships the whole `js/`
  tree. Stack parsing for function names is confined to the `debug` method
  and wrapped in try/catch (or equivalent) — it must never throw on engines
  with different stack formats.
- **`data_ingestion.py` agent output:** the `opencode` subprocess runs with
  `capture_output=True`; its transcript is captured into the subprocess
  result and surfaces only inside `RuntimeError` messages — we neither
  re-log it nor print it. Only our own context lines are logged (at DEBUG).

## Test implications

### Python (`poetry run pytest`)

- **New `tests/test_logutil.py`:**
  - level parsing (case-insensitivity, `WARNING` alias, invalid value → error)
  - stream split: `capsys` — INFO/INFO_USER in `.out`, WARN/ERROR in `.err`
  - `INFO_USER`: plain text (no metadata prefix), stdout only, hidden when
    console threshold is WARN/ERROR, **absent from the written log file**
  - file writer: correct per-run filename pattern, `file_level` honored,
    DEBUG detail present in file, INFO_USER absent
  - config precedence: CLI `--log-level` > env `LOG_LEVEL` > user config >
    committed default (via `load_resourcery_config` overrides)
  - `logs_dir` creation on demand
- **Migrate existing `capsys`/`capfd` assertions** (roughly 60 across
  `test_site.py` (27), `test_data_ingestion.py` (12), `test_js_vendor.py`
  (8), `test_image_acquirer.py` (6), `test_font_acquirer.py` (4),
  `test_build.py` (2)):
  - `INFO_USER` UX copy: keep asserting via `capsys` stdout (the console
    handler writes it there) — these assertions survive nearly unchanged.
  - `WARN`/`ERROR` records: assert via `caplog` (record level + message) and
    switch the stream assertion to stderr where one is made. Note the
    intentional flips: build.py error assertions move `.out` → `.err`;
    data_ingestion UX assertions move `.err` → `.out`.
  - Tests that call library functions directly must either call
    `setup_logging()` with a test config or rely on `caplog` (records are
    captured regardless of handler configuration).
- **Config tests** (`test_config.py`): new `logging:` section resolves
  through the chain; `logs_dir` becomes a `Path`; level strings stay strings;
  `LOG_LEVEL`/`LOGS_DIR` env overrides work.
- **CLI tests** (`test_site.py` + per-module main tests): `--log-level`
  accepted on every parser and mapped to `logging.level`.
- **New-record coverage — one test per touched module** (`site`, `build`,
  `validate`, `data_ingestion`, `image_acquirer`, `font_acquirer`,
  `js_vendor`): assert at least one new `INFO`/`DEBUG` record exists via
  `caplog`. Pattern: `caplog.set_level(logging.DEBUG)`, run the phase
  against existing fixtures, assert a record whose message matches a regex
  pinning fixture-derived data — e.g. `re.search(r"^Rendered \d+ templates",
  msg)` for `build`, `re.search(r"^Loaded \d+ schemas", msg)` for
  `validate`, `re.search(r"^Dispatch: build", msg)` for `site`. Follow the
  existing `any(r.levelno == ... and ... in r.message for r in
  caplog.records)` pattern already used in `test_data_ingestion.py`
  (lines 177-199).
- **Non-empty log file guarantee (integration).** In `test_logutil.py` (or
  one per-module test), run a minimal successful phase/command with a
  tmp_path `logs_dir` at `--log-level DEBUG` and assert: the per-run file
  exists and is non-empty; it contains at least one `INFO` and one `DEBUG`
  record; it contains **no** `INFO_USER` text (e.g. `"✅"` absent). Tests
  never write to the real `logs/` directory.
- **Existing assertions — verified safe, no changes required.** Audit
  result: every `capsys.readouterr()` assertion in the suite is
  substring-style (`in`); the single exact-match
  (`tests/test_data_ingestion.py:211`, `capsys.readouterr().err == ""`)
  targets stderr and stays green because all new records are INFO→stdout;
  the single absence assertion (`tests/test_site.py:330`,
  `"Aborting pipeline" not in ...out`) is string-specific. The new INFO
  records therefore add stdout lines to existing capsys tests at default
  config without breaking them. **Guard:** the operational layer must not
  add `WARN`/`ERROR` records to existing paths — in particular the
  `build_stage_config({}, multi_step=False)` path that the `.err == ""`
  assertion pins.

### JS (`npm test`)

- **`tests/js/unit/tag-manager.test.js:200`:** replace the
  `vi.spyOn(console, 'warn')` assertion with a spy on the module's logger
  (e.g. spy on `logger.warn` via a module-level export, or assert through a
  mocked `createLogger`).
- **New `tests/js/unit/logger.test.js`:**
  - `createLogger(import.meta.url)` derives the module name from the URL
  - level filtering (debug/info/warn/error map to the right console methods)
  - DEBUG includes caller function name (stack parse); INFO+ does not parse
    the stack
  - stack parsing never throws on malformed/empty stacks
- No direct `console.warn`/`console.log` calls remain in `static/js/`
  (excluding `vendor/`).

### Suites

Both suites must pass unchanged in scope: `poetry run pytest` and
`npm test` (`npm run test:unit` + `npm run test:integration`).
