---
size: medium
modified_date: 2026-07-26
implemented_git_tag: specs/refactors/src_layout_package.md/implemented
---

# Standard Python package with `src/` layout (PEP 517/518)

## Introduction

All Python source files currently live in the project root. This makes it impossible
to install the project as a proper Python package, forces fragile imports in tests
(which rely on the working directory coinciding with the root), and prevents tools
like `pip install -e .` from working correctly.

Moving to a `src/` layout with a `resourcery_ssg` namespace package follows the
recommendations of PEP 517 (build-system independent format) and PEP 518
(pyproject.toml configuration). This is the standard approach used by the Python
ecosystem for modern Python packaging. It cleans up the project root, enables
clean editable installs during development, and makes future growth (subpackages,
PyPI publishing) straightforward.

## Current state

All 6 Python source modules live in the project root:

```
Resourcery.ssg/
├── build.py                 # CLI: build
├── validate.py              # (no CLI script defined)
├── font_acquirer.py         # (no CLI script defined)
├── image_acquirer.py        # CLI: acquire-images
├── data_ingestion.py        # CLI: ingest
├── theme_constants.py       # shared utility, no CLI
├── tests/
│   ├── test_build.py        # imports from build
│   ├── test_validate.py     # imports from validate
│   ├── test_font_acquirer.py
│   ├── test_image_acquirer.py
│   ├── test_data_ingestion.py
│   └── test_theme_constants.py
├── pyproject.toml           # scripts point to root modules
├── data/
├── schemas/
├── templates/
├── static/
└── ...
```

Cross-module imports within the source use root-level names:
- `build.py` imports `theme_constants`
- `font_acquirer.py` imports `theme_constants`
- `validate.py` imports `font_acquirer` and `theme_constants`

Three files use `Path(__file__).parent` at module or instance level to locate
the project root (for building paths to `data/`, `static/`, `templates/`, `schemas/`):
- `build.py` — `ROOT_DIR = Path(__file__).parent`
- `validate.py` — `self.root_dir = root_dir or Path(__file__).parent`
- `font_acquirer.py` — `ROOT_DIR = Path(__file__).parent`

Tests use `monkeypatch.setattr()` with string module paths like `"build.DATA_DIR"`,
`"font_acquirer.DATA_DIR"`, `"image_acquirer.PUPPETEER_AVAILABLE"`, etc.

The project has no `packages` configuration in `pyproject.toml`, so Poetry
looks for packages in the root directory only.

The function `build()` in `build.py` shares a name with Python's stdlib `build`
module. While this is not a runtime error (the stdlib module is not imported), it
is a naming anti-pattern that becomes more visible inside a proper package.

## Target state

### Directory structure

```
Resourcery.ssg/
├── src/
│   └── resourcery_ssg/
│       ├── __init__.py          # new — docstring only, no re-exports
│       ├── build.py             # moved from root
│       ├── validate.py          # moved from root
│       ├── font_acquirer.py     # moved from root
│       ├── image_acquirer.py    # moved from root
│       ├── data_ingestion.py    # moved from root
│       └── theme_constants.py   # moved from root
├── tests/
│   └── ...                      # imports updated to package paths
├── pyproject.toml               # updated: packages, scripts
├── data/
├── schemas/
├── templates/
├── static/
├── .gitignore                  # no changes expected
├── CONTRIBUTING.md             # updated to reflect new paths
└── ...
```

### Behavioural changes

| Area | Before | After |
|------|--------|-------|
| Module identity | `build`, `validate`, etc. | `resourcery_ssg.build`, `resourcery_ssg.validate` |
| Local imports | `from theme_constants import ...` | `from resourcery_ssg.theme_constants import ...` |
| Test imports | `from build import ...` | `from resourcery_ssg.build import ...` |
| CLI scripts | `build`, `acquire-images`, `ingest` | same names preserved; `validate` and `acquire-fonts` added |
| Project root resolution | `Path(__file__).parent` (1 level up) | `Path(__file__).resolve().parent.parent.parent` (3 levels up) |
| Editable install | not possible | `poetry install` works, tests run from anywhere |
| Python entry points | root-level bare modules | qualified as `resourcery_ssg.build:build_site` |
| `build()` function renamed | `build()` | `build_site()` |

