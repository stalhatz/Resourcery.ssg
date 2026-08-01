"""
Pure design and data checks for Resourcery.ssg.

Layer between the WCAG math in ``wcag.py`` and the IO/orchestration in
``validate.py``: check functions for design tokens, effects, and cross-data
references. No IO, no jsonschema, no logging, no class state — every public
check function returns an ``(errors, warnings)`` tuple of message strings
and mutates nothing. Extracted from ``validate.py`` as part of the
validate-module split.
"""

import re
from typing import Dict, List, Set, Tuple

from resourcery_ssg.wcag import contrast_ratio, parse_em


def validate_design_tokens(design: dict) -> Tuple[List[str], List[str]]:
    """Validate numeric ranges and WCAG contrast for design tokens.

    Runs after schema validation passes. Returns error messages for
    out-of-range values and contrast failures; warnings are always empty
    for this check.

    design: the design data dict (e.g. the parsed design.json).

    Returns: (errors, warnings) tuple of message strings.
    """

    errors: List[str] = []
    warnings: List[str] = []
    theme = design.get("theme", {})
    colors = theme.get("colors", {})
    typography = theme.get("typography", {})
    spacing_cfg = theme.get("spacing", {})
    radius_cfg = theme.get("radius", {})
    elevation_cfg = theme.get("elevation", {})
    border_cfg = theme.get("border", {})
    motion_cfg = theme.get("motion", {})

    # --- Range checks ---

    # Color levers
    levers = colors.get("levers", {})
    _check_range(errors, levers, "brand_saturation", 0, 1)
    _check_range(errors, levers, "neutral_temperature", -1, 1)
    _check_range(errors, levers, "shade_spread", 0, 1)

    # Overlay strength
    _check_range(errors, colors, "overlay_strength", 0, 1)

    # Typography
    _check_range(errors, typography, "font_size_base", 14, 20)
    _check_range(errors, typography, "type_scale_ratio", 1.125, 1.5)
    _check_range(errors, typography, "body_line_height", 1.4, 1.8)
    _check_range(errors, typography, "heading_line_height", 1.0, 1.3)
    _check_range(errors, typography, "measure", 60, 75)
    _check_range(errors, typography, "heading_weight", 300, 900)

    # Heading letter spacing (custom parser)
    spacing_val = typography.get("heading_letter_spacing")
    if spacing_val is not None:
        em_val = parse_em(spacing_val)
        if em_val is None:
            errors.append(
                f"❌ typography.heading_letter_spacing: cannot parse '{spacing_val}' as em value"
            )
        elif em_val < -0.04 or em_val > 0.12:
            errors.append(
                f"❌ typography.heading_letter_spacing: {em_val}em is out of range (-0.04em to 0.12em)"
            )

    # Spacing
    space_base = spacing_cfg.get("space_base")
    if space_base is not None and space_base not in (4, 8):
        errors.append(
            f"❌ spacing.space_base: {space_base} must be 4 or 8"
        )
    _check_range(errors, spacing_cfg, "space_ratio", 1.5, 2)

    # Radius
    _check_range(errors, radius_cfg, "radius_base", 0, 16)
    for key in ["radius_card", "radius_button", "radius_pill"]:
        _check_range(errors, radius_cfg, key, 0, 48)

    # Elevation
    _check_range(errors, elevation_cfg, "shadow_strength", 0, 1)
    _check_range(errors, elevation_cfg, "shadow_softness", 0, 1)

    # Border
    _check_range(errors, border_cfg, "border_width", 0, 2)

    # Motion
    _check_range(errors, motion_cfg, "transition_duration", 120, 360)

    # --- Contrast checks ---

    bg = colors.get("background")
    if bg and isinstance(bg, str) and bg.startswith("#"):
        _check_contrast_pair(errors, colors, "text", bg, 4.5,
                             "text on background")
        _check_contrast_pair(errors, colors, "text_muted", bg, 3.0,
                             "text_muted on background")
        _check_contrast_pair(errors, colors, "primary", bg, 4.5,
                             "primary on background", large_ok=3.0)
        _check_contrast_pair(errors, colors, "accent", bg, 4.5,
                             "accent on background", large_ok=3.0)

    # Dark mode contrast
    dark_cfg = colors.get("dark", {})
    dark_bg = dark_cfg.get("background")
    if dark_bg and isinstance(dark_bg, str) and dark_bg.startswith("#"):
        _check_contrast_pair(errors, dark_cfg, "text", dark_bg, 4.5,
                             "dark text on dark background")
        _check_contrast_pair(errors, dark_cfg, "text_muted", dark_bg, 3.0,
                             "dark text_muted on dark background")
        _check_contrast_pair(errors, dark_cfg, "primary", dark_bg, 4.5,
                             "dark primary on dark background", large_ok=3.0)
        _check_contrast_pair(errors, dark_cfg, "accent", dark_bg, 4.5,
                             "dark accent on dark background", large_ok=3.0)

    return errors, warnings


