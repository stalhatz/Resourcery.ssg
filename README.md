# Static Link Aggregation Site

A modern, static link aggregation website built with Python, Jinja2, and vanilla JavaScript. Features a responsive metro-style sidebar, sentence-style filtering, compact card layout with modals, and dark mode.

## Architecture

| Component | Technology | Notes |
|-----------|------------|-------|
| **Templating** | Jinja2 | HTML and CSS are templated from config |
| **Data** | JSON | site.config.json + links.json |
| **Validation** | JSON Schema | Enforced via jsonschema library |
| **Styling** | CSS Variables | Theming via CSS custom properties |
| **Interactivity** | Vanilla JS | No framework (FilterManager, ModalManager, etc.) |
| **Build** | Python Script | build.py renders and copies assets |

## Project Structure

```
project/
├── data/
│   ├── site.config.json       # Site configuration (theme, nav, content)
│   └── links.json             # Link entries (validated against schema)
├── schemas/
│   ├── site.config.schema.json
│   └── links.schema.json
├── templates/
│   ├── base.html              # Base layout + sidebar + header
│   ├── index.html             # Main content (cards + modal)
│   └── style.css              # Templated CSS (colors/fonts from config)
├── static/
│   ├── js/
│   │   └── main.js            # All client-side logic
│   └── images/
│       ├── placeholders/      # Category fallback images
│       └── acquired/          # Images fetched via image_acquirer.py
├── build.py                   # Main build script
├── validate.py                # JSON schema validation
├── image_acquirer.py          # Optional: fetch images from URLs
├── pyproject.toml             # Poetry dependencies
└── output/                    # Generated static site (gitignored)
```

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


### Scenario A: "I have a folder of bookmarks"
1. Export bookmarks to HTML or Markdown.
2. Attach the file.
3. **Add this note to the prompt:**
   > "These are my browser bookmarks. Please group them into logical categories and use a 'Developer Dashboard' theme (dark mode, monospace fonts)."

### Scenario B: "I have a research paper PDF"
1. Attach the PDF.
2. **Add this note:**
   > "This is a research paper. Extract all URLs cited in the bibliography as 'Papers'. Create a site theme suitable for an academic repository (serif fonts, conservative colors)."

### Scenario C: "I have a screenshot of a website list"
1. Attach the screenshot.
2. **Add this note:**
   > "Extract the links visible in this screenshot. Use OCR if necessary. Categorize them based on the visible headings."

### Scenario D: "I have a messy Word doc"
1. Attach the `.docx`.
2. **Add this note:**
   > "This document contains a curated list of resources. Clean up the formatting, extract the links, and design a 'Modern Tech Blog' theme."

---

## Context for AI Assistants

If continuing this project in a new chat session, provide this README plus the specific file(s) being modified. Key modules in main.js:

- CategoryHierarchy: Maps parent/child category relationships
- FilterManager: Handles sidebar clicks, dropdowns, filtering logic
- ModalManager: Opens/closes detail modals
- SidebarManager: Handles mobile toggle + collapsible categories
- filterCards(): Core filtering function (search + category)
- handleHashChange(): Syncs URL hash with filter state

## Acknowledgments
This project was vibe-coded with the assistance of **Alibaba Qwen (v3.5)**.

Learn more about Qwen: https://github.com/QwenLM/Qwen

Built with ☕, 🐍, and ✨