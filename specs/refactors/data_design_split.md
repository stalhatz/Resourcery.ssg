---
size: big
modified_date: 2026-05-11
implemented_git_tag: d405920
---

# Split Data from Design in JSON Schema

We want to split data from design in order to enable a (at least) two step site design/configuration. Single shoting is difficult even for bigger models and, eventually, we want to target small, local models.

## Current state 
Although there is some distinction, introduced by splitting input into files following two JSON Schemas [links.schema.json](../schemas/links.schema.json) and [site.config.schema.json](../schemas/site.config.schema.json) we can only claim that links.schema.json is purely a data file. site.config.schema.json contains both data as well as design variables. 

## Target state

Split the configuration into three files to minimize context per LLM call and simplify variable inference:

| File | Purpose | Schema |
|------|---------|--------|
| `links.json` | Pure link data (URLs, titles, descriptions, categories, tags) | Existing links.schema.json (minor updates) |
| `site.config.json` | Site identity, navigation, content copy, features | New: stripped of design fields |
| `design.json` | Visual design only (colors, typography, effects, layout) | New schema |

## Design decisions

- **Separate LLM calls per step** — each pipeline step is an independent call
- **Categories are data** — derived from content, not a design choice
- **Persist intermediate outputs** — each step writes to `workspace/` directory (gitignored), enabling resume/debug
- **Full automation** — LLM runs all steps, human reviews at the end
- **Retry with feedback** — failed steps retry up to 3 times with validation error context
- **No design presets** — design is fully generated from content analysis
- **OpenAI-compatible API** — supports any OpenAI-compatible endpoint (local models via Ollama, LM Studio, etc.)
- **Minimal context flow** — each step receives only the previous step's output
- **Validate after each step** — schema validation before proceeding
- **No backwards compatibility** — existing site.config.json will be manually split
- **Merge at build time** — build.py loads all 3 files and merges into single context dict
- **Image acquisition stays separate** — remains a post-pipeline step (current approach)
- **Multiple input formats** — plain text, CSV, bookmarks HTML, markdown
- **Descriptive text with target group** — user must provide a description of the site's purpose and target audience. This context influences descriptions, taxonomy, copy, and design. The orchestrator extracts it from the input file (format-dependent), or from a CLI argument `--description`, or the LLM infers it from the content if neither is found.
- **Blocking API calls** — no streaming, simpler implementation
- **Interactive mode** — after pipeline completes, user can propose changes and the LLM will iteratively refine outputs

## User input

The user provides:
- **Link content** — URLs, titles, or any raw content that can be resolved to links
- **Descriptive text** — must describe the site's purpose and at minimum specify the **target audience** (e.g., "high-school students", "grad researchers in AI", "general public interested in cooking"). This shapes how every step interprets and presents the content.

Since there is no fixed input format, the descriptive text can be embedded in the input file (as a preamble, heading section, or first paragraph) or provided via the `--description` CLI argument. If neither is present, the LLM in Step 1 is tasked with inferring the likely target group from the links themselves, though the result will be weaker.

## Proposed pipeline

```
Step 1: Extract
  Input:  Raw input file (text, CSV, bookmarks, markdown) + optional --description CLI arg
  Output: workspace/01_extract.json -> {
    site_descriptor: { purpose, target_group, notes },
    links: [{ url, title? }]
  }
  Context passed forward: site_descriptor + links with URLs
  Purpose: Extract URLs/titles from the input file. Also extract or infer the
           site's descriptive text and target audience from the input or CLI arg.

Step 2: Enrich
  Input:  workspace/01_extract.json
  Output: workspace/02_enrich.json -> { links: [{ url, title, summary, description }] }
  Context passed forward: site_descriptor + enriched links
  Purpose: Fetch/generate descriptions and summaries for each link. Tone and
           reading level should match the target group from site_descriptor.

Step 3: Taxonomy (NEW - top-down)
  Input:  workspace/02_enrich.json
  Output: workspace/03_taxonomy.json -> {
    tags: ["accessibility", "api", "authentication", ...],
    categories: [{ id, label, icon, children: [{ id, label, icon }] }]
  }
  Context passed forward: site_descriptor + tag vocabulary + category hierarchy
  Purpose: Define the tag vocabulary (horizontal, overlapping descriptors)
           and category hierarchy (two-level, balanced leaf distribution)
           based on domain, content themes, and the target group's vocabulary.
           Top-down to ensure quality, consistency, and balanced navigation.

Step 4: Classify
  Input:  workspace/02_enrich.json + workspace/03_taxonomy.json
  Output: workspace/04_classify.json -> { links: [..., category, tags] }
  Context passed forward: site_descriptor + classified links
  Purpose: Assign the pre-defined tags and categories to each link.
           Bottom-up matching against the established taxonomy.

Step 5: Identity
  Input:  workspace/04_classify.json
  Output: workspace/05_identity.json -> { site_info, content, navigation.menu_links, features }
  Context passed forward: site_descriptor + site.config.json
  Purpose: Generate site name, description, intro text, footer, and feature flags
           with language and tone appropriate for the target group.

Step 6: Design
  Input:  workspace/04_classify.json + workspace/05_identity.json
  Output: workspace/06_design.json -> { theme: { colors, typography, layout, effects } }
  Context passed forward: design.json
  Purpose: Choose colors, typography, layout, and effects that appeal to and
           are accessible for the target group.

Step 7: Validate & Build
  Input:  links.json + site.config.json + design.json (from workspace/)
  Output: Validated files -> static site (existing build.py + image_acquirer.py)
```

