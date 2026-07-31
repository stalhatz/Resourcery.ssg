---
size: medium
modified_date: 2026-07-31
implemented_git_tag: specs/refactors/entry_point_deduplication.md/implemented
---

# Centralize the Entry-Point Layer

## Introduction

Six standalone CLI modules and the `site` coordinator each hand-roll the same
"CLI flags → config overrides" mapper, the acquire-images flow is copy-pasted
three times, the ingest stage-config parsing exists in two production copies
plus a third re-implementation inside a test, and nine call sites load JSON
with three different error semantics. This duplication is drift-prone: every
future CLI flag or config key must be added in parallel at up to seven places,
and error behaviour for broken JSON files depends on which module happens to
read them.

The goal is to collapse these four duplication families into **shared helpers
with a single, unified behaviour**, without changing the user-facing CLI
surface, the config format, or the module structure (each module keeps its own
`main()` / argparse entry point).

## Current state

### Family 1 — CLI → config override mappers (7 copies, ≈ 88 lines)

Every module builds a flat dotted-key dict for
`load_resourcery_config(overrides=...)` by looping over a flag→key mapping and
skipping `None` values:

| Site | Location | Section prefix | Style |
|------|----------|----------------|-------|
| `build.py` | `main()` at 364-379 | `build.` | inline `flag_to_key` dict |
| `validate.py` | `main()` at 704-712 | `validate.` | inline `flag_to_key` dict |
| `font_acquirer.py` | `main()` at 423-433 | `acquire-fonts.` | inline `flag_to_key` dict |
| `image_acquirer.py` | `main()` at 410-417 | `acquire-images.` | list of (flag, full dotted key) |
| `js_vendor.py` | `main()` at 226-234 | `acquire-js.` | inline `flag_to_key` dict |
| `data_ingestion.py` | `main()` at 953-967 | `ingest.` | inline `flag_to_key` dict |
| `site.py` | `_extract_overrides()` at 151-170 | per-command | reverse-lookup via `ARG_TO_CONFIG_KEY` + `COMMAND_FLAGS` |

Six of the seven copies build `f"{section}.{key}"` dotted keys from a
flag→config-key dict; `site.py` inverts its global `ARG_TO_CONFIG_KEY`
(arg-name → config-key) table and looks up each known config key per command.
`image_acquirer.py` hardcodes the full dotted key in its mapping. All seven
implement the same contract: *include a key only when the parsed argparse value
is not `None`*.

### Family 2 — acquire-images flow (3 copies, ≈ 86 lines)

`image_acquirer.py:424-452`, `site.py:220-243` (the `acquire-images`
subcommand), and `site.py:502-523` (step 4 of the `all` pipeline) repeat the
same flow: read `acquire-images.links` / `acquire-images.images_dir` and
`build.static_dir` from the resolved config → check the links file exists →
`json.load` it → construct `ImageAcquirer(...)` → `acquire_all(..., force=...)`
→ rename the links file to `.json.bak` → `json.dump` the updated data back.

Known divergences between the three copies:

- **Missing links file:** `image_acquirer.main()` prints `❌ Links file not
  found: …` and returns `1`; the `site.py` subcommand prints the same message
  and `sys.exit(1)`; the `all` pipeline prints `⚠️ … — skipping image
  acquisition` and continues.
- **Invalid JSON in links file:** all three crash with a raw
  `json.JSONDecodeError` traceback (none catches it).
- **Success message:** `image_acquirer.py:451-452` prints an extra
  `Backup saved to: …` line that the `site.py` copies lack.

### Family 3 — ingest stage-config parsing (2 production copies + 1 test copy, ≈ 87 lines)

`data_ingestion.py:1018-1059` (in `main()`) and `site.py:309-337` (in
`_run_ingest()`) contain near-identical parsing of the `ingest.stages:` config
subsection: validate stage keys against
`["site.config", "links", "design"]` (unknown key → stderr + `sys.exit(1)`),
build `requested_stages` in pipeline order, then build `stage_config` keeping
only stages with non-`None` overrides. `tests/test_data_ingestion.py:96-111`
re-implements the stage_config-building half as a local `_build_stage_config`
helper "to test it in isolation", mirroring the production logic.

