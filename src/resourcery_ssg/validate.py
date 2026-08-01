#!/usr/bin/env python3
"""
Validation script for Static Link Aggregation Website.
Validates data files against JSON schemas and performs cross-validation.
"""

import logging
import sys
from pathlib import Path
from jsonschema import validate, ValidationError, SchemaError
from typing import Dict, List

from resourcery_ssg.design_checks import (
    validate_cross_references,
    validate_design_tokens,
    validate_effects,
)
from resourcery_ssg.io_utils import load_json, JsonLoadError
from resourcery_ssg.logutil import get_logger, log_user, log_timing

logger = get_logger(__name__)


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

        logger.info(
            f"Loaded {len([s for s in (self.config_schema, self.links_schema, self.design_schema) if s])} schemas"
        )
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
            logger.debug(f"Loaded {config_path} ({len(self.config_data)} records)")
        except JsonLoadError as e:
            self.errors.append(f"❌ {e}")
            self.config_data = {}
        try:
            self.links_data = load_json(links_path)
            logger.debug(
                f"Loaded {links_path} ({len(self.links_data.get('links', []))} records)"
            )
        except JsonLoadError as e:
            self.errors.append(f"❌ {e}")
            self.links_data = {}
        try:
            self.design_data = load_json(design_path)
            logger.debug(f"Loaded {design_path} ({len(self.design_data)} records)")
        except JsonLoadError as e:
            self.errors.append(f"❌ {e}")
            self.design_data = {}

        if not self.config_data or not self.links_data or not self.design_data:
            return False

        return True

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
            log_user(f"✅ {name} schema validation passed")
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

        Side-effects: logs status at INFO_USER for each checked font.
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

            log_user(f"  Checking {field}...")
            candidates = extract_google_font_candidates(stack)
            font_name, _ = find_first_downloadable(stack, weights_param)

            if font_name is None:
                logger.debug(f"Font '{candidates[0]}' availability: missing")
                self.errors.append(
                    f"❌ typography.{field}: no valid Google Font found in stack '{stack}'. "
                    f"Verify font names at fonts.google.com"
                )
            else:
                logger.debug(f"Font '{candidates[0]}' availability: found")
                log_user(f"  ✓ '{font_name}' found on Google Fonts")

    def cross_validate(self) -> bool:
        """Validate links data against the site configuration.

        Checks: category IDs exist, no duplicate link IDs, active links have
        URLs, image paths are well-formed, menu links have valid schemes,
        and theme colour hex codes are valid. The checks themselves run via
        design_checks.validate_cross_references; this method owns the IO
        state access, the log_user reporting, and the return contract.

        Returns: True if no errors (warnings alone do not fail).
        """

        if not self.config_data or not self.links_data:
            return False

        errors, warnings = validate_cross_references(
            self.config_data, self.links_data, self.design_data
        )
        self.errors.extend(errors)
        self.warnings.extend(warnings)

        if not self.warnings:
            log_user("✅ Cross-validation passed")
            return True
        else:
            log_user(
                f"⚠️  Cross-validation completed with {len(self.warnings)} warning(s)"
            )
            return True

    def validate_all(self) -> bool:
        """Run all validation steps in sequence and print results.

        Order: load schemas, load data, validate schemas, cross-validate,
        validate effects, validate fonts. Design checks (tokens, effects,
        cross-references) run via design_checks.

        Returns: True if no errors were recorded, False otherwise.

        Side-effects: logs progress at INFO_USER and findings at WARN.
        """

        log_user("🔍 Starting validation...\n")

        # Load schemas
        log_user("📄 Loading schemas...")
        if not self.load_schemas():
            logger.error("\n❌ Failed to load schemas. Aborting.")
            return False

        # Load data
        log_user("📊 Loading data files...")
        if not self.load_data():
            logger.error("\n❌ Failed to load data files. Aborting.")
            return False
        logger.info(
            f"Validated {len([d for d in (self.config_data, self.links_data, self.design_data) if d])} data files "
            f"({len(self.links_data.get('links', []))} links)"
        )

        log_user("")

        # Validate schemas
        log_user("🔒 Validating against JSON schemas...")
        config_valid = self.validate_schema(
            self.config_data, self.config_schema, "site.config.json"
        )
        links_valid = self.validate_schema(
            self.links_data, self.links_schema, "links.json"
        )
        design_valid = self.validate_schema(
            self.design_data, self.design_schema, "design.json"
        )

        log_user("")

        # Cross-validation
        if config_valid and links_valid and design_valid:
            log_user("🔗 Running cross-validation checks...")
            cross_valid = self.cross_validate()
            log_user("🎨 Running design token validation...")
            token_errors, token_warnings = validate_design_tokens(self.design_data)
            self.errors.extend(token_errors)
            self.warnings.extend(token_warnings)
            effect_errors, effect_warnings = validate_effects(self.design_data)
            self.errors.extend(effect_errors)
            self.warnings.extend(effect_warnings)
            logger.debug("Cross-check: fonts start")
            self.validate_fonts()
            logger.info(
                "Cross-checks passed: categories, tags, ids, colors, urls, fonts"
            )
            log_user("")
        else:
            cross_valid = False

        # Print results
        self._print_results()

        return not self.errors

    def _print_results(self):
        """Print a formatted summary of all errors and warnings.

        Returns: None.

        Side-effects: logs the summary at INFO_USER (findings at WARN).
        """

        logger.info(f"{len(self.warnings)} warnings, {len(self.errors)} errors collected")

        log_user("=" * 60)
        log_user("VALIDATION SUMMARY")
        log_user("=" * 60)

        if self.errors:
            logger.warning(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                logger.warning(f"   {error}")

        if self.warnings:
            logger.warning(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.warning(f"   {warning}")

        if not self.errors and not self.warnings:
            log_user("\n✅ All validations passed! Ready for build.")
        elif not self.errors:
            log_user("\n✅ Validation passed with warnings. Build can proceed.")
        else:
            logger.warning("\n❌ Validation failed. Please fix errors before building.")

        log_user("=" * 60)


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
    parser.add_argument(
        "--log-level", type=str, default=None,
        help="Console log level: DEBUG|INFO|WARN|ERROR (case-insensitive)",
    )
    args = parser.parse_args()

    from resourcery_ssg.config import load_resourcery_config, build_cli_overrides
    from resourcery_ssg.logutil import setup_logging

    overrides = build_cli_overrides(
        args, "validate", {"data": "data_dir", "schemas": "schemas_dir"}
    )
    if args.log_level:
        overrides["logging.level"] = args.log_level

    config = load_resourcery_config(
        config_path=args.config,
        overrides=overrides,
    )
    setup_logging(config)

    with log_timing(logger, "Command", level=logging.INFO):
        validator = DataValidator(**config["validate"])
        success = validator.validate_all()

        # Exit with appropriate code
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