def _check_range(errors: List[str], cfg: dict, key: str, min_val: float, max_val: float) -> None:
    """Check a numeric config value is within [min_val, max_val].

    errors: list to append the error message to.
    cfg: config dict containing the key.
    key: the key to check in cfg.
    min_val: inclusive minimum.
    max_val: inclusive maximum.

    Returns: None.

    Side-effects: appends to the errors list if value is out of range.
    """

    value = cfg.get(key)
    if value is None:
        return
    if not isinstance(value, (int, float)):
        return
    if value < min_val or value > max_val:
        errors.append(
            f"❌ {key}: {value} is out of range [{min_val}, {max_val}]"
        )


def _check_contrast_pair(errors: List[str], colors: dict, fg_key: str, bg_value: str,
                         required_ratio: float, label: str, large_ok: float = None) -> None:
    """Check WCAG contrast ratio for a foreground/background color pair.

    errors: list to append the error message to.
    colors: dict from which to read the foreground color.
    fg_key: key in colors for the foreground color.
    bg_value: hex string for background.
    required_ratio: minimum ratio for normal text.
    label: human-readable label for error messages.
    large_ok: optional relaxed ratio for large text/UI elements.

    Returns: None.

    Side-effects: appends to the errors list if ratio is insufficient.
    """

    fg_value = colors.get(fg_key)
    if not fg_value or not isinstance(fg_value, str) or not fg_value.startswith("#"):
        return

    try:
        ratio = contrast_ratio(fg_value, bg_value)
    except Exception:
        return

    if ratio < required_ratio:
        msg = (
            f"❌ WCAG contrast: {label} — {fg_key}({fg_value}) / "
            f"background({bg_value}) = {ratio:.2f}:1 (needs ≥ {required_ratio}:1)"
        )
        if large_ok is not None and ratio >= large_ok:
            msg += " — PASSES for large text (≥3:1) but FAILS for normal text (≥4.5:1)"
        errors.append(msg)


def validate_effects(design: dict) -> Tuple[List[str], List[str]]:
    """Check for contradictory or ineffective effect and token combinations.

    Inspects card_style, hover_effect, and the border/elevation tokens for
    known bad pairings. Warnings-only today; errors is always empty.

    design: the design data dict (e.g. the parsed design.json).

    Returns: (errors, warnings) tuple of message strings.
    """

    errors: List[str] = []
    warnings: List[str] = []
    effects = design.get("theme", {}).get("effects", {})
    if not effects:
        return errors, warnings  # all defaults, always fine

    card_style = effects.get("card_style", "image-overlay")
    hover_effect = effects.get("hover_effect", "lift")

    theme = design.get("theme", {})
    border_cfg = theme.get("border", {})
    border_width = border_cfg.get("border_width", 1)
    elevation_cfg = theme.get("elevation", {})
    shadow_strength = elevation_cfg.get("shadow_strength", 0.35)

    # elevated card_style with no shadows defeats the point
    if card_style == "elevated" and shadow_strength == 0:
        warnings.append(
            "⚠️ effects: card_style 'elevated' with elevation.shadow_strength 0 "
            "will render identically to 'flat' — consider shadow_strength ≥ 0.15."
        )

    # outlined card_style with border_width 0 is contradictory
    if card_style == "outlined" and border_width == 0:
        warnings.append(
            "⚠️ effects: card_style 'outlined' uses its own primary-color border — "
            "border.border_width 0 hides it completely. Set border_width ≥ 1."
        )

    # image-overlay with hover 'outline' is low contrast (outline on image)
    if card_style == "image-overlay" and hover_effect == "outline":
        warnings.append(
            "⚠️ effects: hover_effect 'outline' on card_style 'image-overlay' "
            "may have poor contrast against dark card backgrounds — consider 'glow'."
        )

    return errors, warnings


