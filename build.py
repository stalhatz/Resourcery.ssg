#!/usr/bin/env python3
"""
Build script for static link aggregation site.
Renders Jinja2 templates with JSON data.
"""

import json
import os
import shutil
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Directories
ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / 'data'
TEMPLATES_DIR = ROOT_DIR / 'templates'
STATIC_DIR = ROOT_DIR / 'static'
OUTPUT_DIR = ROOT_DIR / 'output'

def load_json(path):
    """Load JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def validate_data(config, links):
    """Basic validation of data structure."""
    required_config = ['site_info', 'theme', 'navigation', 'content']
    required_links = ['links']
    
    for key in required_config:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")
    
    for key in required_links:
        if key not in links:
            raise ValueError(f"Missing required links key: {key}")

def build(acquire_images=False):
    """Build the static site."""
    print("🔨 Building static site...")
    
    # Optional: Acquire images before build
    if acquire_images:
        from image_acquirer import ImageAcquirer
        
        links_path = DATA_DIR / 'links.json'
        links_data = load_json(links_path)
        
        acquirer = ImageAcquirer(ROOT_DIR)
        updated_data = acquirer.acquire_all(links_data, force=False)
        
        # Save updated links
        with open(links_path, 'w', encoding='utf-8') as f:
            json.dump(updated_data, f, indent=2, ensure_ascii=False)
        
        print()
    
    # Clean output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    
    # Load data
    config = load_json(DATA_DIR / 'site.config.json')
    links = load_json(DATA_DIR / 'links.json')
    
    # Validate
    validate_data(config, links)
    print("✓ Data validation passed")
    
    # Setup Jinja2
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=True
    )
    
    # Render index.html
    template = env.get_template('index.html')
    output = template.render(config=config, links=links)
    
    with open(OUTPUT_DIR / 'index.html', 'w', encoding='utf-8') as f:
        f.write(output)
    
    print("✓ index.html rendered")
    
    # Copy static files
    static_output = OUTPUT_DIR / 'static'
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, static_output)
        print("✓ Static files copied")
    
    # Copy data files
    data_output = OUTPUT_DIR / 'data'
    data_output.mkdir()
    shutil.copy(DATA_DIR / 'site.config.json', data_output)
    shutil.copy(DATA_DIR / 'links.json', data_output)
    print("✓ Data files copied")
    
    print("\n✅ Build complete!")
    print(f"\n📁 Output directory: {OUTPUT_DIR.absolute()}")
    print("\n🌐 To view the site:")
    print(f"   cd {OUTPUT_DIR} && python -m http.server 8000")
    print("   Then open: http://localhost:8000")

if __name__ == '__main__':
    acquire = '--acquire-images' in sys.argv
    build(acquire_images=acquire)