**Divergence found:** `site.py:316` gates the whole block on
`stages_cfg and multi_step`, so when `stages:` is present but `multi_step` is
false it **silently ignores** the config — no warning, and unknown keys are not
validated. `data_ingestion.py:1025` gates on `stages_cfg` alone: it always
validates keys and, when `multi_step` is false, prints the warning
`⚠️ Warning: 'stages:' is configured but 'multi_step' is false …` and resets
both outputs to `None`. The implemented feature spec
[`per_stage_configuration.md`](../feats/per_stage_configuration.md)
(backwards-compatibility table) **mandates the warning**: *"`stages:` present,
`multi_step: false` … A warning is printed if both are set."* `site.py`'s
silent variant is the deviation.

### Family 4 — JSON loading (9 call sites, ≈ 59 lines, 3 error semantics)

| Site | Location | Mechanism | Error semantics today |
|------|----------|-----------|----------------------|
| `build.py` | `load_json()` at 23-35 | file `json.load` | raises `FileNotFoundError` / `json.JSONDecodeError` |
| `validate.py` | `DataValidator.load_json()` at 290-309 | file `json.load` | **collects** — appends to `self.errors`, returns `{}` |
| `site.py` | 227-228, 506-507 | raw `json.load` | uncaught traceback |
| `image_acquirer.py` | 433-434 | raw `json.load` | uncaught traceback |
| `font_acquirer.py` | 113-119 | raw `json.load` ×2 | uncaught traceback |
| `font_acquirer.py` | 69-72 | `json.loads` (string) | degrades — returns `[]` on `JSONDecodeError` |
| `js_vendor.py` | 145-152 | `json.loads` (string) | prints + `sys.exit(1)` |
| `data_ingestion.py` | 743 | `json.loads` (string) | caught → retry loop (invalid LLM output) |

`build.py`'s `load_json` is also imported by `tests/test_build.py` (which
asserts its exact exception types), and `validate.py`'s method is exercised by
`tests/test_validate.py` (collect-errors assertions) and by the
`test_data_ingestion.py` e2e tests (data injection via
`validator.load_json(...)`).

## Target state

### Principles

1. **Unify behaviours.** Where the duplicated copies diverge, resolve to a
   single behaviour. No backwards compatibility required. DRY is the main
   concern.
2. **One helper per family.** Exactly one implementation of each duplicated
   logic path; the other copies become call sites.
3. **Keep the module structure.** Each module keeps its own `main()` /
   argparse entry point and the `site.py` coordinator stays a thin dispatcher
   (per `CONTRIBUTING.md` architecture). Only the duplicated *helper logic* is
   consolidated.
4. **CLI surface, config format, and exit-code contracts are unchanged.**
   Flags, config keys, and each command's abort/continue policy stay as they
   are today, except where a divergence is explicitly resolved below.

### New module: `src/resourcery_ssg/io_utils.py`

A small, single-purpose module for JSON reading with **one** error semantics:
**raise with file-path context**. It contains:

- `class JsonLoadError(ValueError)` — raised by both helpers. Carries a
  `path` attribute (a `Path` or `None`) and the underlying `cause`. The
  message names the offending file (or source context) and the underlying
  cause, e.g. `Failed to parse JSON in /path/to/links.json: Expecting value …`.
- `load_json(path)` → parses a JSON file. Raises `JsonLoadError` with path
  context on unreadable/missing file and on parse failure.
- `loads_json(text, *, path=None, source=None)` → parses a JSON string. The
  optional `path`/`source` context is embedded in the raised `JsonLoadError`
  message. Used by the call sites that currently parse strings.

All nine call sites migrate:

| Call site | Migration |
|-----------|-----------|
| `build.py:23-35` `load_json` | **Deleted.** Internal uses at 161-163 call `io_utils.load_json`. |
| `validate.py:290-309` method | **Deleted.** The six call sites in `load_schemas()` (321-323) and `load_data()` (340-342) wrap `io_utils.load_json` in `try/except JsonLoadError`, append the exception message to `self.errors`, and use `{}` on failure — preserving the collect-errors behaviour at the call-site level. |
| `site.py:227-228, 506-507` | Migrate inside `acquire_images_from_config` (Family 2) — no direct call remains. |
| `image_acquirer.py:433-434` | Migrate inside `acquire_images_from_config` (Family 2). |
| `font_acquirer.py:113-119` | Call `io_utils.load_json` for both files. |
| `font_acquirer.py:69-72` | Call `io_utils.loads_json`; the degrade-to-`[]` behaviour is kept by catching `JsonLoadError` at this call site. |
| `js_vendor.py:145-152` | Call `io_utils.loads_json` with `path=package_json_path`; keep the print + `sys.exit(1)` handling by catching `JsonLoadError`. |
| `data_ingestion.py:743` | Call `io_utils.loads_json` with `path=output_path`; change the `except json.JSONDecodeError` in the retry loop to `except JsonLoadError` (the retry condition — "step produced invalid JSON" — is unchanged). |

