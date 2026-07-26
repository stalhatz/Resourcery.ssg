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
| **Data** | JSON | site.config.json + links.json |
| **Validation** | JSON Schema | Enforced via jsonschema library |
| **Styling** | CSS Variables | Theming via CSS custom properties |
| **Interactivity** | Vanilla JS | No framework |
| **Build** | Python Script | src/resourcery_ssg/build.py renders and copies assets |

## Quick Start

### 1. Install Dependencies

  `poetry install`

### 2. Validate Data (Optional but Recommended)

  `poetry run validate`

### 3. Acquire Images

  `poetry run acquire-images`

### 4. Build the Site

  `poetry run build`

### 5. Serve Locally

  `cd output`

  `poetry run python -m http.server 8000`

Open `http://localhost:8000` in your browser.


## How to practically use this project to create a static link aggregator web site to suite your data

Attach your input files to your favorite LLM interface alongside `site.config.schema.json` and `links.schema.json` and use the prompt at **[prompts/data-ingestion.md](prompts/data-ingestion.md)**.

## Acknowledgments
This project was vibe-coded with the assistance of **Alibaba Qwen (v3.5)** and **Claude Sonnet (v4.6)**

Built with ☕, 🐍, and ✨