#!/usr/bin/env python3
"""
Coordinator entry point with subcommand dispatch.

Provides a unified ``site`` CLI that reads ``config.yaml`` once and dispatches
to the appropriate command module. Supports:

    site build <args>
    site validate <args>
    site acquire-fonts <args>
    site acquire-images <args>
    site ingest <args>
    site all <args>
"""

import logging
import argparse
import os
import shutil
import sys
from pathlib import Path

from resourcery_ssg.errors import ResourceryError
from resourcery_ssg.logutil import get_logger, log_timing, log_user

logger = get_logger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="Resourcery.ssg — static link aggregation site generator"
    )
    parser.add_argument(
        "--config", type=str, default=None, help="Path to config YAML file"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # build
    build_p = subparsers.add_parser("build", help="Build the static site")
    build_p.add_argument("--data", type=str, default=None)
    build_p.add_argument("--templates", type=str, default=None)
    build_p.add_argument("--static", type=str, default=None)
    build_p.add_argument("--output", type=str, default=None)
    build_p.add_argument(
        "--log-level", type=str, default=None,
        help="Console log level: DEBUG|INFO|WARN|ERROR (case-insensitive)",
    )

    # validate
    val_p = subparsers.add_parser("validate", help="Validate site data against schemas")
    val_p.add_argument("--data", type=str, default=None)
    val_p.add_argument("--schemas", type=str, default=None)
    val_p.add_argument(
        "--log-level", type=str, default=None,
        help="Console log level: DEBUG|INFO|WARN|ERROR (case-insensitive)",
    )

    # acquire-fonts
    fonts_p = subparsers.add_parser(
        "acquire-fonts", help="Acquire fonts from Google Fonts"
    )
    fonts_p.add_argument("--data", type=str, default=None)
    fonts_p.add_argument("--fonts-dir", type=str, default=None)
    fonts_p.add_argument("--css-dir", type=str, default=None)
    fonts_p.add_argument(
        "--log-level", type=str, default=None,
        help="Console log level: DEBUG|INFO|WARN|ERROR (case-insensitive)",
    )

    # acquire-js
    acquire_js_p = subparsers.add_parser(
        "acquire-js", help="Acquire the Nanostores JS library"
    )
    acquire_js_p.add_argument("--package-json", type=str, default=None)
    acquire_js_p.add_argument("--vendor-dir", type=str, default=None)
    acquire_js_p.add_argument(
        "--log-level", type=str, default=None,
        help="Console log level: DEBUG|INFO|WARN|ERROR (case-insensitive)",
    )

    # acquire-images
    imgs_p = subparsers.add_parser(
        "acquire-images", help="Acquire images for links"
    )
    imgs_p.add_argument("--links", type=str, default=None)
    imgs_p.add_argument("--images-dir", type=str, default=None)
    imgs_p.add_argument("--force", action="store_true")
    imgs_p.add_argument(
        "--log-level", type=str, default=None,
        help="Console log level: DEBUG|INFO|WARN|ERROR (case-insensitive)",
    )

    # ingest
    ingest_p = subparsers.add_parser(
        "ingest", help="Run agentic data ingestion (requires --model)"
    )
    ingest_p.add_argument("--note", type=str, default=None)
    ingest_p.add_argument("--site-prompt", type=str, default=None)
    ingest_p.add_argument("--schemas", type=str, default=None)
    ingest_p.add_argument("--prompt", type=str, default=None)
    ingest_p.add_argument("--model", type=str, default=None)
    ingest_p.add_argument("--output", type=str, default=None)
    ingest_p.add_argument("--agent", type=str, default=None)
    ingest_p.add_argument("--opencode-path", type=str, default=None)
    ingest_p.add_argument("--debug", action="store_true")
    ingest_p.add_argument("--multi-step", action="store_true", default=None)
    ingest_p.add_argument("--max-retries", type=int, default=None)
    ingest_p.add_argument(
        "--log-level", type=str, default=None,
        help="Console log level: DEBUG|INFO|WARN|ERROR (case-insensitive)",
    )

    # all
    all_p = subparsers.add_parser(
        "all", help="Run ingest → validate → acquire-fonts → acquire-images → build"
    )
    all_p.add_argument("--data", type=str, default=None)
    all_p.add_argument("--templates", type=str, default=None)
    all_p.add_argument("--static", type=str, default=None)
    all_p.add_argument("--output", type=str, default=None)
    all_p.add_argument("--schemas", type=str, default=None)
    all_p.add_argument("--fonts-dir", type=str, default=None)
    all_p.add_argument("--css-dir", type=str, default=None)
    all_p.add_argument("--links", type=str, default=None)
    all_p.add_argument("--images-dir", type=str, default=None)
    all_p.add_argument("--force", action="store_true")
    # acquire-js flags for "all"
    all_p.add_argument("--package-json", type=str, default=None)
    all_p.add_argument("--vendor-dir", type=str, default=None)

    # ingest flags for "all"
    all_p.add_argument("--note", type=str, default=None)
    all_p.add_argument("--site-prompt", type=str, default=None)
    all_p.add_argument("--prompt", type=str, default=None)
    all_p.add_argument("--model", type=str, default=None)
    all_p.add_argument("--agent", type=str, default=None)
    all_p.add_argument("--opencode-path", type=str, default=None)
    all_p.add_argument("--debug", action="store_true")
    all_p.add_argument("--multi-step", action="store_true", default=None)
    all_p.add_argument("--max-retries", type=int, default=None)
    all_p.add_argument(
        "--log-level", type=str, default=None,
        help="Console log level: DEBUG|INFO|WARN|ERROR (case-insensitive)",
    )

    return parser


# Mapping from argparse attribute name to config key name.
# argparse converts --data to args.data, --fonts-dir to args.fonts_dir, etc.
ARG_TO_CONFIG_KEY = {
    "data": "data_dir",
    "templates": "templates_dir",
    "static": "static_dir",
    "output": "output_dir",
    "schemas": "schemas_dir",
    "fonts_dir": "fonts_dir",
    "css_dir": "css_dir",
    "links": "links",
    "images_dir": "images_dir",
    "package_json": "package_json_path",
    "vendor_dir": "vendor_dir",
    "note": "note",
    "site_prompt": "site_prompt",
    "prompt": "prompt",
    "model": "model",
    "agent": "agent",
    "opencode_path": "opencode_bin",
    "multi_step": "multi_step",
    "max_retries": "max_retries",
}

# Per-command config key names
COMMAND_FLAGS = {
    "build": ["data_dir", "templates_dir", "static_dir", "output_dir"],
    "validate": ["data_dir", "schemas_dir"],
    "acquire-fonts": ["data_dir", "fonts_dir", "css_dir"],
    "acquire-images": ["links", "images_dir"],
    "acquire-js": ["package_json_path", "vendor_dir"],
    "ingest": ["note", "site_prompt", "schemas_dir", "prompt", "model", "output_dir", "agent", "opencode_bin", "multi_step", "max_retries"],
}


def _logging_override(args) -> dict:
    """Dotted-key override for the --log-level flag.

    The ``logging`` section sits outside the command-scoped
    ``ARG_TO_CONFIG_KEY``/``COMMAND_FLAGS`` mapping, so it needs its own
    section prefix.
    """
    value = getattr(args, "log_level", None)
    return {"logging.level": value} if value else {}


def main():
    """Parse arguments, load config, and dispatch to the requested subcommand."""
    parser = _build_parser()
    args = parser.parse_args()

    from resourcery_ssg.config import load_resourcery_config, build_cli_overrides
    from resourcery_ssg.logutil import setup_logging

    with log_timing(logger, "Command", level=logging.INFO):
        try:
            if args.command == "all":
                _run_all(args)
                return

            if args.command not in COMMAND_FLAGS:
                parser.print_help()
                sys.exit(1)

            known_flags = COMMAND_FLAGS[args.command]
            flag_to_key = {
                arg: key for arg, key in ARG_TO_CONFIG_KEY.items() if key in known_flags
            }
            overrides = build_cli_overrides(args, args.command, flag_to_key)
            overrides.update(_logging_override(args))

            config = load_resourcery_config(
                config_path=args.config,
                overrides=overrides,
            )
            setup_logging(config)
            config_path_label = (
                f"config {args.config}" if args.config else "committed defaults"
            )
            logger.info(f"Dispatch: {args.command} ({config_path_label})")
            if overrides:
                pairs = ", ".join(f"{k}={v}" for k, v in sorted(overrides.items()))
                logger.debug(f"Config overrides: {pairs}")

            if args.command == "build":
                from resourcery_ssg.build import build_site

                _seed_static_staging(config)
                build_site(**{k: v for k, v in config["build"].items() if k != "static_source"},
                           ingest_note=config.get("ingest", {}).get("note"),
                           ingest_site_prompt=config.get("ingest", {}).get("site_prompt"))

            elif args.command == "validate":
                from resourcery_ssg.validate import DataValidator

                validator = DataValidator(**config["validate"])
                success = validator.validate_all()
                sys.exit(0 if success else 1)

            elif args.command == "acquire-fonts":
                from resourcery_ssg.font_acquirer import acquire_fonts

                acquire_fonts(**config["acquire-fonts"])

            elif args.command == "acquire-images":
                from resourcery_ssg.image_acquirer import acquire_images_from_config

                sys.exit(0 if acquire_images_from_config(config, force=args.force) else 1)

            elif args.command == "acquire-js":
                from resourcery_ssg.js_vendor import acquire_js
                acquire_js(**config["acquire-js"])

            elif args.command == "ingest":
                _run_ingest(config)
        except ResourceryError:
            sys.exit(1)


def _run_ingest(config, args=None):
    """Run agentic data ingestion from the resolved config.

    Extracts ingest parameters from config["ingest"] and dispatches
    to ``run_ingestion``. Returns silently if no ``model`` is configured
    (ingestion is optional).

    Args:
        config: The resolved config dict (from load_resourcery_config).
        args: Optional argparse namespace (provides --debug and --opencode-path
            overrides not stored in config).

    ResourceryError: when required ingest inputs (note/site_prompt, or path
        keys) are missing or a referenced input path does not exist;
        propagates from build_stage_config on unknown stage keys.
    """
    ingest_cfg = config.get("ingest")
    if not ingest_cfg:
        logger.warning("  ⚠️  No 'ingest' section in config — skipping ingestion")
        return

    model = ingest_cfg.get("model")
    if not model:
        logger.warning("  ⚠️  ingest.model not set — skipping ingestion")
        return

    note = ingest_cfg.get("note")
    site_prompt = ingest_cfg.get("site_prompt")
    if not note or not site_prompt:
        msg = (
            "  ⚠️  ingest.note and ingest.site_prompt are required — "
            "pass --note and --site-prompt on the command line"
        )
        logger.error(msg)
        raise ResourceryError(msg)

    # Validate that all referenced input paths exist before dispatching.
    # Without this, a missing file (e.g. a deleted note) surfaces as a raw
    # FileNotFoundError traceback from Path(...).resolve(strict=True) inside
    # run_ingestion/run_multi_step_ingestion, and a missing key would raise
    # KeyError at dispatch. Mirrors data_ingestion.main()'s validation.
    for path_value, label in [
        (note, "note"),
        (site_prompt, "site_prompt"),
        (ingest_cfg.get("schemas_dir"), "schemas_dir"),
        (ingest_cfg.get("prompt"), "prompt"),
    ]:
        if not path_value:
            msg = f"Error: {label} is required (and not set in config.yaml)"
            logger.error(msg)
            raise ResourceryError(msg)
        if not Path(path_value).exists():
            msg = f"Error: {label} path does not exist: {path_value}"
            logger.error(msg)
            raise ResourceryError(msg)

    from resourcery_ssg.data_ingestion import (
        run_ingestion,
        run_multi_step_ingestion,
        build_stage_config,
    )

    multi_step = ingest_cfg.get("multi_step", False)
    max_retries = ingest_cfg.get("max_retries", 3)
    opencode_bin = ingest_cfg.get("opencode_bin", "opencode")

    # Process stages configuration (per-stage overrides and selective execution)
    stages_cfg = ingest_cfg.get("stages")
    stage_config, requested_stages = build_stage_config(
        stages_cfg, multi_step=multi_step
    )

    if multi_step:
        prompts_dir = Path(ingest_cfg["prompt"]).resolve().parent
        run_multi_step_ingestion(
            note_path=Path(note),
            site_prompt_path=Path(site_prompt),
            schemas_dir=Path(ingest_cfg["schemas_dir"]),
            prompts_dir=prompts_dir,
            global_model=model,
            output_dir=Path(ingest_cfg["output_dir"]),
            global_max_retries=max_retries,
            stage_config=stage_config,
            requested_stages=requested_stages,
            opencode_bin=opencode_bin,
            debug=getattr(args, "debug", False) or ingest_cfg.get("debug", False),
        )
    else:
        run_ingestion(
            note_path=Path(note),
            site_prompt_path=Path(site_prompt),
            schemas_dir=Path(ingest_cfg["schemas_dir"]),
            prompt_path=Path(ingest_cfg["prompt"]),
            model=model,
            output_dir=Path(ingest_cfg["output_dir"]),
            opencode_bin=opencode_bin,
            debug=getattr(args, "debug", False) or ingest_cfg.get("debug", False),
        )
    log_user("\n✓ Ingestion complete.")


def _seed_static_staging(config):
    """Copy base static assets from ``static_source`` to ``static_dir``.

    Files from the source always overwrite corresponding files in the staging
    directory.  Generated content (acquired fonts, images) lives in
    subdirectories (fonts/, images/) that typically do not exist in the base
    static_source, so they are preserved automatically.  If they do exist
    in the source, the source version wins — rebuild means rebuild.
    """
    build_cfg = config.get("build", {})
    source_raw = build_cfg.get("static_source")
    if not source_raw:
        return
    source = Path(source_raw)
    dest = Path(build_cfg["static_dir"])

    if not source.exists():
        logger.warning(f"  ⚠️  static_source not found: {source} — skipping")
        return

    log_user(f"  📦 Seeding static staging: {source} → {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    n_files = 0
    for item in source.iterdir():
        if item.name == ".gitkeep":
            continue  # skip gitkeep files
        dst_path = dest / item.name
        if item.is_dir():
            dst_path.mkdir(exist_ok=True)
            for sub_item in item.iterdir():
                sub_dst = dst_path / sub_item.name
                if sub_item.is_dir():
                    n_files += sum(
                        len(files) for _, _, files in os.walk(sub_item)
                    )
                    shutil.copytree(sub_item, sub_dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(sub_item, sub_dst)
                    n_files += 1
        else:
            shutil.copy2(item, dst_path)
            n_files += 1
    logger.debug(f"Staging: seeded {source} → {dest} ({n_files} files)")


def _run_all(args):
    """Run the full pipeline: ingest → validate → acquire-fonts → acquire-images → build.

    Ingestion is optional — skipped if no ``ingest.model`` is configured.
    Stops on first failure.
    """
    from resourcery_ssg.config import load_resourcery_config, build_cli_overrides
    from resourcery_ssg.logutil import setup_logging

    def _flag_to_key(command):
        known_keys = COMMAND_FLAGS[command]
        return {arg: key for arg, key in ARG_TO_CONFIG_KEY.items() if key in known_keys}

    overrides = build_cli_overrides(args, "build", _flag_to_key("build"))
    # Also extract flags for other commands — they share some flags with build
    overrides.update(
        build_cli_overrides(args, "validate", _flag_to_key("validate"))
    )
    overrides.update(
        build_cli_overrides(args, "acquire-fonts", _flag_to_key("acquire-fonts"))
    )
    overrides.update(
        build_cli_overrides(args, "acquire-images", _flag_to_key("acquire-images"))
    )
    overrides.update(
        build_cli_overrides(args, "ingest", _flag_to_key("ingest"))
    )
    overrides.update(
        build_cli_overrides(args, "acquire-js", _flag_to_key("acquire-js"))
    )
    overrides.update(_logging_override(args))

    config = load_resourcery_config(
        config_path=args.config,
        overrides=overrides,
    )
    setup_logging(config)
    config_path_label = f"config {args.config}" if args.config else "committed defaults"
    logger.info(f"Dispatch: {args.command} ({config_path_label})")
    if overrides:
        pairs = ", ".join(f"{k}={v}" for k, v in sorted(overrides.items()))
        logger.debug(f"Config overrides: {pairs}")

    # Seed the static staging directory from static_source (if configured).
    # This copies base static assets (js/, base images/, etc.) into the
    # staging dir so that acquire-fonts and acquire-images can add generated
    # files alongside them, and build can copy everything to the final output.
    _seed_static_staging(config)

    # Determine total steps (ingest is step 0 when configured)
    has_ingest = bool(config.get("ingest", {}).get("model"))
    total_steps = 6 if has_ingest else 5

    step = 0

    # Step 0: Ingest (optional)
    if has_ingest:
        step += 1
        log_user("\n" + "=" * 60)
        log_user(f"STEP {step}/{total_steps}: Ingest")
        log_user("=" * 60)
        with log_timing(logger, "Step 'ingest'"):
            _run_ingest(config, args)

    # 1. Validate
    step += 1
    log_user("\n" + "=" * 60)
    log_user(f"STEP {step}/{total_steps}: Validate")
    log_user("=" * 60)
    from resourcery_ssg.validate import DataValidator

    validator = DataValidator(**config["validate"])
    with log_timing(logger, "Step 'validate'"):
        validation_ok = validator.validate_all()
    if not validation_ok:
        logger.error("\n❌ Validation failed. Aborting pipeline.")
        sys.exit(1)
    log_user("\n✓ Validation passed.")

    # 2. Acquire fonts
    step += 1
    log_user("\n" + "=" * 60)
    log_user(f"STEP {step}/{total_steps}: Acquire fonts")
    log_user("=" * 60)
    from resourcery_ssg.font_acquirer import acquire_fonts

    try:
        with log_timing(logger, "Step 'acquire-fonts'"):
            acquire_fonts(**config["acquire-fonts"])
    except ResourceryError:
        logger.error("\n❌ Font acquisition failed. Aborting pipeline.")
        sys.exit(1)
    log_user("\n✓ Fonts acquired.")

    # 3. Acquire JS
    step += 1
    log_user("\n" + "=" * 60)
    log_user(f"STEP {step}/{total_steps}: Acquire JS")
    log_user("=" * 60)
    from resourcery_ssg.js_vendor import acquire_js
    with log_timing(logger, "Step 'acquire-js'"):
        acquire_js()
    log_user("\n✓ JS vendor file acquired.")

    # 4. Acquire images
    step += 1
    log_user("\n" + "=" * 60)
    log_user(f"STEP {step}/{total_steps}: Acquire images")
    log_user("=" * 60)
    from resourcery_ssg.image_acquirer import acquire_images_from_config

    with log_timing(logger, "Step 'acquire-images'"):
        acquire_images_from_config(config, force=getattr(args, "force", False))

    # 5. Build
    step += 1
    log_user("\n" + "=" * 60)
    log_user(f"STEP {step}/{total_steps}: Build")
    log_user("=" * 60)
    from resourcery_ssg.build import build_site

    build_kwargs = {k: v for k, v in config["build"].items() if k != "static_source"}
    build_kwargs["ingest_note"] = config.get("ingest", {}).get("note")
    build_kwargs["ingest_site_prompt"] = config.get("ingest", {}).get("site_prompt")
    with log_timing(logger, "Step 'build'"):
        build_site(**build_kwargs)
    log_user("\n✅ Pipeline complete!")


if __name__ == "__main__":
    main()
