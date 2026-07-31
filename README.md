# Resourcery.ssg

A static link collection site generator powered by Python, Jinja2, and vanilla JavaScript. Comes with a structured JSON schema and a ready-made LLM prompt to extract and enrich your existing links — wherever you've stored them — into the required format. From there, one build command produces a fully navigable, responsive site with a hierarchical category sidebar, tag-based discovery, full-text search, card modals, and dark mode. No platform, no auth, no runtime dependencies.

## Who Is This For

People who:
- Have accumulated links, resources, or references in notes or bookmarks and want to give them a proper home
- Need to share a curated collection with a group without setting up a platform, managing accounts, or writing any frontend code
- Want something more structured than a text file but quicker to build than a purpose-built web app
- Appreciate that the output is just static HTML/CSS/JS — hostable anywhere, works offline, no dependencies at runtime

## Use Cases

**Education & Research**
- Sharing a course bibliography or reading list with students
- Curating sources around a research topic for a team or collaborator

**Community & Culture**
- Introducing friends to a fandom, genre, or subculture through a guided collection
- Building a living resource hub for a community (tools, references, further reading)

**Professional**
- Onboarding resources for a new team member
- A public-facing list of tools, services, or references relevant to your domain

**Personal**
- Turning years of saved links into something navigable and shareable
- A digital garden of references without the overhead of a CMS


## Architecture

| Component | Technology | Notes |
|-----------|------------|-------|
| **Templating** | Jinja2 | HTML and CSS are templated from config |
| **Data** | JSON | site.config.json + links.json + design.json |
| **Validation** | JSON Schema | Enforced via jsonschema library |
| **Design Tokens** | Python | design.json compiled to CSS custom properties at build time (incl. dark-mode tokens) |
| **Styling** | CSS Variables | Theming via CSS custom properties |
| **Interactivity** | Vanilla JS (ESM) | No framework; Nanostores atoms for state, URL hash as source of truth |
| **Data Ingestion** | LLM agent | opencode-driven CLI turns markdown notes into validated JSON |
| **Configuration** | config.yaml | All paths and per-command settings, overridable via CLI/env |
| **Build** | Python CLI | `site` coordinator (src/resourcery_ssg/site.py) dispatches build, validate, acquire-*, ingest |

## Prerequisites

- **Python 3.10+** and [Poetry](https://python-poetry.org/)
- **opencode CLI** — required to generate your site's content (`links.json`, `site.config.json`, `design.json`) from markdown notes. Install it and set it up with an LLM provider/API key. Only skippable if you already have the three JSON files.
- **Your content** — either raw markdown notes (to be converted into the site) or the three JSON files that define it: `links.json` (your links), `site.config.json` (site settings), `design.json` (design).

## Quick Start

All commands go through the unified `site` CLI (`poetry run site <subcommand>`). It works out of the box with sensible defaults — override paths and settings via CLI flags (e.g. `--data`, `--output`), environment variables, or your own config file (see [Configuration](#configuration) below).

### The Easy Way: One Command

  `poetry install`

  `poetry run site all --note ./my-notes.md --site-prompt ./my-site-prompt.md`

`site all` runs the full pipeline — ingest → validate → acquire-fonts → acquire-images → build — and stops on the first failure. The `--note`/`--site-prompt` flags feed the ingestion step (both are required when ingestion is active).

**Already have your content (or no opencode)?** Create your own config file with ingestion disabled and run with it — see below.

### Configuration

Create a config file with just the settings you want to change, then pass it with `--config`:

```yaml
# my-site.yaml
vars:
  DATA_DIR: ./my-data          # where your content lives (links.json, site.config.json, design.json)
  OUTPUT_DIR: ./my-site        # where the built site goes

ingest:
  model: null                  # disables the ingestion step (no opencode needed)
  # note: ./my-notes.md        # set these to enable ingestion
  # site_prompt: ./my-site-prompt.md
```

  `poetry run site --config my-site.yaml all`

CLI flags and environment variables always win over the config file.

### Step by Step (for more control)

#### 1. Generate Your Content from Notes (Optional)

  `poetry run site ingest --note ./my-notes.md --site-prompt ./my-site-prompt.md --model gpt-4o`

Turns a raw markdown note into `links.json`, `site.config.json`, and `design.json` via an LLM agent (requires the opencode CLI). Both `--note` and `--site-prompt` are required. Skip this step only if you already have the three JSON files — or generate them with any LLM interface via the manual prompt route below.

#### 2. Validate Data (Optional but Recommended)

  `poetry run site validate`

#### 3. Acquire Assets

  `poetry run site acquire-fonts`

  `poetry run site acquire-js`

  `poetry run site acquire-images`

#### 4. Build the Site

  `poetry run site build`

#### 5. Serve Locally

  `cd output`

  `poetry run python -m http.server 8000`

Open `http://localhost:8000` in your browser.

The individual scripts (`poetry run build`, `poetry run validate`, ...) still work for ad-hoc use.

#### Running the Tests

  `poetry run pytest`            # Python suite (unit + integration)

  `npm install && npm test`      # JavaScript suite (Vitest + jsdom)

Python `network` and `e2e` markers are skipped by default; opt in with `poetry run pytest -m network`.


## How to practically use this project to create a static link aggregator web site to suite your data

**Option A — agentic (recommended):** run `poetry run site ingest --note <your-note.md> --site-prompt <your-site-prompt.md> --model <model>` (see [src/resourcery_ssg/config.yaml](src/resourcery_ssg/config.yaml) for prompt paths, multi-step mode, and retries). Requires the **opencode CLI** set up with an LLM provider — the tool orchestrates it to produce `links.json`, `site.config.json`, and `design.json`, validated against the schemas.

**Option B — manual:** attach your input files to your favorite LLM interface alongside the schemas and use the matching prompt from **[prompts/](prompts/)**:

| Prompt | Purpose |
|--------|---------|
| [prompts/data-ingestion.md](prompts/data-ingestion.md) | One-shot ingestion of a full note (all files) |
| [prompts/ingest-site-config.md](prompts/ingest-site-config.md) | Site config + design generation |
| [prompts/ingest-links.md](prompts/ingest-links.md) | Links extraction/enrichment |
| [prompts/ingest-design.md](prompts/ingest-design.md) | Design token generation |

Schemas: `links.schema.json`, `site.config.schema.json`, `design.schema.json` (all in [schemas/](schemas/)).

## Acknowledgments
This project was vibe-coded with the assistance of **Alibaba Qwen (v3.5)** and **Claude Sonnet (v4.6)**

Built with ☕, 🐍, and ✨