---
size: small
modified_date: 2026-07-28
implemented_git_tag: specs/feats/build_attribution/implemented
---

# Optional Build Attribution Footer

## Introduction

Resourcery.ssg sites are generated from two human-authored source files: a note (raw markdown listing links) and a site prompt (a short text describing the site's purpose and audience). These source files are the true *origin* of the site's content — every link, every category, and every design decision traces back to them.

Today, there is no visible attribution on the generated site. Visitors see the curated content but have no indication that the site was automatically generated, what tool produced it, or what source materials were used. This matters when the site is shared publicly (e.g., as a discovery portal) — it should wear its provenance visibly but unobtrusively, establishing trust and transparency.

This spec adds a **single boolean flag** that enables a small attribution footer on every generated page, plus two auto-generated source pages that display the original note and site prompt as rendered HTML. The entire feature is opt-in and off by default.

## Current state

- `build_site()` renders two HTML pages: `index.html` and `browse.html` (plus a themed `style.css`). All pages extend `base.html` via Jinja2 block inheritance.
- `base.html` contains a `<footer>` element (lines ~115-129) that renders `copyright`, `text`, and `links` from `site.config.json` (`config.content.footer.*`). No other content exists in the footer.
- The `config.yaml` `build:` section has four keys: `data_dir`, `templates_dir`, `static_dir`, `output_dir`. No attribution flag exists.
- The `ingest:` section of `config.yaml` does **not** include `note` or `site_prompt` keys — these are passed exclusively via CLI flags to `data_ingestion.py`. They are not persisted in any config file, so the build pipeline has no way to discover the source files.
- No Python markdown-to-HTML library is present in `pyproject.toml`.
- The `_NON_PATH_KEYS` set in `config.py` (`model`, `opencode_bin`, `agent`) prevents path resolution for known non-path strings. No changes are needed for this feature (booleans are unaffected by `_resolve_paths`).

## Target state

### Flag

A single boolean, `build.attribution`, is added to the committed `config.yaml` under the `build:` section.

```yaml
build:
  data_dir: ${DATA_DIR}
  templates_dir: ${TEMPLATES_DIR}
  static_dir: ${STATIC_DIR}
  output_dir: ${OUTPUT_DIR}
  # attribution: false           # uncomment and set to true to enable
```

- If absent → treated as `false` (no behaviour change).
- If `false` → no footer note, no source pages generated.
- If `true` → footer note appears on every page AND `note.html`/`prompt.html` are generated.

### Footer note

When `build.attribution` is `true`, every generated page (`index.html`, `browse.html`, `note.html`, `prompt.html`) renders an additional line in the existing `<footer>` section of `base.html`:

> *"This web site was created automatically using Resourcery.ssg using this note file and this prompt file as inputs"*

Link mapping:

| Phrase | Link target |
|--------|-------------|
| "Resourcery.ssg" | `https://github.com/stalhatz/Resourcery.ssg` |
| "this note file" | `note.html` |
| "this prompt file" | `prompt.html` |

**Rendering requirements:**
- The note appears inside the existing `<footer class="main-footer">` element, after the existing `copyright`/`text`/`links` content.
- Rendered conditionally in `base.html` via a new `attribution_enabled` context variable (boolean).
- Visually distinct but unobtrusive — a single line of subtle text (e.g., small font size, muted color, separated from footer links above by a thin horizontal rule or margin).
- The exact visual styling is left to the implementer; the spec only constrains it to be "subtle and unobtrusive."

### Source pages (`note.html` and `prompt.html`)

When `build.attribution` is `true`, the build pipeline generates two additional HTML pages in the output directory:

| Page | Content displayed | Config key for source path |
|------|-------------------|----------------------------|
| `output/note.html` | Full content of the source markdown note file, converted to HTML | `ingest.note` |
| `output/prompt.html` | Full content of the source site prompt markdown file, converted to HTML | `ingest.site_prompt` |

**Source file paths:**
- Come from the resolved config (`ingest.note` and `ingest.site_prompt`).
- These keys are **user-provided** — they do not exist in the committed `config.yaml` by default. The committed config gains **commented-out example entries** under the `ingest:` section:

```yaml
ingest:
  #  ...
  # note: ./my-links.md                 # optional — path to source note file
  # site_prompt: ./my-purpose.md        # optional — path to site prompt file
```

- If `build.attribution` is `true` but either `ingest.note` or `ingest.site_prompt` is absent from the resolved config, the build step raises a clear error and exits.
- If the paths exist in config but the files do not exist on disk, the build step raises a clear error and exits.

**Template: `source.html`**

A new Jinja2 template at `templates/source.html` that:

1. Extends `base.html` (full site chrome: sidebar, header, footer).
2. Renders the markdown content (converted to HTML) inside the `{% block content %}` area.
3. Sets the page `<title>` to a descriptive label derived from a context variable (e.g., `"Source Note — <site name>"` or `"Site Prompt — <site name>"`).
4. The content area scrolls naturally (the markdown source may be long).

**Markdown-to-HTML conversion:**
- The raw markdown file is read as UTF-8 text.
- Content is converted to full HTML (headings, lists, bold/italic, links, code blocks, images, blockquotes, horizontal rules, etc.).
- Requires a new Python dependency added to `pyproject.toml` (e.g., `mistune`, `markdown`, or `markdown-it-py`). The implementer should choose the lightest suitable library.
- The converted HTML is passed to the template as a `source_content` context variable, already safe for rendering (the markdown library's HTML output, not escaped again).
- The page title is passed as a `source_title` context variable (e.g., `"Source Note"` or `"Site Prompt"`).

### Build pipeline changes

In `build.py` → `build_site()`:

1. Read `build.attribution` from the resolved config. Absent → treat as `false`.
2. If `true`:
   - Read `ingest.note` and `ingest.site_prompt` from the resolved config.
   - If either key is missing → raise a clear error: `"build.attribution is enabled but ingest.note is not set in config"` (respectively).
   - If either file does not exist on disk → raise a clear error: `"Cannot find note file at <resolved-path>"`.
   - Read both markdown files as UTF-8 text.
   - Convert markdown to HTML using the chosen library.
   - Render `templates/source.html` twice:
     - First pass: `source_content=<note-html>`, `source_title="Source Note"`, plus `attribution_enabled=True`.
     - Second pass: `source_content=<prompt-html>`, `source_title="Site Prompt"`, plus `attribution_enabled=True`.
   - Write to `output_dir / "note.html"` and `output_dir / "prompt.html"`.
   - Pass `attribution_enabled=True` in `base_context` so `base.html` conditionally renders the footer note on **all** pages.
3. If absent/false:
   - Pass `attribution_enabled=False` in `base_context`.
   - Skip source page generation entirely.

**Interaction with `site.py` coordinator:**

The `site.py` coordinator's `build` and `all` subcommands already forward all build-level CLI flags to `load_resourcery_config()`. Since `build.attribution` is a config-only key (no dedicated CLI flag), it flows through the standard config resolution. No changes to `site.py` are required.

### Dependencies

A new Python markdown library is added to `pyproject.toml`. Candidates (the implementer chooses):

| Library | Size | Key features |
|---------|------|-------------|
| `mistune` | ~30KB, zero deps | Fast, pure Python, GitHub-Flavored Markdown via plugin |
| `markdown` | ~200KB | Most mature, extension system, widely used |
| `markdown-it-py` | ~600KB | Modern, CommonMark spec-compliant, fast |

The choice should favor the lightest library that handles standard Markdown with fenced code blocks, tables, and inline HTML (the features authors are likely to use in their note/prompt files).

### Error handling

| Condition | Behaviour |
|-----------|-----------|
| `build.attribution` absent or `false` | No attribution, no source pages. Normal build. |
| `build.attribution: true` but `ingest.note` missing from config | Build exits with error: `"Error: build.attribution is enabled but ingest.note is not set in config. Add 'note' under the 'ingest' section."` |
| `build.attribution: true` but `ingest.site_prompt` missing | Build exits with error: `"Error: build.attribution is enabled but ingest.site_prompt is not set in config. Add 'site_prompt' under the 'ingest' section."` |
| `build.attribution: true` but file at `ingest.note` path not found | Build exits with error: `"Error: Cannot read note file: <resolved-path>"` |
| `build.attribution: true` but file at `ingest.site_prompt` path not found | Build exits with error: `"Error: Cannot read site prompt file: <resolved-path>"` |
| `build.attribution: true` but file is not valid UTF-8 | Build exits with error: `"Error: Cannot decode <filename> as UTF-8"` |

### Config changes summary

**Committed `config.yaml`**:

1. `build:` section gains `# attribution: false` (commented out, with documentation comment).
2. `ingest:` section gains two commented-out entries:
   ```yaml
   # note: ./path/to/your-note.md
   # site_prompt: ./path/to/your-site-prompt.md
   ```

No new CLI flags are introduced. The `site.py` coordinator and individual scripts are unchanged.

## Acceptance criteria

1. **Default off.** Running `poetry run build` (or `site build`) with no `build.attribution` key in config produces exactly the current output — no footer note, no `note.html`/`prompt.html` pages.

2. **Flag presence toggles everything.** Setting `build.attribution: true` in the resolved config enables **both** the footer note (on all 4 generated pages) **and** the source page generation. Setting it to `false` or omitting it disables both.

3. **Footer appears on all pages.** When enabled, the attribution line is visible in the footer of `index.html`, `browse.html`, `note.html`, and `prompt.html` — each with working links to the GitHub repo and to `note.html`/`prompt.html`.

4. **Source pages render valid HTML.** `note.html` and `prompt.html` extend `base.html`, display the full markdown content rendered as HTML (headings, lists, links, code blocks, etc.), set a meaningful page title, and are reachable via their filenames.

5. **Missing config keys produce clear errors.** If `build.attribution` is `true` but `ingest.note` or `ingest.site_prompt` is absent from the resolved config, the build exits with a specific error message naming the missing key.

6. **Missing source files produce clear errors.** If the paths exist in config but the files do not exist on disk, the build exits with a specific error message showing the resolved path.

7. **No regression.** The existing build flow (`index.html`, `browse.html`, `style.css`, static file copying) is unchanged when `build.attribution` is absent or `false`.

8. **Markdown library is a declared dependency.** The chosen library is added to `pyproject.toml` and installs cleanly via `poetry install`.

## Open questions

1. **Which markdown library?** — The implementer should evaluate `mistune` (lightest), `markdown` (most mature), and `markdown-it-py` (spec-compliant) and pick the one that best fits the project. The spec does not prescribe a specific library.
2. **Should `note.html` and `prompt.html` be listed in the sidebar navigation?** — Not specified here. The footer note already links to them. Adding them to the nav risks cluttering the category-driven sidebar. The implementer may add them to `config.navigation.menu_links` (in site.config.json) if the LLM is instructed to do so; no template-level auto-listing is needed.
3. **Should the source pages include a back-link (e.g., "← Back to Home")?** — `base.html` already shows a "← Home" link in the header on `browse.html`. The `source.html` template can follow the same pattern (`request.path` check) or always show the home link. Left to the implementer's judgment.
4. **Should the footer attribution use a `<section>` or `<p>` element?** — A `<p>` inside the existing `<div class="footer-content">` container is sufficient. No additional semantic landmarking is needed.
5. **What if `ingest.note` and `ingest.site_prompt` point to the same file?** — They are rendered as two separate pages with different titles. No deduplication is needed; the author chose to use the same file for both.

## Related specs

### Depends upon
- [specs/refactors/path_configurability.md](../refactors/path_configurability.md) — the config system (`config.yaml`, `load_resourcery_config()`, `${VAR}` resolution) that this feature relies on to discover `ingest.note` and `ingest.site_prompt`.

### Extends
- None — this is a new, self-contained feature.

### See also
- [specs/feats/data_ingestion.md](data_ingestion.md) — defines the `ingest.note` and `ingest.site_prompt` concepts (as CLI args). This spec promotes them to config keys so the build pipeline can reference them.
- [specs/feats/multi_step_ingestion.md](multi_step_ingestion.md) — the multi-step ingestion pipeline that also reads `ingest.note` and `ingest.site_prompt` from config.
- [specs/feats/per_stage_configuration.md](per_stage_configuration.md) — the `ingest.stages:` subsection lives alongside the new commented-out `note`/`site_prompt` entries.

## Technical details

- `base_context` in `build_site()` gains a single new key: `"attribution_enabled"` (boolean). This is used by `base.html` for the conditional footer note, and passed through to `source.html` for consistency (all pages get the footer).
- The markdown-to-HTML conversion should happen **before** template rendering, not inside the template. Templates receive pre-rendered HTML as a string.
- `source.html` must not re-escape the `source_content` variable — use `{{ source_content | safe }}` in the template to render the HTML directly.
- The `ingest.note` and `ingest.site_prompt` values are resolved by the config system to absolute `Path` objects (since they look like file paths and are not in `_NON_PATH_KEYS`). The build function reads them directly via `path.read_text(encoding="utf-8")`.
- No changes to `_NON_PATH_KEYS` are needed — `attribution` is a boolean and never reaches `_resolve_paths` as a string, and `note`/`site_prompt` are legitimate file paths that *should* be converted to `Path` objects.
- The footer attribution is a single `<p>` element. The CSS for the attribution line should be implemented in `style.css` (the themed CSS template) so it picks up the site's design token colors. A dedicated CSS class (e.g., `.attribution-note`) allows the footer to render without attribution when the flag is off — the `<p>` element simply doesn't appear in the HTML.
- The `style.css` template already renders via Jinja2 with access to `theme_tokens`. The attribution styling can reference theme colors (e.g., `color: {{ theme_tokens.surface_fg_muted }}`) for consistency with the site's visual design.
- If an existing `note.html` or `prompt.html` is in the static directory (which would be copied verbatim by the build step's `shutil.copytree`), the generated pages will be written to output and overwrite any stale copies. The order of operations in `build_site()` must ensure source page generation happens **after** static file copying, so the generated pages take precedence.

---

> **Note on file paths:** This spec follows the `src/` layout convention established by
> [`refactors/src_layout_package.md`](../refactors/src_layout_package.md). All source
> references to `build.py`, `config.py`, and `site.py` are under `src/resourcery_ssg/`.
