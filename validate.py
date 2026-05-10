#!/usr/bin/env python3
"""
Validation script for Static Link Aggregation Website.
Validates data files against JSON schemas and performs cross-validation.
"""

import json
import sys
from pathlib import Path
from jsonschema import validate, ValidationError, SchemaError
from typing import Dict, List, Set, Tuple, Any


class DataValidator:
    """Validates site configuration and links data against JSON schemas."""

    def __init__(self, root_dir: Path = None):
        """Initialise the validator with project root and data/schema directory paths.

        root_dir: project root directory. Defaults to the directory containing this file.
        """

        self.root_dir = root_dir or Path(__file__).parent
        self.data_dir = self.root_dir / "data"
        self.schemas_dir = self.root_dir / "schemas"

        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.config_data: Dict = {}
        self.links_data: Dict = {}
        self.config_schema: Dict = {}
        self.links_schema: Dict = {}

    def load_json(self, path: Path) -> Dict:
        """Load and parse a JSON file, recording errors on failure.

        path: filesystem path to the JSON file.

        Returns: parsed dictionary, or an empty dict on failure.

        FileNotFoundError: caught internally, appended to self.errors.
        json.JSONDecodeError: caught internally, appended to self.errors.
        """

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self.errors.append(f"❌ File not found: {path}")
            return {}
        except json.JSONDecodeError as e:
            self.errors.append(f"❌ Invalid JSON in {path}: {e}")
            return {}

    def load_schemas(self) -> bool:
        """Load both JSON schema files from the schemas directory.

        Returns: True if both schemas loaded successfully, False otherwise.
        """

        config_schema_path = self.schemas_dir / "site.config.schema.json"
        links_schema_path = self.schemas_dir / "links.schema.json"

        self.config_schema = self.load_json(config_schema_path)
        self.links_schema = self.load_json(links_schema_path)

        if not self.config_schema or not self.links_schema:
            return False

        return True

    def load_data(self) -> bool:
        """Load both data files from the data directory.

        Returns: True if both files loaded successfully, False otherwise.
        """

        config_path = self.data_dir / "site.config.json"
        links_path = self.data_dir / "links.json"

        self.config_data = self.load_json(config_path)
        self.links_data = self.load_json(links_path)

        if not self.config_data or not self.links_data:
            return False

        return True

    def validate_effects(self):
        """Check for contradictory or ineffective effect combinations.

        Inspects card_style, shadow_intensity, hover_effect, and
        border_treatment for known bad pairings. Appends warnings to
        self.warnings rather than raising.

        Returns: None.

        Side-effects: appends to self.warnings.
        """

        effects = self.config_data.get("theme", {}).get("effects", {})
        if not effects:
            return  # all defaults, always fine

        card_style = effects.get("card_style", "image-overlay")
        shadow_intensity = effects.get("shadow_intensity", "subtle")
        hover_effect = effects.get("hover_effect", "lift")
        border_treatment = effects.get("border_treatment", "hairline")

        # elevated card_style with no shadows defeats the entire point
        if card_style == "elevated" and shadow_intensity == "none":
            self.warnings.append(
                "⚠️ effects: card_style 'elevated' with shadow_intensity 'none' "
                "will render identically to 'flat' — consider 'medium' or 'dramatic'."
            )

        # outlined card_style overrides its own border, border_treatment is irrelevant
        if card_style == "outlined" and border_treatment in ("none", "hairline"):
            self.warnings.append(
                "⚠️ effects: card_style 'outlined' uses its own primary-color border — "
                "border_treatment 'none'/'hairline' has no visible effect on cards."
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

        from font_acquirer import (
            find_first_downloadable,
            extract_google_font_candidates,
        )
        from theme_constants import get_required_weights, weights_to_api_param

        typography = self.config_data.get("theme", {}).get("typography", {})
        font_family = typography.get("font_family", "")
        heading_font = typography.get("heading_font", "")

        heading_style = (
            self.config_data.get("theme", {})
            .get("effects", {})
            .get("heading_style", "natural")
        )
        weights_param = weights_to_api_param(get_required_weights(heading_style))

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

        # Validate color hex codes in config
        colors = self.config_data.get("theme", {}).get("colors", {})
        for color_name, color_value in colors.items():
            if not self._is_valid_hex_color(color_value):
                self.warnings.append(
                    f"⚠️  Invalid hex color for '{color_name}': '{color_value}'"
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

        print()

        # Cross-validation
        if config_valid and links_valid:
            print("🔗 Running cross-validation checks...")
            cross_valid = self.cross_validate()
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

    Returns: None.

    SystemExit: 0 if all validations pass, 1 if any errors were found.
    """

    validator = DataValidator()
    success = validator.validate_all()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
