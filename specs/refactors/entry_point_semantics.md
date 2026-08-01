---
size: small
modified_date: 2026-08-01
implemented_git_tag: specs/refactors/entry_point_semantics.md/implemented
---

# Unify Divergent Entry-Point Semantics

## Introduction

Resourcery.ssg has five CLI entry points that reach the two library
functions `build_site()` (build.py) and `acquire_js()` (js_vendor.py):
`site build`, `site all`, `site acquire-js`, the standalone `build`, and the
standalone `acquire-js`. Three of them implement **different semantics** for
two behaviors that `site build` / `site all` already implement correctly:

1. `site all` calls `acquire_js()` with **no config arguments**, while
   `site acquire-js` and standalone `acquire-js` pass
   `acquire_js(**config["acquire-js"])`.
2. Standalone `build` forwards the **whole** `build:` config section —
   including `static_source` — into `build_site()`, whose signature has no
   such parameter → a latent `TypeError`.
3. Standalone `build` never seeds the static staging directory, while both
   `site build` and `site all` seed it before dispatching.

The first divergence is a silent wrong-behavior bug (overridden config keys
are ignored); the second is a latent crash; the third is a correctness gap
masked by the second. All three survived the entry-point deduplication
refactor (implemented `entry_point_deduplication.md`), the raise/exit
refactor (implemented `library_raise_main_exit.md`), and the logging refactor
(implemented `logging_infrastructure.md`) — they are residual drift, not
regressions introduced by those refactors (see Current state for origin
commits).

The goal is to unify every entry point on the `site build` / `site all`
semantics: config-scoped kwargs for `acquire_js`, `static_source` filtered
out of `build_site` kwargs, and static staging seeded before dispatch.
`build_site()` stays a pure path-taking library function — no
`static_source` handling moves into it (user-confirmed).

## Current state

### Divergence 1 — `site all` ignores `config["acquire-js"]`

| Call site | Location | Call |
|-----------|----------|------|
| `site all` step 3 (`_run_all`) | `site.py:517` | `acquire_js()` — **bare** |
| `site acquire-js` subcommand | `site.py:262` | `acquire_js(**config["acquire-js"])` |
| standalone `acquire-js` (`main`) | `js_vendor.py:253` | `acquire_js(**config["acquire-js"])` |

`acquire_js()` falls back to defaults when no kwargs are given
(js_vendor.py:138-143): repo-root `package.json` and `./static/js/vendor`.
These coincide with the committed `config.yaml` values (config.yaml:29-31),
so default configurations neither crash nor diverge. The bug is silent and
conditional:

- Any user config that overrides `acquire-js.vendor_dir` or
  `acquire-js.package_json_path` is **ignored** in `site all` — the vendored
  file is read from / written to the default location instead of the
  configured one.
- `site all --package-json … --vendor-dir …` (site.py:130-131) are
  **silently dead flags**: `_run_all` resolves them into
  `config["acquire-js"]` via `build_cli_overrides` (site.py:444) and then
  never reads them.

Origin: the bare call dates from `0022b68` (modular ESM refactor,
2026-07-31). The three subsequent refactor commits
(`1d72577`, `e22d91e`, `596f1ca`) all passed over it without touching it.

### Divergence 2 — standalone `build` forwards `static_source` to `build_site`

| Site | Location | Behavior |
|------|----------|----------|
| `build.py` `main()` | `build.py:417` | `build_kwargs = dict(config["build"])` — **no filtering** |
| `build.py` `main()` | `build.py:422` | `build_site(**build_kwargs)` → `TypeError` when `static_source` present |
| `site build` subcommand | `site.py:239` | filters: `{k: v for k, v in config["build"].items() if k != "static_source"}` |
| `site all` step 5 | `site.py:537` | same filter |

`build_site()`'s signature (build.py:126-127) is
`(*, data_dir, templates_dir, static_dir, output_dir, attribution=None,
ingest_note=None, ingest_site_prompt=None)` — there is no
`static_source` parameter, so the standalone entry point raises
`TypeError: build_site() got an unexpected keyword argument 'static_source'`
whenever `build.static_source` is configured.

