#!/usr/bin/env python3
"""
Font acquirer for Resourcery.ssg
Downloads Google Fonts at build time into static/fonts/ and generates
static/css/fonts.css with local @font-face rules.
No CDN dependency at runtime — consistent with the project's zero-runtime-dependency philosophy.

Run before build.py:
    poetry run python font_acquirer.py
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

from resourcery_ssg.theme_constants import get_required_weights, weights_to_api_param

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
STATIC_DIR = ROOT_DIR / "static"
FONTS_DIR = STATIC_DIR / "fonts"
CSS_DIR = STATIC_DIR / "css"

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

    json.JSONDecodeError: caught internally, returns empty list.
    """

    if not fonts_css.exists():
        return []
    first_line = fonts_css.read_text(encoding="utf-8").split("\n")[0]
    match = re.match(r"/\*\s*(\[.*?\])\s*\*/", first_line)
    if not match:
        return []
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return []


def is_cache_valid(fonts_css: Path, wanted_names: list) -> bool:
    """Check whether the local font cache covers all requested fonts.

    Verifies that fonts.css lists exactly the wanted fonts and that every
    corresponding .woff2 file exists on disk. Makes no network contact.

    fonts_css: path to the fonts.css cache file.
    wanted_names: list of font name strings that should be cached.

    Returns: True if the cache is complete and up to date, False otherwise.
    """

    if set(read_cached_fonts(fonts_css)) != set(wanted_names):
        return False
    for name in wanted_names:
        slug = name.lower().replace(" ", "-")
        if not any(FONTS_DIR.glob(f"{slug}-*.woff2")):
            return False
    return True


def load_config() -> dict:
    """Load site.config.json from the data directory.

    Returns: dictionary of site configuration.

    FileNotFoundError: the config file does not exist.
    json.JSONDecodeError: the config file is not valid JSON.
    """

    with open(DATA_DIR / "site.config.json", "r", encoding="utf-8") as f:
        return json.load(f)


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

    Side-effects: prints a warning when the first-preference font fails
        but a fallback succeeds.
    """

    candidates = extract_google_font_candidates(stack)
    if not candidates:
        return None, None

    for i, name in enumerate(candidates):
        css = fetch_google_fonts_css(name, weights_param)
        if css:
            if i > 0:
                print(
                    f"  ⚠️  '{candidates[0]}' not found on Google Fonts, "
                    f"using '{name}' instead (position {i+1} in stack)"
                )
            return name, css

    print(f"  ✗ None of the candidates resolved: {candidates}")
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
        print(f"  ✗ Failed to download {url}: {e}")
        return False


def process_font(font_name: str, css: str, face_blocks_out: list) -> bool:
    """Download all woff2 variants from previously fetched CSS.

    Parses the CSS for @font-face blocks, downloads each unique woff2
    variant (subset × style × weight) to the fonts directory, and appends
    rewritten local @font-face rules to face_blocks_out.

    font_name: the font family name (used in @font-face and filenames).
    css: raw CSS from the Google Fonts API containing @font-face blocks.
    face_blocks_out: list to which local @font-face rule strings are appended.

    Returns: True if at least one variant was successfully processed.

    Side-effects: downloads files to FONTS_DIR; appends to face_blocks_out.
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
        local_path = FONTS_DIR / local_filename

        if local_path.exists():
            print(f"    · {local_filename} (cached)")
        else:
            if not download_file(remote_url, local_path):
                continue
            print(f"    ✓ {local_filename}")

        face = (
            f"@font-face {{\n"
            f"  font-family: '{font_name}';\n"
            f"  font-style: {font_style};\n"
            f"  font-weight: {font_weight};\n"
            f"  font-display: swap;\n"
            f"  src: url('/static/fonts/{local_filename}') format('{ext}');"
        )
        if unicode_range:
            face += f"\n  unicode-range: {unicode_range};"
        face += "\n}"
        face_blocks_out.append(face)
        ok_count += 1

    print(f"    → {ok_count} variant(s) written")
    return ok_count > 0


def acquire_fonts():
    """Download all required Google Fonts and generate fonts.css.

    Reads typography config from site.config.json, determines required
    weights from heading_style, checks the local cache, downloads any
    missing font files, and writes static/css/fonts.css with local
    @font-face rules.

    Returns: None.

    Side-effects: creates directories, downloads files, writes fonts.css,
        prints progress to stdout.

    SystemExit: 1 if any font download fails.
    """

    print("🔤 Acquiring fonts...\n")

    config = load_config()
    typography = config.get("theme", {}).get("typography", {})
    font_family = typography.get("font_family", "")
    heading_font = typography.get("heading_font", "")

    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    CSS_DIR.mkdir(parents=True, exist_ok=True)

    # Derive exact weights needed from heading_style
    heading_style = (
        config.get("theme", {}).get("effects", {}).get("heading_style", "natural")
    )
    weights_param = weights_to_api_param(get_required_weights(heading_style))

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

    if is_cache_valid(CSS_DIR / "fonts.css", wanted_names):
        print("ℹ  fonts.css is up to date and all font files present — skipping")
        return

    # Check whether there are any Google Font candidates at all
    all_candidates = extract_google_font_candidates(
        font_family
    ) + extract_google_font_candidates(heading_font)
    if not all_candidates:
        print("ℹ  No Google Fonts detected — using system fonts only.")
        (CSS_DIR / "fonts.css").write_text(
            "/* No Google Fonts configured */\n", encoding="utf-8"
        )
        print("\n✅ fonts.css written (empty)")
        return

    face_blocks = []
    all_ok = True
    seen = set()

    for label, stack in [("font_family", font_family), ("heading_font", heading_font)]:
        if not stack:
            continue

        print(f"  Processing {label}: '{stack}'")
        font_name, css = find_first_downloadable(stack, weights_param)

        if font_name is None:
            print(
                f"  ✗ No valid Google Font found in {label} stack — will rely on system fallbacks"
            )
            all_ok = False
            continue

        if font_name in seen:
            print(f"  · '{font_name}' already downloaded, skipping")
            continue

        seen.add(font_name)
        print(f"  → Downloading '{font_name}'...")
        if not process_font(font_name, css, face_blocks):
            all_ok = False

    fonts_css = CSS_DIR / "fonts.css"
    header = f"/* {json.dumps(list(seen))} */\n"
    fonts_css.write_text(header + "\n\n".join(face_blocks) + "\n", encoding="utf-8")
    print(f"\n✅ fonts.css written — {len(face_blocks)} @font-face rule(s)")
    print(f"   {fonts_css.resolve()}")

    if not all_ok:
        print("\n⚠️  Some fonts failed — check names at fonts.google.com")
        sys.exit(1)


def main():
    """Entry-point for CLI (registered in pyproject.toml scripts).

    Delegates to acquire_fonts().
    """
    acquire_fonts()


if __name__ == "__main__":
    acquire_fonts()
