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
| **Build** | Python Script | build.py renders and copies assets |

## Quick Start

### 1. Install Dependencies

  `poetry install`

### 2. Validate Data (Optional but Recommended)

  `poetry run python validate.py`

### 3. Acquire Images

  `poetry run python image_acquirer.py`

### 4. Build the Site

  `poetry run python build.py`

### 5. Serve Locally

  `cd output`

  `poetry run python -m http.server 8000`

Open `http://localhost:8000` in your browser.


## How to practically use this project to create a static link aggregator web site to suite your data

Attach your input files to your favorite LLM interface alongside `site.config.schema.json` and `links.schema.json` and add this prompt : 


``` markdown
# Role: Static Site Data Generator

You are an expert data engineer and UI designer. Your task is to analyze the attached files (which contain raw links, lists of resources, or research data) and generate two valid JSON files (`site.config.json` and `links.json`) for a static link aggregation website.

You must strictly adhere to the provided JSON Schemas (`site.config.schema.json` and `links.schema.json`). Do not invent fields that do not exist in the schema.

## 🎯 Your Tasks

### 1. Analyze Input Data
- Extract all valid URLs, titles, and descriptions from the attachments.
- Identify natural categories based on the content.
- Extract or infer tags for each resource.
- When descriptions are unavailable try to create short and long descriptions based on context (for example in a list of elements titled "Mobile phones under 200$" incorporate context by axing your descriptions around price to performance ratio)
- When descriptions are available use a short description to infer a long one and inversely
- Determine if an image URL is available; if not, mark as null (the site has fallbacks).
- If a corresponding URL is not present but you judge by the context that this element must be classified, try to come up with a URL yourself (for example in a list of OSs if an entry is "Opensuse Tumbleweed" you can infer the URL : https://get.opensuse.org/tumbleweed/)

### 2. Design the Site Identity (`site.config.json`)
Based on the **tone and subject matter** of the attached content, make design decisions:
- **Colors:** If the content is academic/corporate, use professional blues/grays. If creative, use vibrant colors.
- **Typography:** Choose fonts that match the content style.
- **Navigation:** Structure the `categories` hierarchy logically based on the extracted data.
- **Content:** Write compelling header titles, subtitles, and footer text that match the site's purpose.
- **Effects** control the visual personality of the site (card style, shadows, borders, hover behaviour, typography) — choose values that match the domain and tone of the content.

### 3. Populate Links (`links.json`)
- Map every extracted resource to a link object.
- Assign the most appropriate `category` ID (must match an ID defined in `site.config.json`).
- Write a `summary` (max 150 chars) and a `description` (longer text) for each.
- Set `status` to "active" by default.
- Generate a unique, URL-safe `id` for each link (e.g., `my-resource-title`).

## 📐 Constraints & Rules

1. **Schema Compliance:** The output MUST validate against the given JSON schemas.
2. **Category Consistency:** Every `link.category` must exist in `site.config.navigation.categories`.
3. **ID Safety:** All `id` fields must be lowercase alphanumeric with hyphens (e.g., `computer-vision`).
4. **Color Format:** All colors must be 6-digit hex codes (e.g., `#2563eb`).
5. **No Hallucinations:** Do not invent URLs. If a URL is missing, do not create a link entry.

## 📤 Output Format

Provide exactly two JSON code blocks. Do not add markdown formatting inside the JSON.
```

## Acknowledgments
This project was vibe-coded with the assistance of **Alibaba Qwen (v3.5)** and **Claude Sonnet (v4.6)**

Built with ☕, 🐍, and ✨