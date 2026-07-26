#!/usr/bin/env python3
"""
Build script for static link aggregation site.
Renders Jinja2 templates with JSON data.
"""

import json
import random
import os
import shutil
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from resourcery_ssg.theme_constants import get_heading_weight, get_heading_letter_spacing

# Directories
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"
OUTPUT_DIR = ROOT_DIR / "output"


def load_json(path):
    """Load and parse a JSON file from disk.

    path: filesystem path to the JSON file.

    Returns: parsed dictionary contents.

    FileNotFoundError: the file does not exist at path.
    json.JSONDecodeError: the file contents are not valid JSON.
    """

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_data(config, links):
    """Assert that both data dicts contain all required top-level keys.

    config: site configuration dictionary.
    links: links data dictionary.

    Returns: None.

    ValueError: a required key is missing from either dictionary.
    """

    required_config = ["site_info", "navigation", "content"]
    required_links = ["links"]

    for key in required_config:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")

    for key in required_links:
        if key not in links:
            raise ValueError(f"Missing required links key: {key}")


# ==================== CUSTOM JINJA2 FILTERS ====================


def shuffle_filter(value):
    """Return a shuffled copy of a sequence.

    value: any sequence (list, tuple, etc.) to shuffle.

    Returns: new list with elements in random order.
    """

    value_list = list(value)
    random.shuffle(value_list)
    return value_list


# ==================== PRE-COMPUTATION HELPERS ====================


def build_category_map(config):
    """Pre-compute the parent-to-children-and-self lookup map.

    Produces a dict where parent category IDs map to a list of their
    children plus themselves, and leaf categories map to themselves.
    This is serialized to the browser so it never re-parses config at runtime.

    config: site configuration dictionary containing navigation.categories.

    Returns: dict mapping category IDs to lists of category IDs.

    Example:
        {"development": ["frontend", "backend", "development"],
         "frontend":    ["frontend"],
         "backend":     ["backend"]}
    """

    category_map = {}
    for cat in config.get("navigation", {}).get("categories", []):
        children_ids = [c["id"] for c in cat.get("children", [])]
        category_map[cat["id"]] = children_ids + [cat["id"]]
        for child in cat.get("children", []):
            category_map[child["id"]] = [child["id"]]
    return category_map


def build_all_tags(links_data):
    """Deduplicate and sort all tags across every link entry.

    Preserves original casing for display. Lowercased keys are used
    for deduplication so that "Python" and "python" collapse to one entry.

    links_data: dictionary with a "links" key containing link records.

    Returns: sorted list of unique tag strings.

    Example:
        ["API", "design", "open-source", "python"]
    """

    tag_set = {}
    for link in links_data.get("links", []):
        for tag in link.get("tags", []):
            if tag and tag.strip():
                tag_set[tag.strip().lower()] = tag.strip()
    return sorted(tag_set.values(), key=lambda t: t.lower())


# ==================== BUILD ====================


def build_site():
    """Render all templates and copy static assets to the output directory.

    Loads data from site.config.json and links.json, pre-computes category
    and tag lookup structures, renders Jinja2 templates (index.html,
    browse.html, style.css), and copies static files (images, JS, fonts,
    fonts.css) into output/.

    Returns: None.

    Prints progress and warnings to stdout.

    SystemExit: if fonts.css is missing (run font_acquirer.py first).
    """

    print("🔨 Building static site...")

    # Clean output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # Load data
    config = load_json(DATA_DIR / "site.config.json")
    links_data = load_json(DATA_DIR / "links.json")
    design = load_json(DATA_DIR / "design.json")
    config["theme"] = design["theme"]

    # Resolve heading style values from theme_constants (single source of truth)
    heading_style = (
        config.get("theme", {}).get("effects", {}).get("heading_style", "natural")
    )

    # Guard: fonts must be acquired before building
    fonts_css_path = STATIC_DIR / "css" / "fonts.css"
    if not fonts_css_path.exists():
        print("⚠️  static/css/fonts.css not found — run font_acquirer.py first")
        sys.exit(1)

    # Pre-compute derived data
    category_map = build_category_map(config)
    all_tags = build_all_tags(links_data)

    # Setup Jinja2
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)

    # Register custom filters
    env.filters["shuffle"] = shuffle_filter

    # Shared base context — every template gets these
    base_context = {
        "config": config,
        "links": links_data,
        "category_map": category_map,
        "all_tags": all_tags,
    }

    # ==================== RENDER TEMPLATES ====================

    # Render index.html (landing page)
    template = env.get_template("index.html")
    output = template.render(**base_context)
    with open(OUTPUT_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(output)
    print("✓ index.html rendered (landing page)")

    # Render browse.html (full browse)
    template = env.get_template("browse.html")
    output = template.render(**base_context)
    with open(OUTPUT_DIR / "browse.html", "w", encoding="utf-8") as f:
        f.write(output)
    print("✓ browse.html rendered (full browse)")

    # Render style.css (THEMED CSS - CRITICAL!)
    template = env.get_template("style.css")
    output = template.render(**base_context)

    # Create css directory in output
    css_dir = OUTPUT_DIR / "static" / "css"
    css_dir.mkdir(parents=True, exist_ok=True)

    with open(css_dir / "style.css", "w", encoding="utf-8") as f:
        f.write(output)
    print("✓ style.css rendered (themed)")

    # ==================== COPY STATIC FILES ====================

    static_output = OUTPUT_DIR / "static"

    # Copy images
    images_src = STATIC_DIR / "images"
    if images_src.exists():
        shutil.copytree(images_src, static_output / "images")
        print("✓ Images copied")

    # Copy JS
    js_src = STATIC_DIR / "js"
    if js_src.exists():
        shutil.copytree(js_src, static_output / "js")
        print("✓ JavaScript copied")

    # Copy fonts
    fonts_src = STATIC_DIR / "fonts"
    if fonts_src.exists():
        shutil.copytree(fonts_src, static_output / "fonts")
        print("✓ Fonts copied")

    # Copy fonts.css
    css_out = static_output / "css"
    css_out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fonts_css_path, css_out / "fonts.css")
    print("✓ fonts.css copied")

    print("\n✅ Build complete!")
    print(f"\n📁 Output directory: {OUTPUT_DIR.absolute()}")
    print("\n🌐 To view the site:")
    print(f"   cd {OUTPUT_DIR} && python -m http.server 8000")
    print("   Landing page:  http://localhost:8000/")
    print("   Browse page:   http://localhost:8000/browse.html")


if __name__ == "__main__":
    build_site()