## File schemas

### links.json (existing, minor updates)

```json
{
  "site_meta": { "title", "version", "last_updated" },
  "links": [
    {
      "id", "title", "summary", "description", "url",
      "category", "tags",
      "image" (optional), "featured" (optional),
      "created_at", "updated_at", "status", "pricing", "language"
    }
  ]
}
```

### site.config.json (stripped of design)

```json
{
  "site_info": { "name", "url", "logo", "favicon", "description" },
  "navigation": {
    "categories": [{ "id", "label", "icon", "children": [{ "id", "label", "icon" }] }],
    "menu_links": [{ "label", "url", "open_new_tab" }]
  },
  "content": {
    "landing": { "intro_title", "intro_text", "featured_count" },
    "header": { "title", "subtitle" },
    "footer": { "copyright", "text", "links": [{ "label", "url" }] },
    "placeholders": { "search_bar", "default_image_alt" }
  },
  "features": {
    "search": { "enabled" },
    "dark_mode": { "enabled" }
  }
}
```

### design.json (new schema)

```json
{
  "theme": {
    "colors": {
      "primary", "secondary", "background", "surface",
      "text", "text_muted", "accent", "error", "success",
      "dark": { all above optional }
    },
    "typography": {
      "font_family", "font_size_base", "heading_font", "heading_size_scale"
    },
    "layout": {
      "sidebar_width", "max_width"
    },
    "effects": {
      "card_style", "shadow_intensity", "border_radius",
      "border_treatment", "hover_effect", "heading_style"
    }
  }
}
```

## Orchestrator design

### New file: `orchestrate.py`

A Python script that:

1. Reads input file (auto-detects format: txt, csv, html, md) and CLI `--description` argument
2. Extracts URLs/titles from input; also extracts or notes the descriptive text / target group
3. For each step in the pipeline:
   a. Loads previous step's output from `workspace/`
   b. Constructs prompt with JSON schema for expected output, including the `site_descriptor` when relevant
   c. Calls LLM via OpenAI-compatible API (blocking call)
   d. Validates output against JSON schema
   e. On validation failure: retries up to 3 times, passing validation errors back to LLM
   f. On success: writes output to `workspace/` directory
4. Writes final outputs to `data/` directory (links.json, site.config.json, design.json)
5. Runs existing `validate.py` for cross-file validation
6. Runs existing `build.py` to generate the site
7. Runs existing `image_acquirer.py` to fetch images
8. Enters interactive mode: user can propose changes, LLM refines outputs, rebuilds

### Configuration

Environment variables:

```
LLM_API_BASE=https://api.openai.com/v1  (or http://localhost:11434/v1 for Ollama)
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini  (or llama3.2, etc.)
MAX_RETRIES=3
INPUT_FILE=path/to/input.txt
```

CLI arguments:

```
--description "A collection of AI theory links for grad students"
  Overrides or provides the descriptive text (purpose + target group).
  If the input file already contains a descriptive preamble, this
  argument takes precedence.
```

### Prompt strategy

Each step's prompt includes:
- Role definition (what the LLM is doing)
- Task description
- Input data (previous step's output)
- JSON schema for expected output
- Constraints and guidelines (from schema descriptions)

### Interactive mode

After the pipeline completes and the site is built:
- User reviews the generated site
- User can propose changes (e.g., "make the primary color more blue", "rename category X to Y", "rewrite the intro text")
- LLM applies changes to the relevant file(s)
- Site rebuilds
- Loop continues until user is satisfied

## Validation

- Each step validates its output against its JSON schema before proceeding
- Step 7 runs full cross-validation (existing validate.py extended for 3 files)
- Validation errors are fed back to LLM on retry

## Build pipeline changes

- `build.py` loads all 3 files and merges into a single context dict for Jinja2 templates
- Templates remain unchanged (receive same context structure)
- `validate.py` extended to validate cross-file references across 3 files

## Migration

No backwards compatibility required. Existing `data/site.config.json` will be manually split into `data/site.config.json` + `data/design.json` as part of implementation.

## New schemas to create

- `schemas/site.config.schema.json` — updated, design fields removed
- `schemas/design.schema.json` — new, contains all theme/design fields

## Workspace directory

- `workspace/` — stores intermediate pipeline outputs (01_extract.json through 06_design.json)
- Added to `.gitignore`
- Cleaned between runs unless `--resume` flag is used