The committed `config.yaml` does **not** set `static_source` (config.yaml:13-18),
which is why the default `poetry run build` works and the bug stays latent.
Every real-world config in the repository sets it:

| Config | `static_source` |
|--------|-----------------|
| `userdata/tech/config.yaml` | line 13: `${STATIC_SOURCE}` (= `./static`) |
| `userdata/tech_1/config.yaml` | line 13: `${STATIC_SOURCE}` |
| `tests/fixtures/e2e-config.yaml` | line 28: `${STATIC_SOURCE}` |
| committed `config.yaml` | absent (defaults coincide) |

So `poetry run build --config userdata/tech/config.yaml` **crashes today**.

Origin: `build.py` `main()` was rewritten by `f958fb6` (attribution feature,
2026-07-28), which introduced `build_kwargs = dict(config["build"])` without
the filter that `site.py` already had. No later commit touched it.

### Divergence 3 — standalone `build` never seeds static staging

| Site | Location | Seeds staging? |
|------|----------|----------------|
| `site build` subcommand | `site.py:238` | yes — `_seed_static_staging(config)` before `build_site` |
| `site all` | `site.py:463` | yes — before step 1 (validate) |
| standalone `build` (`main`) | `build.py` | **no** |

`_seed_static_staging(config)` (site.py:371-413) copies
`build.static_source` → `build.static_dir`. It is a no-op when
`static_source` is unset, warns and skips when the source is missing
(site.py:387-389), and overwrites destination files (rebuild-means-rebuild,
site.py:377-379).

Consequence: with `build.static_source` configured, standalone `build`
builds against an **unseeded** `static_dir` — missing `fonts.css`
(`ResourceryError: static/css/fonts.css not found — run font_acquirer.py
first`, build.py:176-179) or stale/missing assets. Today this is masked by
Divergence 2: the `TypeError` fires first. Once 2 is fixed, the staging gap
becomes the standalone build's failure mode.

Origin: staging was introduced by `5f76439` (path configurability) as a
coordinator/pipeline concept; standalone `build` never gained it.

### Impact matrix

| Entry point | `acquire-js` kwargs | `static_source` filter | staging seed | Status today |
|-------------|---------------------|------------------------|--------------|--------------|
| `site build` | — | ✅ site.py:239 | ✅ site.py:238 | correct (reference semantics) |
| `site all` | ❌ site.py:517 | ✅ site.py:537 | ✅ site.py:463 | silently wrong vendor dir / package.json under overridden `acquire-js` config (incl. `--package-json` / `--vendor-dir` flags) |
| `build` (standalone) | — | ❌ build.py:417 | ❌ | **crash** (`TypeError`) whenever `build.static_source` is set; then unseeded-staging build failure once 2 is fixed |
| `site acquire-js` | ✅ site.py:262 | — | — | correct |
| `acquire-js` (standalone) | ✅ js_vendor.py:253 | — | — | correct |

## Target state

### Fix 1 — `site all` passes `config["acquire-js"]` and handles its failures like the fonts step

`_run_all` step 3 (site.py:515-518) becomes:

```python
from resourcery_ssg.js_vendor import acquire_js

try:
    with log_timing(logger, "Step 'acquire-js'"):
        acquire_js(**config["acquire-js"])
except ResourceryError:
    logger.error("\n❌ JS acquisition failed. Aborting pipeline.")
    sys.exit(1)
```

This mirrors the acquire-fonts step (site.py:502-507) exactly: same
`try / except ResourceryError` shape, same abort-message style, same
`sys.exit(1)`. `acquire_js` raises `ResourceryError` on all six failure
modes (js_vendor.py:149/160/168/189/195/206 — the raise mechanism
established by the implemented `library_raise_main_exit.md`), so the
catch is always reachable. The `--package-json` / `--vendor-dir` flags on
`site all` become effective as a side effect (they already resolve into
`config["acquire-js"]`).

