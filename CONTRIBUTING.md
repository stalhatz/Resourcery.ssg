# Contributing to Resourcery.ssg

## File Structure

### File / Folder Roles

| Path | Type | Role |
|------|------|------|
| `build.py` | Python script | Main entry point. Renders Jinja2 templates into static HTML/CSS, copies static assets, pre-computes category maps and tag lists from JSON data. |
| `validate.py` | Python script | Data integrity gate. Validates JSON data against JSON Schema (draft-07), cross-validates categories/tags/IDs, checks hex colors, URLs, font availability, and effect compatibility. |
| `font_acquirer.py` | Python script | Build-time Google Font downloader. Fetches `.woff2` files from Google Fonts API, caches locally, generates `fonts.css` with embedded `@font-face` rules. Zero CDN dependency at runtime. |
| `image_acquirer.py` | Python script | Link image downloader. Extracts images from link URLs via `og:image` meta tags or headless Puppeteer screenshots. |
| `theme_constants.py` | Python script | Single source of truth for heading style configuration (weight, letter-spacing, required font weights). Imported by `build.py` and `font_acquirer.py`. |
| `schemas/links.schema.json` | JSON Schema | JSON Schema definition for `data/links.json`. Defines required properties, types, and constraints for every link entry. |
| `schemas/site.config.schema.json` | JSON Schema | JSON Schema definition for `data/site.config.json`. Defines theming, effects, navigation, and metadata shape. |
| `templates/` | Directory | Jinja2 templates that produce the static site output. |
| `templates/base.html` | Jinja2 template | Shell layout. DOCTYPE, `<head>`, theme injection, navigation, footer, modal shell, JS globals from build context. Extended by all page templates. |
| `templates/index.html` | Jinja2 template | Landing page. Renders featured links (shuffled, limited by `featured_count`), hero section. |
| `templates/browse.html` | Jinja2 template | Browse/filter page. Renders all links with `data-*` attributes for client-side filtering, sorting, search. |
| `templates/modal.html` | Jinja2 template | Link detail modal. Populated from `data-*` attributes on card elements at runtime. |
| `templates/style.css` | Jinja2 template | Themed CSS. Rendered through Jinja2 to inject `--color-*`, `--shadow-*`, `--border-radius`, `--heading-*` CSS custom properties from `site.config.json`. |
| `static/` | Directory | Source static assets. Copied verbatim into `output/static/` during build. |
| `static/js/main.js` | JavaScript | All client-side interactivity: tag search, category filtering, sorting, modal, dark mode, sidebar, URL hash routing. ES5-compatible. |
| `static/images/acquired/` | Directory | Downloaded link images (from `image_acquirer.py`). |
| `output/` | Directory | Build output (gitignored). Complete static site ready for any HTTP server. |
| `schemas/` | Directory | JSON Schema files. Used for validation and as LLM prompt guidance during data creation. |
| `pyproject.toml` | Config | Poetry project configuration. Defines dependencies (production + dev), scripts (`build`, `acquire-images`), and tool configs (Black, pytest). |
| `poetry.lock` | Lock file | Poetry dependency lock. Commit to ensure reproducible builds. |

---

## Version Control

### Branch Strategy

- `main` is the single long-lived branch.
- Work is committed directly to `main`. No feature branches or PR workflow is currently established.
- To add feature branch workflow, create branches off `main` named `feat/<short-description>` or `fix/<short-description>`.

### Commit Style

Conventional commit prefixes are used:

| Prefix | When to use |
|--------|-------------|
| `feat:` | A new feature or capability |
| `fix:` | A bug fix |
| `refactor:` | Code restructuring without behavior change |
| `bumped` | Dependency version updates |
| `Updated` | Documentation or non-functional changes |

Commit messages should be descriptive but concise (one line). Example:

```
feat: build-time Google Font acquisition. No runtime CDN dependency
```

### What Is Tracked / Ignored

**Tracked:** Python source, Jinja2 templates, JSON schemas, config files (`pyproject.toml`, `poetry.lock`), documentation.

**Not tracked** (in `.gitignore`): `data/` (input data), `output/` (build artifacts), `*.sh` files, images, font binaries, IDE config (`.vscode/`, `.kilo/`).

---

## Architecture

### Overview

Resourcery.ssg is a **static site generator (SSG)** with zero runtime dependencies. All processing happens at build time, producing a directory of plain HTML/CSS/JS that works with any HTTP server.

```
JSON Data Files  ──>  Validate ──>  Render Jinja2 ──>  Static Site
(site.config.json      (validate.py)    (build.py)        (output/)
 + links.json)
                          │
                    Acquire Assets
                    (fonts, images)
```

