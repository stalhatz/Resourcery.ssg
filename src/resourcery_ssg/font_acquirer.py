#!/usr/bin/env python3
"""
Font acquirer for Resourcery.ssg
Downloads Google Fonts at build time into static/fonts/ and generates
static/css/fonts.css with local @font-face rules.
No CDN dependency at runtime — consistent with the project's zero-runtime-dependency philosophy.

Run before build.py:
    poetry run python font_acquirer.py
"""

import logging
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from resourcery_ssg.errors import ResourceryError
from resourcery_ssg.io_utils import load_json, loads_json, JsonLoadError
from resourcery_ssg.logutil import get_logger, log_timing, log_user
from resourcery_ssg.theme_constants import get_effective_weights, weights_to_api_param

logger = get_logger(__name__)

GOOGLE_FONTS_API = "https://fonts.googleapis.com/css2"
# Modern browser UA — required to receive woff2 format from Google Fonts API
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

SYSTEM_FONT_KEYWORDS = {
    "-apple-system",
    "blinkmacsystemfont",
    "system-ui",
    "segoe ui",
    "helvetica neue",
    "arial",
    "helvetica",
    "sans-serif",
    "serif",
    "monospace",
    "cursive",
    "fantasy",
    "ui-sans-serif",
    "ui-serif",
    "ui-monospace",
    "georgia",
    "times new roman",
    "courier new",
    "var(--font-family)",
}


def read_cached_fonts(fonts_css: Path) -> list:
    """Read the cached font name list from the JSON comment on line 1 of fonts.css.

    fonts_css: path to the fonts.css file.

    Returns: list of font name strings, or an empty list if the file
        does not exist or the metadata comment is missing or malformed.

    JsonLoadError: caught internally, returns empty list.
    """

    if not fonts_css.exists():
        return []
    first_line = fonts_css.read_text(encoding="utf-8").split("\n")[0]
    match = re.match(r"/\*\s*(\[.*?\])\s*\*/", first_line)
    if not match:
        return []
    try:
        return loads_json(match.group(1), source="fonts.css")
    except JsonLoadError:
        return []


def is_cache_valid(fonts_css: Path, wanted_names: list, fonts_dir: Path = None) -> bool:
    """Check whether the local font cache covers all requested fonts.

    Verifies that fonts.css lists exactly the wanted fonts and that every
    corresponding .woff2 file exists on disk. Makes no network contact.

    fonts_css: path to the fonts.css cache file.
    wanted_names: list of font name strings that should be cached.
    fonts_dir: directory containing font files (defaults to parent of fonts_css).

    Returns: True if the cache is complete and up to date, False otherwise.
    """

    if fonts_dir is None:
        fonts_dir = fonts_css.parent
    if set(read_cached_fonts(fonts_css)) != set(wanted_names):
        return False
    for name in wanted_names:
        slug = name.lower().replace(" ", "-")
        if not any(fonts_dir.glob(f"{slug}-*.woff2")):
            return False
    return True


def _load_config(data_dir: Path) -> dict:
    """Load site config and merge design theme into it.

    Reads both site.config.json and design.json from data_dir, and
    overlays the ``theme`` section of design.json onto the config.

    data_dir: directory containing site.config.json and design.json.

    Returns: dictionary of site configuration with ``theme`` populated.

    JsonLoadError: site.config.json does not exist or either file is not
        valid JSON.
    """

    config = load_json(data_dir / "site.config.json")

    design_path = data_dir / "design.json"
    if design_path.exists():
        design = load_json(design_path)
        theme = design.get("theme", {})
        if theme:
            config["theme"] = theme

    return config


def is_system_font(name: str) -> bool:
    """Check whether a font name is a known system/keyword font.

    name: CSS font-family name (may include quotes).

    Returns: True if the name appears in SYSTEM_FONT_KEYWORDS, False otherwise.
    """

    return name.strip().strip("'\"").lower() in SYSTEM_FONT_KEYWORDS


def extract_google_font_candidates(stack: str) -> list:
    """Extract non-system font names from a CSS font-family stack, preserving order.

    stack: comma-separated CSS font-family string.

    Returns: list of font name strings that are not in SYSTEM_FONT_KEYWORDS.
    """

    names = []
    for part in stack.split(","):
        name = part.strip().strip("'\"")
        if name and not is_system_font(name):
            names.append(name)
    return names


def fetch_google_fonts_css(font_name: str, weights_param: str) -> str | None:
    """Fetch @font-face CSS from the Google Fonts API.

    font_name: name of the font family (e.g. "Roboto").
    weights_param: Google Fonts ital,wght parameter string.

    Returns: raw CSS string containing @font-face rules, or None if the
        request fails or the response contains no @font-face blocks.

    Exception: any network/HTTP error is caught internally and returns None.
    """

    family_param = f"{font_name.replace(' ', '+')}:ital,wght@{weights_param}"
    url = f"{GOOGLE_FONTS_API}?family={family_param}&display=swap"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            css = r.read().decode("utf-8")
            return css if "@font-face" in css else None
    except Exception:
        return None