def extract_valid_categories(config_data: dict) -> Set[str]:
    """Collect all valid category IDs from the navigation config.

    Includes both parent categories and their children.

    config_data: the site configuration dict (e.g. the parsed site.config.json).

    Returns: set of category ID strings.
    """

    valid_categories = set()

    categories = config_data.get("navigation", {}).get("categories", [])

    for category in categories:
        valid_categories.add(category["id"])

        children = category.get("children", [])
        for child in children:
            valid_categories.add(child["id"])

    return valid_categories


def validate_cross_references(config_data: dict, links_data: dict, design_data: dict) -> Tuple[List[str], List[str]]:
    """Validate links data against the site configuration.

    Checks: category IDs exist, no duplicate link IDs, active links have
    URLs, image paths are well-formed, menu links have valid schemes,
    and theme colour hex codes are valid. Pure — reporting is left to the
    caller.

    config_data: the site configuration dict.
    links_data: the links data dict (e.g. the parsed links.json).
    design_data: the design data dict (e.g. the parsed design.json).

    Returns: (errors, warnings) tuple of message strings. Duplicate link
        IDs are errors; everything else is a warning.
    """

    errors: List[str] = []
    warnings: List[str] = []
    valid_categories = extract_valid_categories(config_data)
    link_ids = set()
    duplicate_ids = []

    # Validate links against config categories
    for link in links_data.get("links", []):
        link_id = link.get("id", "unknown")
        category = link.get("category", "")

        # Check for duplicate IDs
        if link_id in link_ids:
            duplicate_ids.append(link_id)
        link_ids.add(link_id)

        # Check category exists
        if category and category not in valid_categories:
            warnings.append(
                f"⚠️  Link '{link_id}' uses unknown category '{category}'"
            )

        # Check for required fields based on status
        if link.get("status") == "active":
            if not link.get("url"):
                warnings.append(f"⚠️  Active link '{link_id}' is missing URL")

        # Check image paths (basic validation)
        image = link.get("image")
        if image and not image.startswith(("http://", "https://", "/")):
            warnings.append(
                f"⚠️  Link '{link_id}' has suspicious image path: '{image}'"
            )

    # Report duplicate IDs
    if duplicate_ids:
        errors.append(
            f"❌ Duplicate link IDs found: {', '.join(duplicate_ids)}"
        )

    # Validate config menu links
    for menu_link in config_data.get("navigation", {}).get("menu_links", []):
        url = menu_link.get("url", "")
        if not url.startswith(("http://", "https://", "mailto:", "/")):
            warnings.append(
                f"⚠️  Menu link '{menu_link.get('label')}' has suspicious URL: '{url}'"
            )

    # Validate color hex codes in config (skip non-color fields like levers, overlay_strength)
    color_keys = {"primary", "secondary", "background", "surface", "text",
                   "text_muted", "accent", "error", "success"}
    colors = design_data.get("theme", {}).get("colors", {})
    for color_name, color_value in colors.items():
        if color_name in color_keys and not is_valid_hex_color(color_value):
            warnings.append(
                f"⚠️  Invalid hex color for '{color_name}': '{color_value}'"
            )
        # Also check dark mode anchors
        if color_name == "dark" and isinstance(color_value, dict):
            for dk, dv in color_value.items():
                if dk in color_keys and isinstance(dv, str) and not is_valid_hex_color(dv):
                    warnings.append(
                        f"⚠️  Invalid hex color for 'dark.{dk}': '{dv}'"
                    )

    return errors, warnings


def is_valid_hex_color(color: str) -> bool:
    """Check if a string is a valid 6-digit hex colour code.

    color: the string to check.

    Returns: True if the string matches the pattern #RRGGBB, False otherwise.
    """

    if not isinstance(color, str):
        return False
    return bool(re.match(r"^#[0-9a-fA-F]{6}$", color))