### Design Principles

1. **Zero runtime dependencies.** No CDN, no API calls, no JavaScript frameworks. Everything is downloaded or rendered at build time.
2. **Separation of concerns.** Each Python script is a standalone entry point: validation, build, font acquisition, image acquisition. Single file per concern.
3. **Data-on-DOM pattern.** All link metadata is embedded in `data-*` attributes on card elements. The modal reads from these attributes — no template re-rendering needed.
4. **Build-time pre-computation.** `category_map` and `all_tags` are computed once during build and serialized into `window` globals. The browser never parses full data for these lookups.
5. **URL hash routing.** All filter/sort/tag/search state is encoded in the URL fragment. Enables bookmarkable links and browser back/forward.
6. **CSS Variables for theming.** Entire visual identity is controlled by CSS custom properties injected at build time from `site.config.json`.
7. **Progressive enhancement.** Filters have native `<select>` fallbacks. JS failure degrades gracefully.
8. **LLM-friendly design.** JSON Schema `description` fields are written to guide LLMs in generating appropriate data. The README includes a full LLM prompt template.

### Python Modules

Each Python module is a standalone CLI with a `main()` function and `if __name__ == '__main__'` guard. They share no state — data flows through JSON files on disk and Python data structures passed to Jinja2.

```python
# Standard pattern:
def main():
    ...

if __name__ == '__main__':
    main()
```

### Frontend

All JavaScript is vanilla ES5-compatible, organized into **singleton manager objects**:

| Object | Responsibility |
|--------|---------------|
| `TagManager` | Active tag state, search suggestions |
| `ModalManager` | Open/close link detail modals |
| `ThemeManager` | Dark/light mode toggle with `localStorage` persistence |
| `SidebarManager` | Collapsible category accordion, mobile overlay |
| `CardManager` | Click/keyboard handlers on link cards |
| `FilterManager` | Custom dropdown for category/sort with full ARIA |

Global functions (`filterCards()`, `sortCards()`, `handleHashChange()`) coordinate between managers. The URL `hashchange` event is the single source of truth for application state.

### JSON Data Shape

**`data/site.config.json`:**
```json
{
  "site": { "title", "description", "url", "language" },
  "brand": { "name", "tagline", "logo" },
  "theme": { "colors", "effects", "fonts", "layout" },
  "navigation": [{ "label", "href", "icon" }],
  "placeholders": { "avatar", "image" },
  "metadata": { "author", "license", "version" }
}
```

**`data/links.json`:** Array of objects with `id`, `title`, `url`, `description`, `category_id`, `tags`, `image`, `dates` (created, updated, checked), and optional properties (`comment`, `priority`, `archived`).

---

## Docstring Style

### Python

- **Module-level docstring:** Triple-quoted string at top of file describing the module's purpose.
- **Class docstring:** Triple-quoted string describing class responsibility.
- **Function docstring:** Triple-quoted for nontrivial functions, describing what the function does and what it returns. No reStructuredText or Google-style parameter docs.
- **Inline comments:** Used sparingly for non-obvious logic.

```python
"""
Build script for static link aggregation site.
Renders Jinja2 templates with JSON data.
"""


def extract_google_font_candidates(stack: str) -> list:
    """Return all non-system font names from a CSS font-family stack, in order."""
    ...
```

### JavaScript

- **File header:** Block comment `/* ... */` describing the module.
- **Section dividers:** `// ==================== SECTION NAME ====================`
- **Inline notes:** Line comments `//` for bugfix markers, removed code annotations.
- **No JSDoc types.** Functions are not formally documented beyond naming.

### CSS (Jinja2 template)

- **Section dividers:** `/* ============ SECTION ============ */`
- **Override notes:** `/* image-overlay: no overrides needed — base styles handle it */`

### JSON Schema

- **`description` fields** serve dual purpose: human documentation and LLM prompt guidance. Write them as complete sentences describing valid values and their meaning.

---

## Data Flow

### Build Pipeline (sequential)