There is **no change** to:
- The CLI command names users run (`poetry run build`, `poetry run validate`, etc.)
- The function signatures, class interfaces, or any public API other than the
  renamed `build()` → `build_site()`
- How `build.py` reads data, renders templates, or produces output
- How `validate.py` performs validation
- How tests discover fixtures or work with test data
- The Jinja2 templates, static assets, JSON schemas, or data files

### Configuration changes (`pyproject.toml`)

1. **Add packages configuration** so Poetry discovers the package under `src/`:
   ```toml
   [tool.poetry]
   packages = [{ include = "resourcery_ssg", from = "src" }]
   ```

2. **Update existing CLI scripts** to use qualified module paths and the renamed
   `build_site` function:

   | Script name | Before | After |
   |-------------|--------|-------|
   | `build` | `build:build` | `resourcery_ssg.build:build_site` |
   | `acquire-images` | `image_acquirer:main` | `resourcery_ssg.image_acquirer:main` |
   | `ingest` | `data_ingestion:main` | `resourcery_ssg.data_ingestion:main` |

3. **Add missing CLI scripts** (user-facing tools that are currently only
   callable via `python path/to/file.py`):

   | Script name | Entry point |
   |-------------|-------------|
   | `validate` | `resourcery_ssg.validate:main` |
   | `acquire-fonts` | `resourcery_ssg.font_acquirer:main` |

### Code changes

#### 1. Rename `build()` to `build_site()` in `build.py`

The function `build()` (the build entry point) is renamed to `build_site()` to
avoid shadowing Python's stdlib `build` module. The `if __name__ == '__main__'`
guard and the CLI entry point both call `build_site` instead.

#### 2. Cross-module import changes (within `src/resourcery_ssg/`)

| File | Current import | New import |
|------|---------------|------------|
| `build.py` | `from theme_constants import ...` | `from resourcery_ssg.theme_constants import ...` |
| `font_acquirer.py` | `from theme_constants import ...` | `from resourcery_ssg.theme_constants import ...` |
| `validate.py` | `from font_acquirer import ...` | `from resourcery_ssg.font_acquirer import ...` |
| `validate.py` | `from theme_constants import ...` | `from resourcery_ssg.theme_constants import ...` |

#### 3. Project root resolution

Files that resolve the project root via `Path(__file__).parent` must go up
additional levels to account for the new `src/resourcery_ssg/` depth:

| File | Variable/usage | Current | New |
|------|---------------|---------|-----|
| `build.py` | `ROOT_DIR` | `Path(__file__).parent` | `Path(__file__).resolve().parent.parent.parent` |
| `font_acquirer.py` | `ROOT_DIR` | `Path(__file__).parent` | `Path(__file__).resolve().parent.parent.parent` |
| `validate.py` | `DataValidator.__init__` default | `root_dir or Path(__file__).parent` | `root_dir or Path(__file__).resolve().parent.parent.parent` |

(The implementation may choose to extract `_PROJECT_ROOT` into `__init__.py` and
share it — this is a style decision left to the planner.)

### Test changes

1. **Import paths**: All test imports that currently reference root-level modules
   must be updated to reference the `resourcery_ssg` package:
   ```
   - from build import load_json, validate_data, shuffle_filter, ...
   + from resourcery_ssg.build import load_json, validate_data, shuffle_filter, ...
   ```
   Specifically: `build` → `resourcery_ssg.build`, `validate` → `resourcery_ssg.validate`,
   `font_acquirer` → `resourcery_ssg.font_acquirer`, `image_acquirer` → `resourcery_ssg.image_acquirer`,
   `data_ingestion` → `resourcery_ssg.data_ingestion`, `theme_constants` → `resourcery_ssg.theme_constants`.