Rationale for a dedicated module: `config.py` is the config-resolution layer
and should not become a dumping ground for generic I/O; `io_utils.py` gives
JSON reading one home and one exception type, and both `config.py` (YAML) and
the JSON call sites remain cleanly separated.

### Shared CLI override mapper: `config.py::build_cli_overrides`

Add to `config.py` (the module that already owns the overrides contract —
`load_resourcery_config(overrides=...)` and `_expand_dotted_overrides`, which
also skips `None` values):

- `build_cli_overrides(args, section, flag_to_key)` → `dict` — builds the flat
  dotted-key overrides dict `{f"{section}.{key}": value}` from a parsed
  argparse namespace, including a key **only when its value is not `None`**
  (preserving the `store_true, default=None` semantics of e.g.
  `--multi-step`). `flag_to_key` maps argparse attribute name → config key
  name.

All seven override sites migrate to it:

| Site | Migration |
|------|-----------|
| `build.py:364-379` | `build_cli_overrides(args, "build", {...})` |
| `validate.py:704-712` | `build_cli_overrides(args, "validate", {...})` |
| `font_acquirer.py:423-433` | `build_cli_overrides(args, "acquire-fonts", {...})` |
| `image_acquirer.py:410-417` | `build_cli_overrides(args, "acquire-images", {"links": "links", "images_dir": "images_dir"})` — the full-dotted-key style disappears |
| `js_vendor.py:226-234` | `build_cli_overrides(args, "acquire-js", {...})` |
| `data_ingestion.py:953-967` | `build_cli_overrides(args, "ingest", {...})` |
| `site.py:151-170` `_extract_overrides` | **Deleted.** `main()` calls the helper with the per-command filtered mapping `{arg: key for arg, key in ARG_TO_CONFIG_KEY.items() if key in known_config_keys}`; `_run_all` does the same per command and `update()`s the combined dict. `ARG_TO_CONFIG_KEY` and `COMMAND_FLAGS` tables stay as the single source of flag-name ↔ config-key naming. |

Rationale for the `config.py` home: it already defines the overrides contract
(dotted keys, `None`-skipping) consumed by `load_resourcery_config`; every
migrating module already imports from it; and the helper needs no new
dependencies (`args` is used duck-typed via `getattr`).

### Shared acquire-images flow: `image_acquirer.py::acquire_images_from_config`

Add to `image_acquirer.py`:

- `acquire_images_from_config(config, *, force=False)` → `bool` — runs the
  full acquire-images flow from a resolved config dict: reads
  `acquire-images.links`, `acquire-images.images_dir` and `build.static_dir`;
  if the links file is missing **or fails to parse** (`JsonLoadError` from
  `io_utils.load_json`), prints a single unified `⚠️` message naming the file
  and returns `False`; otherwise loads the links, constructs the
  `ImageAcquirer`, runs `acquire_all(..., force=force)`, renames the file to
  `.json.bak`, writes the updated data back, prints the `✅ Updated …` **and**
  `Backup saved to: …` lines, and returns `True`.

The three call sites become:

| Call site | Behaviour after migration |
|-----------|--------------------------|
| `image_acquirer.py` `main()` | `return 0 if acquire_images_from_config(config, force=args.force) else 1` — exit-code contract unchanged |
| `site.py` `acquire-images` subcommand (216-243) | `sys.exit(0 if acquire_images_from_config(config, force=args.force) else 1)` — exit-code contract unchanged |
| `site.py` `all` step 4 (494-523) | `acquire_images_from_config(config, force=getattr(args, "force", False))`, result ignored — pipeline continues (missing-file semantics preserved) |