**Documented behaviour change:** `site all` currently exits 1 on a JS
failure with only the underlying error message and **no abort line**
(frozen as row 17 of `library_raise_main_exit.md`'s preservation table:
"Error: … on stderr, exit 1, no abort line"). Mirroring the fonts step adds
the line `❌ JS acquisition failed. Aborting pipeline.` to stderr. This is a
deliberate unification with the fonts step and supersedes the frozen
"no abort line" surface (see Supersedes).

### Fix 2 — standalone `build` filters `static_source` out of `build_site` kwargs

`build.py` `main()` mirrors `site.py:537` verbatim:

```python
build_kwargs = {k: v for k, v in config["build"].items() if k != "static_source"}
build_kwargs["ingest_note"] = config.get("ingest", {}).get("note")
build_kwargs["ingest_site_prompt"] = config.get("ingest", {}).get("site_prompt")
```

replacing `build_kwargs = dict(config["build"])` (build.py:417). Everything
else in `main()` (override extraction, config load, the
`try / except ResourceryError: sys.exit(1)` dispatch) stays as-is.

### Fix 3 — standalone `build` seeds static staging before dispatch

`build.py` `main()` gains the staging call that `site build` (site.py:238)
and `site all` (site.py:463) already perform, placed inside the existing
`try`, immediately before `build_site(**build_kwargs)` — mirroring the
`site build` subcommand's ordering (seed, then dispatch). Seeding itself is
non-raising (warn-and-continue on missing source), so no new error handling
is needed.

**Module placement of the seeding helper (decided: move to `build.py`).**
`_seed_static_staging` currently lives in `site.py` (371-413). Moving it to
`build.py` as a public `seed_static_staging(config)` is decided because:

- It consumes **only** `build.*` config keys (`static_source`,
  `static_dir`) — `build.py` owns the `build:` section's semantics, exactly
  as `image_acquirer.py` owns `acquire_images_from_config` (the precedent
  from the implemented `entry_point_deduplication.md`).