2. **monkeypatch string paths**: All `monkeypatch.setattr()` calls that use
   string module paths must be updated:
   - `"build.DATA_DIR"` → `"resourcery_ssg.build.DATA_DIR"`
   - `"font_acquirer.DATA_DIR"` → `"resourcery_ssg.font_acquirer.DATA_DIR"`
   - `"image_acquirer.PUPPETEER_AVAILABLE"` → `"resourcery_ssg.image_acquirer.PUPPETEER_AVAILABLE"`
   - `"font_acquirer.fetch_google_fonts_css"` → `"resourcery_ssg.font_acquirer.fetch_google_fonts_css"`
   - `"font_acquirer.FONTS_DIR"` → `"resourcery_ssg.font_acquirer.FONTS_DIR"`
   - `"font_acquirer.CSS_DIR"` → `"resourcery_ssg.font_acquirer.CSS_DIR"`
   - And any other instance of this pattern.

3. **`build` → `build_site` references**: The test imports `build` (the function)
   from `build.py`. This becomes `build_site`:
   ```
   - from build import ..., build,
   + from resourcery_ssg.build import ..., build_site,
   ```
   And in the integration test:
   ```
   - build()
   + build_site()
   ```

4. **No other test logic changes.** Tests continue to use `data/testdata/` fixtures
   and the same pytest configuration. All tests must pass after the migration with
   no changes to test logic, conftest, or fixture definitions.

### Documentation

`CONTRIBUTING.md` must be updated:
- The "File / Folder Roles" table — paths change from `build.py` to
  `src/resourcery_ssg/build.py`, etc.
- The "Python Modules" section — import examples and patterns change.
- The "Architecture" section — references to file paths in diagrams and lists
  reflect the new structure.

`README.md` quick start section must be updated:
- Replace `poetry run python validate.py` with `poetry run validate`
- Replace `poetry run python image_acquirer.py` with `poetry run acquire-images`
- Replace `poetry run python build.py` with `poetry run build`
- The "Build" table entry changes from `build.py` to `src/resourcery_ssg/build.py`

## Open questions

None resolved — see decisions above.

## Technical details

- **Tests must pass after the move with no logic changes.** The entire migration
  is mechanical path/import changes. If a test fails, the migration is incomplete.
- **Do not break `Path(__file__).parent` usage.** This is the most common subtle
  bug in `src/`-layout migrations. Every file that uses it must be updated.
- **`poetry install` must work** after the migration for tests and CLI scripts.
  Run `poetry install` and verify `poetry run build`, `poetry run validate`, etc.
- **No git history is lost.** Use `git mv` to move files so git tracks the renames.
- **All migrated root `.py` files** should be removed from the root after the move
  (they become dead symlinks or stubs otherwise).
- **`__init__.py`** should be minimal — a module docstring describing the package.
  Avoid re-exports to prevent circular import risk.
- **`acquire-fonts` CLI** follows the `acquire-` prefix convention set by
  `acquire-images`.
- **Rename `build()` → `build_site()`** as part of this migration to resolve the
  stdlib name clash. The CLI command name `build` is preserved — only the
  underlying function and the `pyproject.toml` entry point change.

## Related specs

### Affected (path references become stale)

The following implemented specs reference root-level module paths that this
restructuring changes. These specs are implemented and their behavioural scope is
immutable, but the path references are now outdated. A note will be appended to
each affected spec identifying the new paths:

- **`specs/refactors/data_design_split.md`** (implemented `d405920`) —
  References `build.py`, `validate.py`, `font_acquirer.py`, `image_acquirer.py`,
  and `data_ingestion.py` as root-level modules in pipeline flow descriptions.

- **`specs/tests/testing.md`** (implemented `d45343d`) —
  References `build.py`, `validate.py`, `font_acquirer.py`, `image_acquirer.py`,
  and `theme_constants.py` as root-level modules in integration test definitions.

- **`specs/feats/data_ingestion.md`** (implemented) —
  References `data_ingestion.py`, `validate.py`, and `build.py` as root-level
  modules alongside each other.

- **`specs/docs/docstring.md`** (implemented `1cf3cb7`) —
  References Python files generically; less affected but references module names
  at root level.