Resolved divergences: the duplicated `❌`-and-exit blocks are gone (the
function owns the failure message); the `all` step keeps its warn-and-continue
policy via the boolean return; and the success message is unified on the more
informative two-line form. **Documented behaviour change:** the `all` pipeline
previously aborted with a raw traceback on an unparseable `links.json`; it now
warns and continues with the data on disk, consistent with the missing-file
case (unification is acceptable — no backwards compatibility required).

### Shared stage-config parser: `data_ingestion.py::build_stage_config`

Add to `data_ingestion.py` (the module that owns the ingest feature and that
`site.py` already imports from for `run_ingestion` /
`run_multi_step_ingestion`):

- `build_stage_config(stages_cfg, *, stage_keys=None, multi_step=True)` →
  `(stage_config, requested_stages)` tuple, both `None` when the config is
  absent or ignored. With `stage_keys` defaulting to
  `["site.config", "links", "design"]`:
  1. If `stages_cfg` is falsy → return `(None, None)`.
  2. Always validate stage keys first — unknown key → stderr message +
     `sys.exit(1)` (data_ingestion.py's canonical order: validation happens
     even when `multi_step` is false).
  3. If `multi_step` is true → build `requested_stages` in pipeline order,
     then `stage_config` keeping only stages with non-`None` overrides (the
     `isinstance(overrides, dict) or hasattr(overrides, "items")` guard is
     kept so frozen `MappingProxyType` values — including the `None`/empty-YAML
     cases — behave exactly as today).
  4. If `multi_step` is false → print the `⚠️ Warning: 'stages:' is
     configured but 'multi_step' is false …` message and return `(None, None)`.

The two production copies are replaced by single calls:
`data_ingestion.py:1018-1059` → `stage_config, requested_stages =
build_stage_config(stages_cfg, multi_step=multi_step)`;
`site.py:309-337` → same call. **Resolved divergence:** `site.py`'s silent
ignore-when-`multi_step`-false behaviour is replaced by the canonical
warning + always-on key validation, restoring the behaviour mandated by the
implemented `per_stage_configuration.md` feature spec.

The test copy `tests/test_data_ingestion.py:96-111` (`STAGE_KEYS` +
`_build_stage_config`) is deleted; the `TestBuildStageConfig` class is
rewritten to call the production helper (see Tests).

Rationale for the `data_ingestion.py` home: the parsing is ingest-feature
logic, the canonical copy already lives there, `site.py` already depends on
the module, and putting ingest semantics into the generic `config.py` would
pollute it.

### What stays unchanged

- Each module's own `main()` / argparse setup and its `--config` flag.
- `site.py` as the thin coordinator; `COMMAND_FLAGS` and `ARG_TO_CONFIG_KEY`.
- The `config.yaml` format and every config key.
- The public CLI command names and exit-code contracts (including
  `acquire-images` returning `1` / `site` exiting `1` on a missing links file,
  and the `all` pipeline warn-and-continue policy for a missing file).
- `data_ingestion.py`'s `run_multi_step_ingestion` / `run_ingestion` public
  signatures (they consume `stage_config` / `requested_stages` unchanged).
- `validate.py`'s collect-errors behaviour — preserved at the call-site level
  around the unified raising helper.

### Target metrics

- Override mappers: 7 copies (≈ 88 lines) → 1 helper + 7 one-line call sites.
- Acquire-images flow: 3 copies (≈ 86 lines) → 1 function + 3 call sites.
- Stage-config parsing: 2 production + 1 test copy (≈ 87 lines) → 1 function +
  2 call sites + a rewritten test class.
- JSON loading: 9 call sites with 3 error semantics (≈ 59 lines) → 2 helpers +
  1 exception type with a single raise-with-context semantics.
- Gross duplication eliminated: **≈ 320 lines**; net line reduction after
  adding the shared helpers (≈ 120 lines) and call-site glue: **≈ 145-160
  lines**. (The pitch's "~200 lines" estimate is optimistic; the real figure
  is ≈ 320 gross / ≈ 150 net.)

## Resolved questions

1. **Should `JsonLoadError` subclass `json.JSONDecodeError` for drop-in
   compatibility with existing `except` clauses?** — **Resolved: No**
   (user-confirmed, 2026-07-31). Only two call sites catch it today
   (`data_ingestion.py:743`, `font_acquirer.py:70`) and both migrate to
   `except JsonLoadError`; keeping a single custom exception type with a
   `path`/`cause` attribute is simpler and the message carries more context.
