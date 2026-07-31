#!/usr/bin/env python3
"""
Build script for static link aggregation site.
Renders Jinja2 templates with JSON data.
"""

import mistune
import random
import os
import shutil
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from resourcery_ssg.io_utils import load_json
from resourcery_ssg.theme_constants import (
    get_heading_weight,
    get_heading_letter_spacing,
    resolve_heading,
)
from resourcery_ssg.token_gen import generate_theme_tokens


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


def build_site(*, data_dir, templates_dir, static_dir, output_dir,
               attribution=None, ingest_note=None, ingest_site_prompt=None):
    """Render all templates and copy static assets to the output directory.

    Loads data from site.config.json and links.json, pre-computes category
    and tag lookup structures, renders Jinja2 templates (index.html,
    browse.html, style.css), and copies static files (images, JS, fonts,
    fonts.css) into output/.

    Args:
        data_dir: Directory containing site.config.json, links.json, design.json.
        templates_dir: Directory containing Jinja2 templates.
        static_dir: Directory containing static assets (images, JS, fonts).
        output_dir: Directory to write the generated site into.

    Returns: None.

    Prints progress and warnings to stdout.

    SystemExit: if fonts.css is missing (run font_acquirer.py first).
    """

    print("🔨 Building static site...")

    # Clean output directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Load data
    config = load_json(data_dir / "site.config.json")
    links_data = load_json(data_dir / "links.json")
    design = load_json(data_dir / "design.json")
    config["theme"] = design["theme"]

    # Generate design tokens at build time
    theme_tokens = generate_theme_tokens(config["theme"])

    # Resolve heading style values with typography overrides
    heading_style = (
        config.get("theme", {}).get("effects", {}).get("heading_style", "natural")
    )
    typography = config.get("theme", {}).get("typography", {})
    heading = resolve_heading(typography, heading_style)

    # Guard: fonts must be acquired before building
    fonts_css_path = static_dir / "css" / "fonts.css"
    if not fonts_css_path.exists():
        print("⚠️  static/css/fonts.css not found — run font_acquirer.py first")
        sys.exit(1)

    # ==================== ATTRIBUTION ====================

    # Resolve attribution flag (absent → None → False)
    attribution_enabled = attribution if attribution else False

    note_html = None
    prompt_html = None

    if attribution_enabled:
        # Validate ingest.note is set
        if not ingest_note:
            print("Error: build.attribution is enabled but ingest.note is not set in config.")
            print("Add 'note' under the 'ingest' section in your config.yaml.")
            sys.exit(1)

        # Validate ingest.site_prompt is set
        if not ingest_site_prompt:
            print("Error: build.attribution is enabled but ingest.site_prompt is not set in config.")
            print("Add 'site_prompt' under the 'ingest' section in your config.yaml.")
            sys.exit(1)

        # Validate files exist on disk
        note_path = Path(ingest_note)
        prompt_path = Path(ingest_site_prompt)

        if not note_path.exists():
            print(f"Error: Cannot read note file: {note_path}")
            sys.exit(1)

        if not prompt_path.exists():
            print(f"Error: Cannot read site prompt file: {prompt_path}")
            sys.exit(1)

        # Read markdown files as UTF-8
        try:
            note_md = note_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"Error: Cannot decode {note_path.name} as UTF-8")
            sys.exit(1)

        try:
            prompt_md = prompt_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"Error: Cannot decode {prompt_path.name} as UTF-8")
            sys.exit(1)

        # Convert markdown to HTML using mistune with GFM plugin
        markdown = mistune.create_markdown(
            escape=False,
            plugins=["strikethrough", "footnotes", "table", "speedup"]
        )
        note_html = markdown(note_md)
        prompt_html = markdown(prompt_md)

    # Pre-compute derived data
    category_map = build_category_map(config)
    all_tags = build_all_tags(links_data)

    # Setup Jinja2
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)

    # Register custom filters
    env.filters["shuffle"] = shuffle_filter

    # Shared base context — every template gets these
    base_context = {
        "config": config,
        "links": links_data,
        "category_map": category_map,
        "all_tags": all_tags,
        "theme_tokens": theme_tokens,
        "heading_weight": heading["heading_weight"],
        "heading_letter_spacing": heading["heading_letter_spacing"],
        "attribution_enabled": attribution_enabled,
    }

    # ==================== RENDER TEMPLATES ====================

    # Render index.html (landing page)
    template = env.get_template("index.html")
    output = template.render(**base_context)
    with open(output_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(output)
    print("✓ index.html rendered (landing page)")

    # Render browse.html (full browse)
    template = env.get_template("browse.html")
    output = template.render(**base_context)
    with open(output_dir / "browse.html", "w", encoding="utf-8") as f:
        f.write(output)
    print("✓ browse.html rendered (full browse)")

    # Render style.css (THEMED CSS - CRITICAL!)
    template = env.get_template("style.css")
    output = template.render(**base_context)

    # Create css directory in output
    css_dir_out = output_dir / "static" / "css"
    css_dir_out.mkdir(parents=True, exist_ok=True)

    with open(css_dir_out / "style.css", "w", encoding="utf-8") as f:
        f.write(output)
    print("✓ style.css rendered (themed)")

    # ==================== COPY STATIC FILES ====================

    static_output = output_dir / "static"

    # Copy images
    images_src = static_dir / "images"
    if images_src.exists():
        shutil.copytree(images_src, static_output / "images")
        print("✓ Images copied")

    # Copy JS
    js_src = static_dir / "js"
    if js_src.exists():
        shutil.copytree(js_src, static_output / "js")
        print("✓ JavaScript copied")

    # Copy fonts
    fonts_src = static_dir / "fonts"
    if fonts_src.exists():
        shutil.copytree(fonts_src, static_output / "fonts")
        print("✓ Fonts copied")

    # Copy fonts.css
    css_out = static_output / "css"
    css_out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fonts_css_path, css_out / "fonts.css")
    print("✓ fonts.css copied")

    # ==================== SOURCE PAGES (attribution) ====================

    if attribution_enabled:
        template = env.get_template("source.html")

        # Render note.html
        output = template.render(
            **base_context,
            source_title="Source Note",
            source_content=note_html,
        )
        with open(output_dir / "note.html", "w", encoding="utf-8") as f:
            f.write(output)
        print("✓ note.html rendered (source note)")

        # Render prompt.html
        output = template.render(
            **base_context,
            source_title="Site Prompt",
            source_content=prompt_html,
        )
        with open(output_dir / "prompt.html", "w", encoding="utf-8") as f:
            f.write(output)
        print("✓ prompt.html rendered (site prompt)")

    print("\n✅ Build complete!")
    print(f"\n📁 Output directory: {output_dir.absolute()}")
    print("\n🌐 To view the site:")
    print(f"   cd {output_dir} && python -m http.server 8000")
    print("   Landing page:  http://localhost:8000/")
    print("   Browse page:   http://localhost:8000/browse.html")


def main():
    """Entry-point for CLI (registered in pyproject.toml scripts).

    Parses CLI arguments, loads configuration, and dispatches to build_site().
    """
    import argparse

    parser = argparse.ArgumentParser(description="Build the static site")
    parser.add_argument("--data", type=str, default=None, help="Data directory")
    parser.add_argument("--templates", type=str, default=None, help="Templates directory")
    parser.add_argument("--static", type=str, default=None, help="Static assets directory")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    parser.add_argument("--config", type=str, default=None, help="Path to config YAML")
    args = parser.parse_args()

    from resourcery_ssg.config import load_resourcery_config, build_cli_overrides

    overrides = build_cli_overrides(
        args,
        "build",
        {
            "data": "data_dir",
            "templates": "templates_dir",
            "static": "static_dir",
            "output": "output_dir",
        },
    )

    config = load_resourcery_config(
        config_path=args.config,
        overrides=overrides,
    )
    build_kwargs = dict(config["build"])
    build_kwargs["ingest_note"] = config.get("ingest", {}).get("note")
    build_kwargs["ingest_site_prompt"] = config.get("ingest", {}).get("site_prompt")
    build_site(**build_kwargs)


if __name__ == "__main__":
    main()
