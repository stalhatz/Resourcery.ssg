---
size: medium
modified_date: 2026-07-26
implemented_git_tag: specs/refactors/path_configurability.md/implemented
---

# Configurable Input/Output Paths for All Commands

## Introduction

Every Resourcery.ssg command currently assumes a fixed project directory structure. Paths are derived from `Path(__file__).resolve().parent.parent.parent` (the project root) plus hardcoded subdirectory names (`data/`, `templates/`, `static/`, `output/`, `schemas/`). This makes it impossible to:

- Host multiple websites from a single checkout by pointing commands at different site directories
- Use the tool from outside the project root (e.g. via `pipx` or as a library)
- Run the tool in CI where the working directory differs from the repo root
- Test commands without monkeypatching module-level constants

The goal is to make every path a script touches independently configurable, with a committed config file as the single source of truth — no hardcoded path strings in Python code.

## Current state

| Command | Input paths | Output paths | Overridable? |
|---------|-------------|--------------|--------------|
| `validate` | `data/` (data files), `schemas/` (schema files) — both relative to project root | Console only | `DataValidator(root_dir=...)` constructor arg only |
| `build` | `data/`, `templates/`, `static/` — all relative to project root | `output/` (relative to project root) | No (module-level constants monkeypatched in tests) |
| `acquire-fonts` | `data/site.config.json` | `static/fonts/`, `static/css/fonts.css` | No (module-level constants monkeypatched in tests) |
| `acquire-images` | `--links` path (default `data/links.json`) | `static/images/acquired/` | Partial (`--links` arg, `root_dir` constructor arg) |
| `ingest` | All via required CLI args | `--output` CLI arg | Fully overridable |

Module-level path constants in `build.py` and `font_acquirer.py` are computed at import time from `Path(__file__)`, meaning they are frozen when the module is first loaded and cannot be overridden at invocation time without monkeypatching.

## Target state

### Principles

1. **Zero hardcoded paths in Python code.** No `Path(__file__)`, no `ROOT_DIR`, no `DATA_DIR = ROOT_DIR / "data"`. All path values come from the config layer.
2. **Every output dir has its own CLI flag.** If a script writes to two directories, it has two flags. No subpath derivation from a single `--output`.
3. **A committed `config.yaml` is the single source of truth for defaults.** It lives in the repository root and replaces all hardcoded defaults.
4. **Semantic grouping variables** (`STATIC_DIR`, `DATA_DIR`, `TEMPLATES_DIR`, etc.) are defined in the config's `vars:` section and can be overridden via `.env` / environment variables. Scripts never reference them directly. The config layer resolves `${VAR}` references before scripts see the values.
5. **Backward compatibility.** `poetry run build` with no arguments must produce the same result as today.

### Path resolution order

```
CLI argument (highest)
  ↓
Environment variable / .env
  ↓
User --config file (if specified)
  ↓
Committed config.yaml (lowest — default)
```

Each step overrides matching keys from the step below. If a path is referenced nowhere in this chain, the tool errors — no implicit fallback derivation.

### Config file format

A YAML file with two sections:

- **`vars:`** — defines named variables (like `STATIC_DIR`, `DATA_DIR`) that can be referenced elsewhere in the config via `${VAR}` syntax. These are defaults — environment variables with the same name override them.
- **Per-command sections** (`build:`, `validate:`, etc.) — the specific paths each command needs. Values can reference `vars:` entries or environment variables with `${VAR}` syntax.

A `${VAR}` reference resolves in this order:
1. Environment variable (including `.env` file)
2. Variable defined in `vars:` section (user config, if any)
3. Variable defined in `vars:` section (committed config)
4. Literal string unmodified (if none of the above match)

No special `:-default` syntax is needed — the `vars:` section serves as the default layer.

**Concrete resolution example:**

Given committed `config.yaml`:
```yaml
vars:
  STATIC_DIR: ./static
build:
  static: ${STATIC_DIR}
```

And `.env`:
```
STATIC_DIR=./assets
```

The flow in `config.py` is:

1. Load `.env` → set `STATIC_DIR=./assets` in `os.environ`
2. Load committed `config.yaml` → `vars.STATIC_DIR = ./static`
3. Resolve `build.static = ${STATIC_DIR}`:
   - Check `os.environ` → found: `./assets` → **use `./assets`**
   - (would fall back to `vars:` only if env var didn't exist)
4. Result: `build.static = ./assets`

**`config.yaml` (committed in project root):**

```yaml
vars:
  STATIC_DIR: ./static
  DATA_DIR: ./data
  TEMPLATES_DIR: ./templates
  SCHEMAS_DIR: ./schemas
  OUTPUT_DIR: ./output
  FONTS_DIR: ${STATIC_DIR}/fonts
  CSS_DIR: ${STATIC_DIR}/css
  IMAGES_DIR: ${STATIC_DIR}/images/acquired

build:
  data: ${DATA_DIR}
  templates: ${TEMPLATES_DIR}
  static: ${STATIC_DIR}
  output: ${OUTPUT_DIR}
validate:
  data: ${DATA_DIR}
  schemas: ${SCHEMAS_DIR}
acquire-fonts:
  data: ${DATA_DIR}
  fonts_dir: ${FONTS_DIR}
  css_dir: ${CSS_DIR}
acquire-images:
  links: ${DATA_DIR}/links.json
  images_dir: ${IMAGES_DIR}
```

Without any env vars set, all values resolve through the `vars:` section to the current defaults, preserving backward compatibility. A user override config (`--config sites/alpha/config.yaml`) can redefine any subset — both `vars:` entries and per-command paths.

### Per-command CLI flags

The flags map one-to-one to config keys. Every output directory has its own flag — no shared `--output` with different semantics.

#### `build`

| Flag | Config key | Purpose |
|------|-----------|---------|
| `--data` | `build.data` | Directory with `site.config.json`, `links.json`, `design.json` |
| `--templates` | `build.templates` | Directory with Jinja2 templates |
| `--static` | `build.static` | Directory with static assets (CSS, JS, images, fonts) |
| `--output` | `build.output` | Directory to write the generated site into |

If `--output` points to an existing directory, it is removed and recreated (same as current behaviour).

#### `validate`

| Flag | Config key | Purpose |
|------|-----------|---------|
| `--data` | `validate.data` | Directory with `site.config.json`, `links.json`, `design.json` |
| `--schemas` | `validate.schemas` | Directory with `*.schema.json` files |

No `--output` — results go to console only.

#### `acquire-fonts`

| Flag | Config key | Purpose |
|------|-----------|---------|
| `--data` | `acquire-fonts.data` | Directory with `site.config.json` |
| `--fonts-dir` | `acquire-fonts.fonts_dir` | Directory to write `.woff2` font files into |
| `--css-dir` | `acquire-fonts.css_dir` | Directory to write `fonts.css` into |

The generated `fonts.css` uses **relative URL paths** from `css_dir` to `fonts_dir` (e.g. `../fonts/filename.woff2`). No separate URL configuration needed — it's always correct regardless of where the directories are.

#### `acquire-images`

| Flag | Config key | Purpose |
|------|-----------|---------|
| `--links` | `acquire-images.links` | Path to `links.json` |
| `--images-dir` | `acquire-images.images_dir` | Directory to write acquired images into |
| `--force` | — (flag) | Re-acquire all images (existing behaviour) |

#### `ingest`

Already fully configurable via existing CLI args. No changes required.

### `.env` file and environment variables

A `.env` file in the current working directory is auto-loaded if present. It defines semantic grouping variables that override the `vars:` section of any config file.

These variables are NOT script-facing. They feed into the config interpolation layer: when a config value contains `${STATIC_DIR}`, the resolver checks (1) environment, (2) user config's `vars:`, (3) committed config's `vars:`. Scripts only see the resolved specific paths (e.g. `fonts_dir: ./assets/fonts`, not `STATIC_DIR`).

Common variables:

| Variable | Purpose | Overrides in `vars:` |
|----------|---------|---------------------|
| `DATA_DIR` | Data files root | Yes |
| `TEMPLATES_DIR` | Templates root | Yes |
| `STATIC_DIR` | Static assets root | Yes |
| `SCHEMAS_DIR` | Schemas root | Yes |
| `OUTPUT_DIR` | Build output root | Yes |
| `FONTS_DIR` | Font files output | Yes |
| `CSS_DIR` | CSS output | Yes |
| `IMAGES_DIR` | Images output | Yes |
| `LLM_API_BASE` | LLM API base URL | — |
| `LLM_API_KEY` | LLM API key | — |
| `LLM_MODEL` | Default model | — |

### Usage examples

```bash
# Zero-config (committed defaults → current behaviour)
poetry run build

# Point at a different site with an override config
poetry run build --config sites/alpha/config.yaml

# Override specific paths on the CLI
poetry run build --data sites/alpha/data --templates shared/templates --output sites/alpha/_site

# Via .env: set semantic variables, everything derived automatically
# .env contains: STATIC_DIR=./assets  DATA_DIR=./content
poetry run build

# Acquire fonts with explicit control over every output
poetry run acquire-fonts --fonts-dir ./assets/fonts --css-dir ./assets/css
```

### Multi-site workflow

```
resourcery-projects/
├── site-alpha/
│   ├── config.yaml          # site-specific config (overrides defaults)
│   ├── data/
│   └── _site/                   (gitignored)
├── site-beta/
│   ├── config.yaml
│   ├── data/
│   └── _site/
└── shared/
    ├── templates/
    ├── schemas/
    └── static/
```

```bash
poetry run build --config resourcery-projects/site-alpha/config.yaml
poetry run validate --config resourcery-projects/site-beta/config.yaml
```

### Coordinator script (`site`)

A unified entry point that reads `config.yaml` once and dispatches to the right command. This avoids duplicate config loading when running multiple commands and provides a single CLI surface.

```bash
# Single command through the coordinator
poetry run site build --config sites/alpha/config.yaml
poetry run site validate --config sites/alpha/config.yaml
poetry run site acquire-fonts --config sites/alpha/config.yaml
poetry run site acquire-images --config sites/alpha/config.yaml

# Full pipeline
poetry run site all --config sites/alpha/config.yaml
```

**Behaviour:**

1. Reads and resolves the config file (committed defaults → user `--config` → env vars → CLI overrides)
2. For subcommands (`build`, `validate`, `acquire-fonts`, `acquire-images`): dispatches to the corresponding module's main function with resolved paths
3. For `all`: runs validate → acquire-fonts → acquire-images → build in sequence, stopping on first failure
4. Subcommand-specific CLI flags (e.g. `--output` for build, `--fonts-dir` for acquire-fonts) are passed through and override config values

**Design:** `src/resourcery_ssg/site.py` with `argparse` subparsers. Each subcommand forwards its known flags to the config resolver as overrides before calling the target function.

**Poetry script entry:**

```toml
[tool.poetry.scripts]
site = "resourcery_ssg.site:main"
# Individual scripts are kept for direct access without config:
build = "resourcery_ssg.build:main"
acquire-images = "resourcery_ssg.image_acquirer:main"
ingest = "resourcery_ssg.data_ingestion:main"
validate = "resourcery_ssg.validate:main"
acquire-fonts = "resourcery_ssg.font_acquirer:main"
```

The individual scripts remain unchanged and usable without config (they load the committed `config.yaml` automatically). The `site` coordinator adds convenience for config-driven workflows.

### Backward compatibility

`poetry run build` with no arguments, no `.env`, and no `--config` produces exactly the same result as today, because the committed `config.yaml` resolves `${STATIC_DIR}` to `./static` (from the `vars:` section) when no env var is set — matching the current hardcoded defaults.

### Internal architecture change

Python modules lose all module-level path constants. Functions accept paths as parameters:

```python
# Before (build.py)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
TEMPLATES_DIR = ROOT_DIR / "templates"

def build_site():
    config = load_json(DATA_DIR / "site.config.json")
    ...

# After (build.py)
def build_site(*, data_dir, templates_dir, static_dir, output_dir):
    config = load_json(data_dir / "site.config.json")
    ...

def main():
    config = load_config()  # reads committed + user config + env + CLI
    build_site(
        data_dir=config["build"]["data"],
        templates_dir=config["build"]["templates"],
        static_dir=config["build"]["static"],
        output_dir=config["build"]["output"],
    )
```

A shared config loader (`config.py` or similar) handles:

1. Loading committed `config.yaml` (with its `vars:` section)
2. Overlaying user `--config` (if specified) — merging its `vars:` and path sections
3. Resolving all `${VAR}` references: check env → user config vars → committed config vars
4. Overlaying CLI argument values onto resolved paths
5. Returning a frozen config dict to the caller

### Required new files

- **`config.yaml`** (committed in project root) — default path configuration with `vars:` section
- **`src/resourcery_ssg/config.py`** (new module) — config loading, `${VAR}` resolution, and CLI-overlay logic
- **`src/resourcery_ssg/site.py`** (new module) — coordinator entry point with subcommand dispatch

### Test implications

Tests no longer monkeypatch module-level path constants. Instead, they construct a minimal config dict or pass paths directly:

```python
# Before
monkeypatch.setattr("resourcery_ssg.build.DATA_DIR", testdata_dir)

# After
build_site(data_dir=testdata_dir, templates_dir=..., static_dir=..., output_dir=tmp_output_dir)
```

The `testdata_dir` fixture remains useful — it provides the path to testdata, which tests pass explicitly.

## Related specs

### Enables
- Multi-site workflows (no spec exists yet — this is a prerequisite)
- [feats/bookmark_import.md](../feats/bookmark_import.md) — import from different source directories
- [roadmaps/discovery_mvp.md](../../roadmaps/discovery_mvp.md) — multiple discovery sites from one checkout

### Extends
- [refactors/src_layout_package.md](src_layout_package.md) — continues the decoupling begun by moving to src/ layout

## Architecture: how config, CLI, env, and the coordinator work together

### Resolution priority chain

All path values pass through a four-layer priority chain implemented in `config.py`. Each layer overrides the layer below it:

```
CLI argument (highest priority)
  ↓
Environment variable / .env file
  ↓
User --config YAML (if specified)
  ↓
Committed config.yaml (lowest — default)
```

A value flows through all four layers: `config.py` loads the committed defaults, overlays a user config if provided (deep-merging both `vars:` and per-command sections), resolves `${VAR}` references against environment variables and the merged `vars:` section, then overlays any CLI overrides on top. The result is a frozen dict — callers cannot mutate it after resolution.

### The `config.py` module (`load_resourcery_config`)

`load_resourcery_config(config_path=None, overrides=None)` is the single entry point shared by every command. It:

1. **Loads `.env`** from the current working directory via `python-dotenv` (with a manual fallback parser if the library is unavailable). Variables are loaded into `os.environ` without overriding existing values.
2. **Loads the committed `config.yaml`** — bundled inside the package at `src/resourcery_ssg/config.yaml` and locatable via `Path(__file__).resolve().parent / "config.yaml"`. This file is the source of truth for default paths. It uses a `vars:` section to define semantic grouping variables (`STATIC_DIR`, `DATA_DIR`, etc.) and per-command sections that reference them via `${VAR}` syntax.
3. **Loads and merges user config** — if `config_path` is provided, the user's YAML is loaded and deep-merged with the committed config. Both `vars:` and per-command sections are merged, so users can override individual variables or entire path blocks.
4. **Resolves `${VAR}`** — the function walks the entire merged structure (dicts, lists, strings) and replaces `${VAR}` placeholders. Resolution order: `os.environ` → user `vars:` → committed `vars:`. Unresolved variables are left as-is rather than erroring, allowing optional env-driven overrides.
5. **Applies CLI overrides** — the `overrides` parameter accepts a flat dict of dotted keys like `{"build.output_dir": "/tmp/out"}`. These are expanded into nested dicts via `_expand_dotted_overrides()` and deep-merged on top of the resolved config.
6. **Converts paths** — string values that look like filesystem paths (starting with `.`, `/`, or containing `/`) are resolved relative to CWD and converted to `Path` objects. Values for known non-path keys (`model`, `opencode_bin`, `agent`) are excluded from path conversion because they legitimately contain slashes (e.g. model names like `opencode-go/deepseek-v4-flash`).
7. **Freezes the result** — returns a `types.MappingProxyType`-wrapped dict that raises `TypeError` on mutation attempts.

### Environment and `.env` integration

A `.env` file in CWD is auto-loaded if present. Its variables feed into `os.environ` and therefore participate in `${VAR}` resolution at the environment level — above both config file layers. Common variables:

| Env var | Overrides | Purpose |
|---------|-----------|---------|
| `DATA_DIR` | `vars.DATA_DIR` | Data files root |
| `STATIC_DIR` | `vars.STATIC_DIR` | Static assets root |
| `TEMPLATES_DIR` | `vars.TEMPLATES_DIR` | Templates root |
| `OUTPUT_DIR` | `vars.OUTPUT_DIR` | Build output root |
| `LLM_MODEL` | `ingest.model` | Default LLM model for data ingestion |

Because `.env` feeds into `os.environ` at the environment level, it overrides both the user config and the committed config — exactly as the priority chain specifies.

### The `site.py` coordinator

The coordinator (`src/resourcery_ssg/site.py`) provides a single entry point with subcommands:

```
site build --config <path> [--data ...] [--templates ...] [--static ...] [--output ...]
site validate --config <path> [--data ...] [--schemas ...]
site acquire-fonts --config <path> [--data ...] [--fonts-dir ...] [--css-dir ...]
site acquire-images --config <path> [--links ...] [--images-dir ...] [--force]
site ingest --config <path> --model <name> [--note ...] [--site-prompt ...]
site all --config <path> [--model <name>] [all subcommand flags]
```

Key design properties:

- **Single config load per invocation.** The `--config` flag is a top-level argument read before subcommand dispatch. A single call to `load_resourcery_config()` serves the entire invocation, with subcommand-specific CLI flags applied as overrides on top.
- **CLI flag → config key mapping.** Each subcommand's CLI flags map to config section keys via `ARG_TO_CONFIG_KEY`. For example, `--data` maps to `data_dir` (the config key) and the override is written as `build.data_dir`. This means the CLI never needs to know about the `_dir` suffix convention — the mapping is centralised.
- **`site all` runs the pipeline with dynamic step count.** When a model is configured (via config, `--model`, or env), ingestion runs as step 0, making it a 5-step pipeline (ingest → validate → acquire-fonts → acquire-images → build). Without a model, the pipeline runs 4 steps and skips ingestion silently. The step numbering in console output adjusts dynamically.
- **Static staging for multi-step pipelines.** The `all` subcommand seeds a writable staging directory from the base static source before running the acquisition steps. This prevents `acquire-fonts` and `acquire-images` from writing into a source-controlled static directory, and prevents `build` from destroying generated assets when it cleans the output directory. The staging mechanism is enabled by a `build.static_source` key in the config — when unset, the pipeline uses `static_dir` directly as both source and target (the manual workflow).
- **Each individual subcommand remains usable standalone.** The per-command scripts (`build`, `validate`, etc.) still work without the coordinator. They each load config independently, which is fine for single-command use but less efficient than the coordinator's single-load approach.

### Config-driven E2E workflow

A user-supplied config file (e.g. `tests/fixtures/e2e-config.yaml`) overrides only the paths relevant to the test scenario. Everything else inherits from the committed defaults via deep-merge. The common pattern is:

```yaml
vars:
  DATA_DIR: ./output/test-e2e-data     # staging area for generated JSON
  STATIC_DIR: ./output/test-e2e-static # staging area for generated static assets
  OUTPUT_DIR: ./output/test-e2e        # final output

build:
  static_source: ./static               # base static assets (seeded into staging)

ingest:
  note: ./tests/fixtures/markdown/notes/tech-links.md
  site_prompt: ./tests/fixtures/markdown/site_prompts/dev-portal.md
  model: ""
```

This keeps input fixtures in `tests/fixtures/`, intermediate generated files in `output/test-e2e-*/` staging directories, and the final built site in `output/test-e2e/`. The original unit-test fixtures in `data/testdata/` are never touched by the pipeline.

## Technical details

- `build_site()` signature changes from no arguments to `build_site(*, data_dir, templates_dir, static_dir, output_dir)`.
- `DataValidator.__init__()` gains explicit `data_dir` and `schemas_dir` parameters (replacing `root_dir`).
- `acquire_fonts()` signature changes from no arguments to `acquire_fonts(*, data_dir, fonts_dir, css_dir)`. The generated `fonts.css` uses relative paths from `css_dir` to `fonts_dir` for `@font-face src:` URLs.
- `ImageAcquirer.__init__()` gains explicit `images_dir` parameter (replacing `root_dir`-based derivation).
- A new `config.py` module provides `load_resourcery_config(config_path=None, overrides=None)` that:
  - Loads the committed `config.yaml` (including its `vars:` section) from the package directory
  - Overlays a user-specified config file if `--config` is given — merging both `vars:` and per-command sections
  - Resolves all `${VAR}` references by checking: env var → user config `vars:` → committed config `vars:`
  - Overlays CLI argument values onto resolved paths
  - Returns a `dict` with per-command sections
- `.env` is loaded via `python-dotenv` if available, otherwise a simple manual parser (the project already has `pyyaml` as a dependency — that covers the YAML side).
- Paths in the resolved config and CLI args are relative to the **current working directory** and resolved with `Path(value).resolve()`.
- The committed `config.yaml` is bundled with the package (installed alongside the Python modules) so it is available when the tool is used via `pipx` or as a library.