2. **Should `io_utils` also provide the JSON *write* helper (the
   backup/`json.dump` dance is currently duplicated between
   `image_acquirer.py` and the two `site.py` copies)?** — **Resolved: No,
   out of scope** (user-confirmed, 2026-07-31). Family 2 unification already
   collapses the write logic into `acquire_images_from_config`; a general
   atomic-write helper can be a follow-up spec if a second need appears.

## Related specs

### Depends upon
- None.

### Extends
- [refactors/path_configurability.md](path_configurability.md) (implemented,
  tag `specs/refactors/path_configurability.md/implemented`, commit `5f76439`)
  — that spec centralised config loading (`load_resourcery_config`) and
  created the `site` coordinator, but left the per-module override mappers in
  place; this spec finishes the job with `build_cli_overrides`. Implemented
  specs are immutable, so this is a new spec rather than an amendment.
- [feats/per_stage_configuration.md](../feats/per_stage_configuration.md)
  (implemented, tag `specs/feats/per_stage_configuration.md/implemented`,
  commit `78e9da6`) — that spec introduced the stage-config parsing that this
  spec extracts; the unified `build_stage_config` must preserve the feature's
  defined behaviour exactly, including the `multi_step: false` warning that
  `site.py`'s copy currently omits.

### Enables
- Future CLI/config changes become single-point edits instead of up-to-seven
  parallel edits (e.g. new per-command flags, new JSON-backed inputs).

### Supersedes
- None.

## Technical details

- **Frozen configs:** `load_resourcery_config` returns `MappingProxyType`-
  wrapped dicts; `acquire_images_from_config` and `build_stage_config` must
  only read from it, and `build_stage_config` must keep the
  `isinstance(…, dict) or hasattr(…, "items")` guard (the `MappingProxyType`
  override case is a previously-fixed bug in the test suite and must keep
  passing).
- **`None`-skipping double layer:** `build_cli_overrides` skips `None`
  values at build time; `_expand_dotted_overrides` also skips them at merge
  time. Keeping both is harmless and preserves the "only explicitly passed
  flags override config" contract for `store_true, default=None` flags
  (`--multi-step`, `--force`).
- **`site.py` `_run_all`:** the six per-command `_extract_overrides` calls at
  414-429 become six `build_cli_overrides` calls with filtered
  `ARG_TO_CONFIG_KEY` mappings, merged with `update()` exactly as today.
- **`validate.py` wrappers:** `load_schemas()` and `load_data()` rely on the
  `{}`-on-failure contract (falsy check → return `False`); the
  try/except wrappers must preserve it.
- **`data_ingestion.py` retry loop:** the `except` clause at 744 changes type
  but not behaviour — invalid step output still feeds the retry/feedback
  machinery; the `JsonLoadError` message (with `path=output_path`) improves
  the error text in the retry feedback and the final `RuntimeError`.
- **Tests to update:** `tests/test_build.py` (imports `load_json` from
  `build` and asserts `FileNotFoundError` / `json.JSONDecodeError` — must
  import from `io_utils` and assert `JsonLoadError`),
  `tests/test_validate.py` (collect-errors assertions on the deleted method
  must target the new wrappers), `tests/test_data_ingestion.py`
  (`TestBuildStageConfig` rewritten against `build_stage_config`;
  `validator.load_json` e2e injection at 234-236 / 315-317 replaced by the
  wrapper or `io_utils.load_json`), `tests/test_image_acquirer.py` /
  `tests/test_site.py` (any tests exercising the copied flows).
- **Tests to add:** unit tests for `io_utils.load_json` /
  `io_utils.loads_json` (happy path, missing file, invalid JSON, string
  variant with and without context); unit tests for `build_cli_overrides`
  (None-skipping, dotted-key shape, unknown-arg tolerance); unit tests for
  `acquire_images_from_config` (success writes `.bak` + updated file, missing
  file → `False`); unit tests for `build_stage_config` (all existing
  `TestBuildStageConfig` cases plus unknown-key error and
  `multi_step: false` warning).
- **No packaging changes:** `io_utils.py` is an internal module — no new
  `pyproject.toml` scripts or dependencies.
- **Docstrings:** follow the project's standardised docstring style (module +
  function docstrings with Args/Returns/Raises) per `specs/docs/docstring.md`.