- Dependency direction stays clean. Today: `site.py` imports `build.py`
  function-level (site.py:236, 535) and `build.py` never imports `site.py` —
  there is **no circular import risk** with the move; the reverse (build.py
  importing the coordinator from `site.py`) would invert the architecture
  (CONTRIBUTING.md: "site.py is a thin coordinator that dispatches to
  [the modules]").
- `config.py` is rejected as a home: it is the config-resolution layer and
  should not accumulate filesystem-copy logic (same rationale as
  `entry_point_deduplication.md` used to reject it for ingest stage-config
  parsing).
- A new single-purpose module is rejected: the helper is ~43 lines, has one
  feature owner (`build`), and the established
  `errors.py`/`io_utils.py`/`logutil.py` precedent is for **cross-cutting**
  concerns only.
- Keeping the helper in `site.py` and importing it from `build.py` is
  rejected: it would invert the leaf→coordinator dependency (build.py is a
  leaf module; site.py is the coordinator that dispatches to it,
  CONTRIBUTING.md).

After the move: `site.py` calls `from resourcery_ssg.build import
build_site, seed_static_staging` (function-level, alongside the existing
imports at site.py:236/535) at its two call sites (238, 463); `build.py`
`main()` calls it directly. The function's body, messages, and behavior are
unchanged (see Technical details for the logging-record note).

### What stays unchanged

- `build_site()`'s signature and library semantics — no `static_source`
  handling enters the library function (user-confirmed).
- Committed `config.yaml` — no `static_source` key is added; the latent
  default path stays the "manual workflow" (static_dir as source and target,
  per `path_configurability.md`).
- The already-correct entry points: `site build`, `site all`, `site
  acquire-js`, standalone `acquire-js`.
- Exit codes and message texts of every existing failure path except the
  documented `site all` JS abort line (Fix 1).
- `rebuild_and_serve.sh` — untracked, deliberately out of scope
  (user-confirmed).

## Decisions (resolved — implementation details, not spec-level questions)

The following were raised during drafting and resolved as stated; the planner
and builder should treat them as fixed unless a concrete blocker surfaces
during implementation:

1. **`site all` JS failure gains the abort line** — Fix 1 keeps the
   fonts-style wrap including `❌ JS acquisition failed. Aborting pipeline.`
   (net UX consistency; supersedes the frozen "no abort line" detail of
   `library_raise_main_exit.md` row 17).
2. **Seeding helper moves to `build.py`** as public `seed_static_staging`
   (see Fix 3 rationale; rejected alternatives listed there).
3. **Public name** — `seed_static_staging` (matching the shared-helper
   convention from `entry_point_deduplication.md`).

## Related specs

### Depends upon
- None. (The prerequisites are already implemented: `errors.py` /
  `ResourceryError` from `library_raise_main_exit.md`, `build_cli_overrides`
  from `entry_point_deduplication.md`, `logutil` from
  `logging_infrastructure.md`.)

### Enables
- Restored correctness of the standalone `build` entry point under
  `build.static_source` configs (all userdata configs and the e2e fixture),
  and of `site all` under overridden `acquire-js` configs.
- A future spec that consolidates the duplicated
  `{k: v for k, v in config["build"].items() if k != "static_source"}` +
  `seed_static_staging` call triple (site.py:238-241, site.py:537-539,
  build.py `main()`) into a single shared dispatch helper — out of scope
  here (this spec fixes behavior; a shared `run_build(config)` helper could
  follow the `acquire_images_from_config` precedent).

### Extends
- [refactors/entry_point_deduplication.md](entry_point_deduplication.md)
  (implemented, tag `specs/refactors/entry_point_deduplication.md/implemented`,
  commit `1d72577`) — that spec unified the duplicated *flows* (override
  mappers, acquire-images, stage-config, JSON loading) but left per-entry
  point divergences in the `acquire-js` call and the `build` dispatch in
  place; this spec finishes the unification job for those two call sites.
  Implemented specs are immutable, so this is a new spec rather than an
  amendment.
- [refactors/path_configurability.md](path_configurability.md) (implemented,
  tag `specs/refactors/path_configurability.md/implemented`, commit
  `5f76439`) — that spec introduced static staging as a coordinator
  (`all`) behavior; this spec extends the seeding to the standalone `build`
  entry point so the staging workflow is entry-point-independent.
- [refactors/library_raise_main_exit.md](library_raise_main_exit.md)
  (implemented, tag `specs/refactors/library_raise_main_exit.md/implemented`,
  commit `e22d91e`) — the `except ResourceryError` catch in Fix 1 uses the
  raise mechanism that spec established; Fix 1 also revises the *observable
  surface* that spec froze (row 17 of its preservation table) — see
  Supersedes.
- [refactors/logging_infrastructure.md](logging_infrastructure.md)
  (implemented, tag `specs/refactors/logging_infrastructure.md/implemented`,
  commit `596f1ca`) — the staging DEBUG record format (`Staging: seeded
  {source} → {dest} ({n} files)`, its line 359) is preserved verbatim by the
  helper move; only the emitting logger's module name changes from
  `resourcery_ssg.site` to `resourcery_ssg.build` (record format unchanged,
  so the implemented spec's table stays accurate).

### Supersedes
- Partial: Fix 1's fonts-style abort line supersedes the "no abort line"
  aspect of row 17 (``site all`` JS fails) in
  `library_raise_main_exit.md`'s exit-code preservation table — the only
  frozen CLI-surface detail this spec changes. No other implemented-spec
  surface is affected.

## Technical details

- **Import graph (circular-import check).** `build.py` module-level imports:
  `errors`, `io_utils`, `logutil`, `theme_constants`, `token_gen` — it never
  imports `site.py`. `site.py` imports `build.py` only inside functions
  (site.py:236, 535). Moving `_seed_static_staging` into `build.py` and
  importing it in `site.py` at function level therefore cannot create a
  module-load cycle. If the alternative (import from `site.py` into
  `build.py` `main()`) were chosen, it would also be cycle-free (both
  imports function-level) but architecturally inverted.
- **`config["acquire-js"]` values are `Path` objects.** `load_resourcery_config`
  converts path-like strings (config.yaml:29-31: `package_json_path`,
  `vendor_dir`) to `Path`. Tests asserting kwargs must compare against the
  resolved config's values, not raw strings.
- **Existing test mocks break without an update.** `tests/test_site.py:318`
  and `:471` monkeypatch `resourcery_ssg.js_vendor.acquire_js` with
  `lambda: None`; once Fix 1 passes kwargs, these raise `TypeError: <lambda>()
  got an unexpected keyword argument ...`. Both must become
  `lambda **kwargs: None`. The `TestRunAllFailureAborts` class docstring
  ("Only the font step has an abort line today; JS/build/ingest failures
  must propagate to the site.main() catch-all") must be revised: the JS step
  now carries an abort line too.
- **Tests to update** (all in `tests/test_site.py`):
  - lines 318, 471: `acquire_js` mock → `lambda **kwargs: None`.
  - `_write_all_config` (257-290) needs no change — the committed
    `config.yaml` deep-merge supplies `config["acquire-js"]`; a new
    `acquire-js:` section can be appended for kwargs-propagation tests.
- **Tests to add** (reuse `_write_all_config` / `_write_build_config` /
  `_spy_load_config` / `testdata_dir` patterns; all `@pytest.mark.unit`):
  - `test_run_all_acquire_js_receives_config_kwargs` — `_write_all_config`
    variant with an `acquire-js:` section pointing `package_json_path` /
    `vendor_dir` at tmp paths; spy on `resourcery_ssg.js_vendor.acquire_js`
    capturing kwargs (fonts and build mocked as today); run
    `site._run_all(args)`; assert the spy was called once with kwargs equal
    to the resolved `config["acquire-js"]`. **Fails today** (no kwargs
    passed).
  - `test_run_all_js_failure_aborts` — mirror of
    `test_run_all_font_failure_aborts` (293-307): mocked `acquire_js` raises
    `ResourceryError`; assert `SystemExit` code 1 and
    `JS acquisition failed. Aborting pipeline.` in stderr.
  - `test_build_main_filters_static_source` — `_write_build_config` variant
    that adds `static_source: <tmp source dir>`; spy on
    `resourcery_ssg.build.build_site` capturing kwargs; run
    `build_main()`; assert `static_source` not in the kwargs. **Fails today
    with `TypeError`** — the regression-catching test.
  - `test_build_main_seeds_staging_before_build` — config with
    `static_source` → tmp dir containing a file and `static_dir` → another
    tmp dir; spy on `resourcery_ssg.build.seed_static_staging` and
    `build_site` (shared call recorder, or the `build_site` spy asserting
    the seeded file already exists in `static_dir`); assert seed-then-build
    ordering. **Fails today** (no seeding call).
  - `test_build_main_missing_static_source_warns_and_builds` — `static_source`
    → nonexistent dir; caplog/capsys assert the
    `static_source not found: … — skipping` warning (site.py:387-389 path);
    `build_site` still invoked with filtered kwargs.
  - Recommended: unit tests for the newly public `seed_static_staging`
    (zero direct coverage exists today): no-op when `static_source` unset;
    copies files and skips `.gitkeep`; source-wins overwrite of existing
    staging files; missing source → warning, no raise.
- **Logging-record provenance.** The staging DEBUG record
  (`Staging: seeded {source} → {dest} ({n} files)`) and the user-facing
  `📦 Seeding static staging: {source} → {dest}` line keep their exact
  formats; after the move they are emitted under the
  `resourcery_ssg.build` logger. No format or level changes —
  `logging_infrastructure.md`'s record table remains accurate.
- **No packaging changes.** No new modules, no `pyproject.toml` edits.