def find_first_downloadable(stack: str, weights_param: str) -> tuple:
    """Find the first Google Font in a stack that resolves successfully.

    Tries each non-system font name in order and returns the first one
    that returns valid @font-face CSS from the Google Fonts API.

    stack: comma-separated CSS font-family string.
    weights_param: Google Fonts ital,wght parameter string.

    Returns: (font_name, css) tuple on success, or (None, None) if no
        candidate resolved.

    Side-effects: logs a warning at WARN when the first-preference font
        fails but a fallback succeeds.
    """

    candidates = extract_google_font_candidates(stack)
    if not candidates:
        return None, None

    for i, name in enumerate(candidates):
        css = fetch_google_fonts_css(name, weights_param)
        if css:
            if i > 0:
                logger.warning(
                    f"  ⚠️  '{candidates[0]}' not found on Google Fonts, "
                    f"using '{name}' instead (position {i+1} in stack)"
                )
            return name, css

    logger.warning(f"  ✗ None of the candidates resolved: {candidates}")
    return None, None


def download_file(url: str, dest: Path) -> bool:
    """Download a file from a URL and write it to a local path.

    url: the remote URL to download from.
    dest: local filesystem path for the downloaded file.

    Returns: True if the download succeeded, False otherwise.

    Exception: any network/IO error is caught internally and returns False.
    """

    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            dest.write_bytes(r.read())
        return True
    except Exception as e:
        logger.warning(f"  ✗ Failed to download {url}: {e}")
        return False


def process_font(
    font_name: str,
    css: str,
    face_blocks_out: list,
    fonts_dir: Path,
    css_dir: Path,
    counters: dict = None,
) -> bool:
    """Download all woff2 variants from previously fetched CSS.

    Parses the CSS for @font-face blocks, downloads each unique woff2
    variant (subset × style × weight) to the fonts directory, and appends
    rewritten local @font-face rules to face_blocks_out.

    font_name: the font family name (used in @font-face and filenames).
    css: raw CSS from the Google Fonts API containing @font-face blocks.
    face_blocks_out: list to which local @font-face rule strings are appended.
    fonts_dir: directory to write font files into.
    css_dir: directory where fonts.css will be written (used for relative paths).
    counters: optional dict with "downloaded"/"cached"/"failed" counters to
        increment per variant outcome (used for the end-of-run INFO record).

    Returns: True if at least one variant was successfully processed.

    Side-effects: downloads files to fonts_dir; appends to face_blocks_out.
    """

    # Parse subset name + @font-face block together to avoid filename collisions
    # Google Fonts annotates each block with a comment e.g. /* latin */ /* cyrillic */
    raw_blocks = re.findall(
        r"/\*\s*([^*]+?)\s*\*/\s*@font-face\s*\{([^}]+)\}", css, re.DOTALL
    )
    font_slug = font_name.lower().replace(" ", "-")
    ok_count = 0

    for subset_name, block in raw_blocks:
        src_match = re.search(r"src:\s*url\(([^)]+)\)", block)
        style_match = re.search(r"font-style:\s*(\S+?);", block)
        weight_match = re.search(r"font-weight:\s*(\S+?);", block)
        unicode_match = re.search(r"unicode-range:\s*([^;]+);", block)

        if not src_match:
            continue

        remote_url = src_match.group(1).strip()
        font_style = style_match.group(1) if style_match else "normal"
        font_weight = weight_match.group(1) if weight_match else "400"
        unicode_range = unicode_match.group(1).strip() if unicode_match else None
        ext = remote_url.split(".")[-1].split("?")[0]  # always woff2
        subset = subset_name.strip().replace(" ", "-")

        local_filename = f"{font_slug}-{font_style}-{font_weight}-{subset}.{ext}"
        local_path = fonts_dir / local_filename

        if local_path.exists():
            if counters is not None:
                counters["cached"] += 1
            logger.debug(f"Font '{font_name}': cache hit {local_filename}")
            log_user(f"    · {local_filename} (cached)")
        else:
            logger.debug(f"Font '{font_name}': downloading {remote_url}")
            if not download_file(remote_url, local_path):
                if counters is not None:
                    counters["failed"] += 1
                continue
            if counters is not None:
                counters["downloaded"] += 1
            log_user(f"    ✓ {local_filename}")

        # Build relative URL from css_dir to fonts_dir
        rel_url = Path(os.path.relpath(fonts_dir, css_dir)) / local_filename

        face = (
            f"@font-face {{\n"
            f"  font-family: '{font_name}';\n"
            f"  font-style: {font_style};\n"
            f"  font-weight: {font_weight};\n"
            f"  font-display: swap;\n"
            f"  src: url('{rel_url}') format('{ext}');"
        )
        if unicode_range:
            face += f"\n  unicode-range: {unicode_range};"
        face += "\n}"
        face_blocks_out.append(face)
        ok_count += 1

    log_user(f"    → {ok_count} variant(s) written")
    return ok_count > 0


