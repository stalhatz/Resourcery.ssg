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

# Directories
ROOT_DIR      = Path(__file__).parent
DATA_DIR      = ROOT_DIR / 'data'
TEMPLATES_DIR = ROOT_DIR / 'templates'
STATIC_DIR    = ROOT_DIR / 'static'
OUTPUT_DIR    = ROOT_DIR / 'output'


def load_json(path):
    """Load JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_data(config, links):
    """Basic validation of data structure."""
    required_config = ['site_info', 'theme', 'navigation', 'content']
    required_links  = ['links']

    for key in required_config:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")

    for key in required_links:
        if key not in links:
            raise ValueError(f"Missing required links key: {key}")


# ==================== CUSTOM JINJA2 FILTERS ====================

def shuffle_filter(value):
    """Shuffle a list randomly."""
    value_list = list(value)
    random.shuffle(value_list)
    return value_list


# ==================== PRE-COMPUTATION HELPERS ====================

def build_category_map(config):
    """
    Pre-compute the parent→[children+self] and leaf→[self] lookup map
    so the browser never has to re-parse APP_CONFIG at runtime.

    Example output:
        {
            "development":  ["frontend", "backend", "development"],
            "frontend":     ["frontend"],
            "backend":      ["backend"],
        }
    """
    category_map = {}
    for cat in config.get("navigation", {}).get("categories", []):
        children_ids = [c["id"] for c in cat.get("children", [])]
        category_map[cat["id"]] = children_ids + [cat["id"]]
        for child in cat.get("children", []):
            category_map[child["id"]] = [child["id"]]
    return category_map


def build_all_tags(links_data):
    """
    Deduplicate and sort all tags across every link entry.
    Preserves original casing for display; keys are lowercased for dedup.

    Example output:
        ["API", "design", "open-source", "python", ...]
    """
    tag_set = {}
    for link in links_data.get("links", []):
        for tag in link.get("tags", []):
            if tag and tag.strip():
                tag_set[tag.strip().lower()] = tag.strip()
    return sorted(tag_set.values(), key=lambda t: t.lower())


# ==================== BUILD ====================

def build():
    """Build the static site."""
    print("🔨 Building static site...")

    # Clean output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # Load data
    config     = load_json(DATA_DIR / 'site.config.json')
    links_data = load_json(DATA_DIR / 'links.json')

    # Pre-compute derived data
    category_map = build_category_map(config)
    all_tags     = build_all_tags(links_data)

    # Setup Jinja2
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)

    # Register custom filters
    env.filters['shuffle'] = shuffle_filter

    # Shared base context — every template gets these
    base_context = {
        "config":        config,
        "links":         links_data,
        "category_map":  category_map,
        "all_tags":      all_tags,
    }

    # ==================== RENDER TEMPLATES ====================

    # Render index.html (landing page)
    template = env.get_template('index.html')
    output   = template.render(**base_context)
    with open(OUTPUT_DIR / 'index.html', 'w', encoding='utf-8') as f:
        f.write(output)
    print("✓ index.html rendered (landing page)")

    # Render browse.html (full browse)
    template = env.get_template('browse.html')
    output   = template.render(**base_context)
    with open(OUTPUT_DIR / 'browse.html', 'w', encoding='utf-8') as f:
        f.write(output)
    print("✓ browse.html rendered (full browse)")

    # Render style.css (THEMED CSS - CRITICAL!)
    template = env.get_template('style.css')
    output   = template.render(**base_context)

    # Create css directory in output
    css_dir = OUTPUT_DIR / 'static' / 'css'
    css_dir.mkdir(parents=True, exist_ok=True)

    with open(css_dir / 'style.css', 'w', encoding='utf-8') as f:
        f.write(output)
    print("✓ style.css rendered (themed)")

    # ==================== COPY STATIC FILES ====================

    static_output = OUTPUT_DIR / 'static'

    # Copy images
    images_src = STATIC_DIR / 'images'
    if images_src.exists():
        shutil.copytree(images_src, static_output / 'images')
        print("✓ Images copied")

    # Copy JS
    js_src = STATIC_DIR / 'js'
    if js_src.exists():
        shutil.copytree(js_src, static_output / 'js')
        print("✓ JavaScript copied")

    print("\n✅ Build complete!")
    print(f"\n📁 Output directory: {OUTPUT_DIR.absolute()}")
    print("\n🌐 To view the site:")
    print(f"   cd {OUTPUT_DIR} && python -m http.server 8000")
    print("   Landing page:  http://localhost:8000/")
    print("   Browse page:   http://localhost:8000/browse.html")


if __name__ == '__main__':
    build()
