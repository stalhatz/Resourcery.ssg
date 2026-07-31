#!/usr/bin/env python3
"""
Validation script for Static Link Aggregation Website.
Validates data files against JSON schemas and performs cross-validation.
"""

import re
import sys
from pathlib import Path
from jsonschema import validate, ValidationError, SchemaError
from typing import Dict, List, Set, Tuple, Any, Optional

from resourcery_ssg.io_utils import load_json, JsonLoadError


# ============================================================================
# WCAG relative luminance and contrast helpers
# ============================================================================


def _hex_to_srgb(hex_color: str) -> tuple:
    """Convert a six-digit hex color to sRGB (0-1) tuple.

    hex_color: e.g. "#2563eb".

    Returns: (r, g, b) tuple of floats 0-1.
    """

    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (r, g, b)


def _linearize(channel: float) -> float:
    """Linearize a single sRGB channel value for luminance calculation.

    channel: sRGB value 0-1.

    Returns: linearized value.
    """

    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """Compute WCAG 2.1 relative luminance from a hex color.

    hex_color: six-digit hex string e.g. "#ffffff".

    Returns: luminance value 0-1.
    """

    r, g, b = _hex_to_srgb(hex_color)
    r_lin = _linearize(r)
    g_lin = _linearize(g)
    b_lin = _linearize(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(color1: str, color2: str) -> float:
    """Compute WCAG 2.1 contrast ratio between two hex colors.

    color1: first hex color string.
    color2: second hex color string.

    Returns: contrast ratio (1.0–21.0). Higher = more contrast.
    """

    l1 = relative_luminance(color1)
    l2 = relative_luminance(color2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def parse_em(value: str) -> Optional[float]:
    """Parse a CSS em string to a float, stripping the unit.

    value: e.g. "0.05em", "0", "-0.03em".

    Returns: float value or None if unparseable.
    """

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        cleaned = value.strip().rstrip("em").rstrip("EM")
        return float(cleaned)
    except (ValueError, TypeError):
        return None


# ============================================================================
# Design token validation (range + contrast)
# ============================================================================


def validate_design_tokens(validator_instance) -> None:
    """Validate numeric ranges and WCAG contrast for design tokens.

    Runs after schema validation passes. Appends errors to
    validator_instance.errors for out-of-range values and contrast failures.

    validator_instance: a DataValidator instance with design_data loaded and
        errors list already initialized.

    Returns: None.

    Side-effects: appends to validator_instance.errors.
    """

    design = validator_instance.design_data
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
    _check_range(validator_instance, levers, "brand_saturation", 0, 1)
    _check_range(validator_instance, levers, "neutral_temperature", -1, 1)
    _check_range(validator_instance, levers, "shade_spread", 0, 1)

    # Overlay strength
    _check_range(validator_instance, colors, "overlay_strength", 0, 1)

    # Typography
    _check_range(validator_instance, typography, "font_size_base", 14, 20)
    _check_range(validator_instance, typography, "type_scale_ratio", 1.125, 1.5)
    _check_range(validator_instance, typography, "body_line_height", 1.4, 1.8)
    _check_range(validator_instance, typography, "heading_line_height", 1.0, 1.3)
    _check_range(validator_instance, typography, "measure", 60, 75)
    _check_range(validator_instance, typography, "heading_weight", 300, 900)

    # Heading letter spacing (custom parser)
    spacing_val = typography.get("heading_letter_spacing")
    if spacing_val is not None:
        em_val = parse_em(spacing_val)
        if em_val is None:
            validator_instance.errors.append(
                f"❌ typography.heading_letter_spacing: cannot parse '{spacing_val}' as em value"
            )
        elif em_val < -0.04 or em_val > 0.12:
            validator_instance.errors.append(
                f"❌ typography.heading_letter_spacing: {em_val}em is out of range (-0.04em to 0.12em)"
            )

    # Spacing
    space_base = spacing_cfg.get("space_base")
    if space_base is not None and space_base not in (4, 8):
        validator_instance.errors.append(
            f"❌ spacing.space_base: {space_base} must be 4 or 8"
        )
    _check_range(validator_instance, spacing_cfg, "space_ratio", 1.5, 2)

    # Radius
    _check_range(validator_instance, radius_cfg, "radius_base", 0, 16)
    for key in ["radius_card", "radius_button", "radius_pill"]:
        _check_range(validator_instance, radius_cfg, key, 0, 48)

    # Elevation
    _check_range(validator_instance, elevation_cfg, "shadow_strength", 0, 1)
    _check_range(validator_instance, elevation_cfg, "shadow_softness", 0, 1)

    # Border
    _check_range(validator_instance, border_cfg, "border_width", 0, 2)

    # Motion
    _check_range(validator_instance, motion_cfg, "transition_duration", 120, 360)

    # --- Contrast checks ---

    bg = colors.get("background")
    if bg and isinstance(bg, str) and bg.startswith("#"):
        _check_contrast_pair(validator_instance, colors, "text", bg, 4.5,
                             "text on background")
        _check_contrast_pair(validator_instance, colors, "text_muted", bg, 3.0,
                             "text_muted on background")
        _check_contrast_pair(validator_instance, colors, "primary", bg, 4.5,
                             "primary on background", large_ok=3.0)
        _check_contrast_pair(validator_instance, colors, "accent", bg, 4.5,
                             "accent on background", large_ok=3.0)

    # Dark mode contrast
    dark_cfg = colors.get("dark", {})
    dark_bg = dark_cfg.get("background")
    if dark_bg and isinstance(dark_bg, str) and dark_bg.startswith("#"):
        _check_contrast_pair(validator_instance, dark_cfg, "text", dark_bg, 4.5,
                             "dark text on dark background")
        _check_contrast_pair(validator_instance, dark_cfg, "text_muted", dark_bg, 3.0,
                             "dark text_muted on dark background")
        _check_contrast_pair(validator_instance, dark_cfg, "primary", dark_bg, 4.5,
                             "dark primary on dark background", large_ok=3.0)
        _check_contrast_pair(validator_instance, dark_cfg, "accent", dark_bg, 4.5,
                             "dark accent on dark background", large_ok=3.0)


def _check_range(validator_instance, cfg: dict, key: str, min_val: float, max_val: float) -> None:
    """Check a numeric config value is within [min_val, max_val].

    validator_instance: DataValidator instance.
    cfg: config dict containing the key.
    key: the key to check in cfg.
    min_val: inclusive minimum.
    max_val: inclusive maximum.

    Returns: None.

    Side-effects: appends to validator_instance.errors if value is out of range.
    """

    value = cfg.get(key)
    if value is None:
        return
    if not isinstance(value, (int, float)):
        return
    if value < min_val or value > max_val:
        validator_instance.errors.append(
            f"❌ {key}: {value} is out of range [{min_val}, {max_val}]"
        )


def _check_contrast_pair(validator_instance, colors: dict, fg_key: str, bg_value: str,
                         required_ratio: float, label: str, large_ok: float = None) -> None:
    """Check WCAG contrast ratio for a foreground/background color pair.

    validator_instance: DataValidator instance.
    colors: dict from which to read the foreground color.
    fg_key: key in colors for the foreground color.
    bg_value: hex string for background.
    required_ratio: minimum ratio for normal text.
    label: human-readable label for error messages.
    large_ok: optional relaxed ratio for large text/UI elements.

    Returns: None.

    Side-effects: appends to validator_instance.errors if ratio is insufficient.
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
        validator_instance.errors.append(msg)


class DataValidator:
    """Validates site configuration and links data against JSON schemas."""

    def __init__(self, data_dir: Path, schemas_dir: Path):
        """Initialise the validator with explicit data and schema directory paths.

        data_dir: directory containing site.config.json, links.json, design.json.
        schemas_dir: directory containing *.schema.json files.
        """

        self.data_dir = data_dir
        self.schemas_dir = schemas_dir

        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.config_data: Dict = {}
        self.links_data: Dict = {}
        self.design_data: Dict = {}
        self.config_schema: Dict = {}
        self.links_schema: Dict = {}
        self.design_schema: Dict = {}

    def load_schemas(self) -> bool:
        """Load all JSON schema files from the schemas directory.

        Returns: True if all schemas loaded successfully, False otherwise.
        """

        config_schema_path = self.schemas_dir / "site.config.schema.json"
        links_schema_path = self.schemas_dir / "links.schema.json"
        design_schema_path = self.schemas_dir / "design.schema.json"

        try:
            self.config_schema = load_json(config_schema_path)
        except JsonLoadError as e:
            self.errors.append(f"❌ {e}")
            self.config_schema = {}
        try:
            self.links_schema = load_json(links_schema_path)
        except JsonLoadError as e:
            self.errors.append(f"❌ {e}")
            self.links_schema = {}
        try:
            self.design_schema = load_json(design_schema_path)
        except JsonLoadError as e:
            self.errors.append(f"❌ {e}")
            self.design_schema = {}

        if not self.config_schema or not self.links_schema or not self.design_schema:
            return False

        return True

    def load_data(self) -> bool:
        """Load all data files from the data directory.

        Returns: True if all files loaded successfully, False otherwise.
        """

        config_path = self.data_dir / "site.config.json"
        links_path = self.data_dir / "links.json"
        design_path = self.data_dir / "design.json"

        try:
            self.config_data = load_json(config_path)
        except JsonLoadError as e:
            self.errors.append(f"❌ {e}")
            self.config_data = {}
        try:
            self.links_data = load_json(links_path)
        except JsonLoadError as e:
            self.errors.append(f"❌ {e}")
            self.links_data = {}
        try:
            self.design_data = load_json(design_path)
        except JsonLoadError as e:
            self.errors.append(f"❌ {e}")
            self.design_data = {}

        if not self.config_data or not self.links_data or not self.design_data:
            return False

        return True

    def validate_effects(self):
        """Check for contradictory or ineffective effect and token combinations.

        Inspects card_style, hover_effect, and the new border/elevation tokens
        for known bad pairings. Appends warnings to self.warnings.

        Returns: None.

        Side-effects: appends to self.warnings.
        """

        effects = self.design_data.get("theme", {}).get("effects", {})
        if not effects:
            return  # all defaults, always fine

        card_style = effects.get("card_style", "image-overlay")
        hover_effect = effects.get("hover_effect", "lift")

        theme = self.design_data.get("theme", {})
        border_cfg = theme.get("border", {})
        border_width = border_cfg.get("border_width", 1)
        elevation_cfg = theme.get("elevation", {})
        shadow_strength = elevation_cfg.get("shadow_strength", 0.35)

        # elevated card_style with no shadows defeats the point
        if card_style == "elevated" and shadow_strength == 0:
            self.warnings.append(
                "⚠️ effects: card_style 'elevated' with elevation.shadow_strength 0 "
                "will render identically to 'flat' — consider shadow_strength ≥ 0.15."
            )

        # outlined card_style with border_width 0 is contradictory
        if card_style == "outlined" and border_width == 0:
            self.warnings.append(
                "⚠️ effects: card_style 'outlined' uses its own primary-color border — "
                "border.border_width 0 hides it completely. Set border_width ≥ 1."
            )

        # image-overlay with hover 'outline' is low contrast (outline on image)
        if card_style == "image-overlay" and hover_effect == "outline":
            self.warnings.append(
                "⚠️ effects: hover_effect 'outline' on card_style 'image-overlay' "
                "may have poor contrast against dark card backgrounds — consider 'glow'."
            )

    def validate_schema(self, data: Dict, schema: Dict, name: str) -> bool:
        """Validate a data dictionary against a JSON schema.

        data: the data to validate.
        schema: the JSON schema to validate against.
        name: human-readable label for error messages (e.g. file name).

        Returns: True if validation passes, False otherwise.

        SchemaError: caught internally, appended to self.errors. Raised if
            the schema itself is malformed.
        ValidationError: caught internally, appended to self.errors. Raised
            when data does not conform to the schema.
        """

        try:
            validate(instance=data, schema=schema)
            print(f"✅ {name} schema validation passed")
            return True
        except SchemaError as e:
            self.errors.append(f"❌ {name} schema is invalid: {e.message}")
            return False
        except ValidationError as e:
            self.errors.append(f"❌ {name} validation failed: {e.message}")
            self.errors.append(f"   Path: {' -> '.join(str(p) for p in e.path)}")
            return False

    def validate_fonts(self):
        """Check that every Google Font in the typography config is resolvable.

        Iterates over font_family and heading_font stacks, queries the
        Google Fonts API for each candidate, and records errors for any
        that cannot be found.

        Returns: None.

        Side-effects: prints status for each checked font.
        """

        from resourcery_ssg.font_acquirer import (
            find_first_downloadable,
            extract_google_font_candidates,
        )
        from resourcery_ssg.theme_constants import get_effective_weights, weights_to_api_param

        typography = self.design_data.get("theme", {}).get("typography", {})
        font_family = typography.get("font_family", "")
        heading_font = typography.get("heading_font", "")

        heading_style = (
            self.design_data.get("theme", {})
            .get("effects", {})
            .get("heading_style", "natural")
        )
        weights_param = weights_to_api_param(get_effective_weights(typography, heading_style))

        for field, stack in [
            ("font_family", font_family),
            ("heading_font", heading_font),
        ]:
            if not stack or not extract_google_font_candidates(stack):
                continue

            print(f"  Checking {field}...")
            font_name, _ = find_first_downloadable(stack, weights_param)

            if font_name is None:
                self.errors.append(
                    f"❌ typography.{field}: no valid Google Font found in stack '{stack}'. "
                    f"Verify font names at fonts.google.com"
                )
            else:
                print(f"  ✓ '{font_name}' found on Google Fonts")

    def extract_valid_categories(self) -> Set[str]:
        """Collect all valid category IDs from the navigation config.

        Includes both parent categories and their children.

        Returns: set of category ID strings.
        """

        valid_categories = set()

        categories = self.config_data.get("navigation", {}).get("categories", [])

        for category in categories:
            valid_categories.add(category["id"])

            children = category.get("children", [])
            for child in children:
                valid_categories.add(child["id"])

        return valid_categories

    def cross_validate(self) -> bool:
        """Validate links data against the site configuration.

        Checks: category IDs exist, no duplicate link IDs, active links have
        URLs, image paths are well-formed, menu links have valid schemes,
        and theme colour hex codes are valid.

        Returns: True if no errors (warnings alone do not fail).
        """

        if not self.config_data or not self.links_data:
            return False

        valid_categories = self.extract_valid_categories()
        valid_tags = set()
        link_ids = set()
        duplicate_ids = []

        # Validate links against config categories
        for link in self.links_data.get("links", []):
            link_id = link.get("id", "unknown")
            category = link.get("category", "")
            tags = link.get("tags", [])

            # Check for duplicate IDs
            if link_id in link_ids:
                duplicate_ids.append(link_id)
            link_ids.add(link_id)

            # Check category exists
            if category and category not in valid_categories:
                self.warnings.append(
                    f"⚠️  Link '{link_id}' uses unknown category '{category}'"
                )

            # Collect all tags
            valid_tags.update(tags)

            # Check for required fields based on status
            if link.get("status") == "active":
                if not link.get("url"):
                    self.warnings.append(f"⚠️  Active link '{link_id}' is missing URL")

            # Check image paths (basic validation)
            image = link.get("image")
            if image and not image.startswith(("http://", "https://", "/")):
                self.warnings.append(
                    f"⚠️  Link '{link_id}' has suspicious image path: '{image}'"
                )

        # Report duplicate IDs
        if duplicate_ids:
            self.errors.append(
                f"❌ Duplicate link IDs found: {', '.join(duplicate_ids)}"
            )

        # Validate config menu links
        for menu_link in self.config_data.get("navigation", {}).get("menu_links", []):
            url = menu_link.get("url", "")
            if not url.startswith(("http://", "https://", "mailto:", "/")):
                self.warnings.append(
                    f"⚠️  Menu link '{menu_link.get('label')}' has suspicious URL: '{url}'"
                )

        # Validate color hex codes in config (skip non-color fields like levers, overlay_strength)
        color_keys = {"primary", "secondary", "background", "surface", "text",
                       "text_muted", "accent", "error", "success"}
        colors = self.design_data.get("theme", {}).get("colors", {})
        for color_name, color_value in colors.items():
            if color_name in color_keys and not self._is_valid_hex_color(color_value):
                self.warnings.append(
                    f"⚠️  Invalid hex color for '{color_name}': '{color_value}'"
                )
            # Also check dark mode anchors
            if color_name == "dark" and isinstance(color_value, dict):
                for dk, dv in color_value.items():
                    if dk in color_keys and isinstance(dv, str) and not self._is_valid_hex_color(dv):
                        self.warnings.append(
                            f"⚠️  Invalid hex color for 'dark.{dk}': '{dv}'"
                        )

        # Report results
        if not self.warnings:
            print("✅ Cross-validation passed")
            return True
        else:
            print(
                f"⚠️  Cross-validation completed with {len(self.warnings)} warning(s)"
            )
            return True

    def _is_valid_hex_color(self, color: str) -> bool:
        """Check if a string is a valid 6-digit hex colour code.

        color: the string to check.

        Returns: True if the string matches the pattern #RRGGBB, False otherwise.
        """

        import re

        if not isinstance(color, str):
            return False
        return bool(re.match(r"^#[0-9a-fA-F]{6}$", color))

    def validate_all(self) -> bool:
        """Run all validation steps in sequence and print results.

        Order: load schemas, load data, validate schemas, cross-validate,
        validate effects, validate fonts.

        Returns: True if no errors were recorded, False otherwise.

        Side-effects: prints progress and summary to stdout.
        """

        print("🔍 Starting validation...\n")

        # Load schemas
        print("📄 Loading schemas...")
        if not self.load_schemas():
            print("\n❌ Failed to load schemas. Aborting.")
            return False

        # Load data
        print("📊 Loading data files...")
        if not self.load_data():
            print("\n❌ Failed to load data files. Aborting.")
            return False

        print()

        # Validate schemas
        print("🔒 Validating against JSON schemas...")
        config_valid = self.validate_schema(
            self.config_data, self.config_schema, "site.config.json"
        )
        links_valid = self.validate_schema(
            self.links_data, self.links_schema, "links.json"
        )
        design_valid = self.validate_schema(
            self.design_data, self.design_schema, "design.json"
        )

        print()

        # Cross-validation
        if config_valid and links_valid and design_valid:
            print("🔗 Running cross-validation checks...")
            cross_valid = self.cross_validate()
            print("🎨 Running design token validation...")
            validate_design_tokens(self)
            self.validate_effects()
            self.validate_fonts()
            print()
        else:
            cross_valid = False

        # Print results
        self._print_results()

        return not self.errors

    def _print_results(self):
        """Print a formatted summary of all errors and warnings.

        Returns: None.

        Side-effects: prints to stdout.
        """

        print("=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   {error}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ All validations passed! Ready for build.")
        elif not self.errors:
            print("\n✅ Validation passed with warnings. Build can proceed.")
        else:
            print("\n❌ Validation failed. Please fix errors before building.")

        print("=" * 60)


def main():
    """Run all validations and exit with the appropriate status code.

    Parses CLI arguments, loads configuration, and dispatches to DataValidator.

    Returns: None.

    SystemExit: 0 if all validations pass, 1 if any errors were found.
    """

    import argparse

    parser = argparse.ArgumentParser(description="Validate site data against JSON schemas")
    parser.add_argument("--data", type=str, default=None, help="Data directory")
    parser.add_argument("--schemas", type=str, default=None, help="Schemas directory")
    parser.add_argument("--config", type=str, default=None, help="Path to config YAML")
    args = parser.parse_args()

    from resourcery_ssg.config import load_resourcery_config, build_cli_overrides

    overrides = build_cli_overrides(
        args, "validate", {"data": "data_dir", "schemas": "schemas_dir"}
    )

    config = load_resourcery_config(
        config_path=args.config,
        overrides=overrides,
    )

    validator = DataValidator(**config["validate"])
    success = validator.validate_all()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