def acquire_fonts(*, data_dir, fonts_dir, css_dir):
    """Download all required Google Fonts and generate fonts.css.

    Reads typography config from site.config.json, determines required
    weights from heading_style, checks the local cache, downloads any
    missing font files, and writes fonts.css with local @font-face rules.

    Args:
        data_dir: Directory containing site.config.json.
        fonts_dir: Directory to write .woff2 font files into.
        css_dir: Directory to write fonts.css into.

    Returns: None.

    Side-effects: creates directories, downloads files, writes fonts.css,
        logs progress at INFO_USER.

    ResourceryError: 1 if any font download fails.
    """

    log_user("🔤 Acquiring fonts...\n")

    config = _load_config(data_dir)
    typography = config.get("theme", {}).get("typography", {})
    font_family = typography.get("font_family", "")
    heading_font = typography.get("heading_font", "")

    fonts_dir.mkdir(parents=True, exist_ok=True)
    css_dir.mkdir(parents=True, exist_ok=True)

    # Derive exact weights needed from heading_style + typography overrides
    heading_style = (
        config.get("theme", {}).get("effects", {}).get("heading_style", "natural")
    )
    typography = config.get("theme", {}).get("typography", {})
    weights_param = weights_to_api_param(get_effective_weights(typography, heading_style))

    # Fast cache check — no network contact needed
    wanted_names = list(
        dict.fromkeys(
            candidates[0]
            for stack in [font_family, heading_font]
            if stack
            for candidates in [extract_google_font_candidates(stack)]
            if candidates
        )
    )

    if is_cache_valid(css_dir / "fonts.css", wanted_names, fonts_dir=fonts_dir):
        log_user("ℹ  fonts.css is up to date and all font files present — skipping")
        logger.info(f"Downloaded 0 fonts, {len(wanted_names)} from cache, 0 failed")
        return

    # Check whether there are any Google Font candidates at all
    all_candidates = extract_google_font_candidates(
        font_family
    ) + extract_google_font_candidates(heading_font)
    if not all_candidates:
        log_user("ℹ  No Google Fonts detected — using system fonts only.")
        (css_dir / "fonts.css").write_text(
            "/* No Google Fonts configured */\n", encoding="utf-8"
        )
        log_user("\n✅ fonts.css written (empty)")
        logger.info("Downloaded 0 fonts, 0 from cache, 0 failed")
        return

    face_blocks = []
    all_ok = True
    seen = set()
    counters = {"downloaded": 0, "cached": 0, "failed": 0}

    for label, stack in [("font_family", font_family), ("heading_font", heading_font)]:
        if not stack:
            continue

        log_user(f"  Processing {label}: '{stack}'")
        font_name, css = find_first_downloadable(stack, weights_param)

        if font_name is None:
            logger.warning(
                f"  ✗ No valid Google Font found in {label} stack — will rely on system fallbacks"
            )
            all_ok = False
            continue

        if font_name in seen:
            log_user(f"  · '{font_name}' already downloaded, skipping")
            continue

        seen.add(font_name)
        log_user(f"  → Downloading '{font_name}'...")
        if not process_font(
            font_name, css, face_blocks, fonts_dir, css_dir, counters=counters
        ):
            all_ok = False

    fonts_css = css_dir / "fonts.css"
    header = f"/* {json.dumps(list(seen))} */\n"
    fonts_css.write_text(header + "\n\n".join(face_blocks) + "\n", encoding="utf-8")
    log_user(f"\n✅ fonts.css written — {len(face_blocks)} @font-face rule(s)")
    log_user(f"   {fonts_css.resolve()}")
    logger.info(
        f"Downloaded {counters['downloaded']} fonts, {counters['cached']} from cache, "
        f"{counters['failed']} failed"
    )

    if not all_ok:
        msg = "\n⚠️  Some fonts failed — check names at fonts.google.com"
        logger.error(msg)
        raise ResourceryError(msg)


def main():
    """Entry-point for CLI (registered in pyproject.toml scripts).

    Parses CLI arguments, loads configuration, and dispatches to acquire_fonts().
    """
    import argparse

    parser = argparse.ArgumentParser(description="Acquire fonts from Google Fonts")
    parser.add_argument("--data", type=str, default=None, help="Data directory")
    parser.add_argument("--fonts-dir", type=str, default=None, help="Fonts output directory")
    parser.add_argument("--css-dir", type=str, default=None, help="CSS output directory")
    parser.add_argument("--config", type=str, default=None, help="Path to config YAML")
    parser.add_argument(
        "--log-level", type=str, default=None,
        help="Console log level: DEBUG|INFO|WARN|ERROR (case-insensitive)",
    )
    args = parser.parse_args()

    from resourcery_ssg.config import load_resourcery_config, build_cli_overrides
    from resourcery_ssg.logutil import setup_logging

    overrides = build_cli_overrides(
        args,
        "acquire-fonts",
        {"data": "data_dir", "fonts_dir": "fonts_dir", "css_dir": "css_dir"},
    )
    if args.log_level:
        overrides["logging.level"] = args.log_level

    config = load_resourcery_config(
        config_path=args.config,
        overrides=overrides,
    )
    setup_logging(config)
    with log_timing(logger, "Command", level=logging.INFO):
        try:
            acquire_fonts(**config["acquire-fonts"])
        except ResourceryError:
            sys.exit(1)


if __name__ == "__main__":
    main()