```
Step 1: validate.py
  ├── Load JSON Schema from schemas/
  ├── Load data from data/
  ├── Validate schema compliance
  ├── Cross-validate: categories exist, IDs unique, colors valid, URLs valid
  ├── Validate effects combinations
  └── Validate Google Font availability

Step 2: font_acquirer.py
  ├── Read theme_constants.py for required font weights
  ├── Check font-family stacks in site.config.json
  ├── Check cache (fonts.css line 1 metadata)
  ├── Download missing .woff2 from Google Fonts API
  └── Write fonts.css with @font-face rules

Step 3: image_acquirer.py (optional)
  ├── For each link without a local image:
  │   ├── Fetch URL, parse og:image meta tag
  │   └── Fallback: headless Puppeteer screenshot
  └── Save to static/images/acquired/

Step 4: build.py
  ├── Clean output/
  ├── Load validated data
  ├── Pre-compute category_map and all_tags
  ├── Resolve heading style values from theme_constants.py
  ├── Set up Jinja2 environment
  ├── Render: index.html, browse.html, style.css
  └── Copy: static/images/, static/js/, static/fonts/, static/css/fonts.css
```

### Data to Browser

```
build.py renders templates ──> output/*.html
                                  │
                          Inline <script> tags:
                          window.APP_CONFIG    = (from site.config.json)
                          window.LINKS_DATA    = (from links.json)
                          window.CATEGORY_MAP  = (pre-computed)
                          window.ALL_TAGS      = (pre-computed)
                                  │
                          Browser JS reads globals
                          to filter/sort/search
                          with URL hash as state
```

### Client-Side State Flow

```
URL hash (#category-x, #tag-y, #search-z)
    │
    ▼
handleHashChange() on load + hashchange event
    │
    ├── FilterManager updates category dropdown
    ├── TagManager updates tag/search state
    └── filterCards()
            │
            ├── Reads hash, globals, data-* attributes
            ├── Shows/hides card DOM nodes directly
            └── sortCards() reorders by date/title
                    │
                    └── ModalManager opens modal from card data-* attributes
```

**Key point:** The DOM is the data layer. Card elements carry all their metadata as `data-*` attributes. Filtering is done by toggling `display: none` — no virtual DOM, no re-rendering.

---

## Notes

- **`theme_constants.py` is a shared dependency** between `build.py` and `font_acquirer.py`. Both import it. If you change heading styles, update the constant, not each file.
- **`tojson` filter** is used in Jinja2 for safe Python→JavaScript serialization (`{{ config \| tojson }}`). Never use `json.dumps()` manually for template injection.
- **Font cache invalidation** is done by comparing the first line of `static/css/fonts.css` (a `/* {"font_name": {...}} */` JSON comment) against requested fonts. If any font is missing or has different weights, only the needed fonts are re-downloaded.
- **Effects presets** in `site.config.json` (`card_style`, `shadow_intensity`, `border_radius`, etc.) are documented in the schema with valid values. Adding a new effect value requires updating both the schema and the CSS template.
- **Shell scripts (`.sh`)** are gitignored. They are local development conveniences, not part of the build system.
- **The `plans/` and `specs/` directories** exist as placeholders for future planning documents.
- **`AGENTS.md` is empty** — reserved for AI agent instructions if needed.
- **No tests exist** despite `pytest` being in dev dependencies. The `validate.py` script serves as the data integrity gate in lieu of unit tests.
- **`data/CV/`** is an alternative dataset (French-language CV resources) with its own `site.config.json`. The build script does not reference it — it's kept for reference.

---

## Todo

### Short-term

- [ ] Write unit tests for `validate.py` (category cross-validation, effects logic, font checking)
- [ ] Write unit tests for `build.py` (template rendering, asset copying, pre-computation)
- [ ] Write unit tests for `font_acquirer.py` (cache hit/miss, font parsing)
- [ ] Add `tests/` directory and `pytest` configuration to `pyproject.toml`
- [ ] Add CI configuration (GitHub Actions or similar) to run validation + tests on push
- [ ] Standardize type hints across all Python modules (currently inconsistent)
- [ ] Document the `data/CV/` alternative dataset or remove it from the repo
- [ ] Add a lint step (`black --check`) to the build pipeline

### Long-term

- [ ] Consider extracting category/tag/effect validation into a dedicated validation module instead of inline functions in `validate.py`
- [ ] Evaluate migrating frontend JS to TypeScript with JSDoc types (no build step needed — TS can check plain JS via `// @ts-check`)
- [ ] Add end-to-end tests that build the site and verify output HTML structure
- [ ] Evaluate CSS minification as a build step (e.g., `cssnano` via Python subprocess)
- [ ] Add HTML validation (`nu-html-checker` or similar) to the build pipeline
- [ ] Consider a headless CMS or YAML frontmatter approach for link authoring
- [ ] Evaluate incremental builds (skip re-rendering if data hasn't changed)
- [ ] Add RSS/Atom feed generation from links data
- [ ] Add sitemap.xml generation for SEO
- [ ] Consider moving from Poetry to pip/uv for simpler dependency management
- [ ] Add support for multiple theme variants from a single config
