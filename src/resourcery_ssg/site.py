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

import argparse
import shutil
import sys
from pathlib import Path


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

    # validate
    val_p = subparsers.add_parser("validate", help="Validate site data against schemas")
    val_p.add_argument("--data", type=str, default=None)
    val_p.add_argument("--schemas", type=str, default=None)

    # acquire-fonts
    fonts_p = subparsers.add_parser(
        "acquire-fonts", help="Acquire fonts from Google Fonts"
    )
    fonts_p.add_argument("--data", type=str, default=None)
    fonts_p.add_argument("--fonts-dir", type=str, default=None)
    fonts_p.add_argument("--css-dir", type=str, default=None)

    # acquire-images
    imgs_p = subparsers.add_parser(
        "acquire-images", help="Acquire images for links"
    )
    imgs_p.add_argument("--links", type=str, default=None)
    imgs_p.add_argument("--images-dir", type=str, default=None)
    imgs_p.add_argument("--force", action="store_true")

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
    "ingest": ["note", "site_prompt", "schemas_dir", "prompt", "model", "output_dir", "agent", "opencode_bin", "multi_step", "max_retries"],
}


def _extract_overrides(args, command: str, known_config_keys: list) -> dict:
    """Build a CLI overrides dict from parsed args for a specific command.

    Args:
        args: Parsed argparse namespace.
        command: The config section name (e.g. "build", "validate").
        known_config_keys: List of config key names to extract.

    Returns:
        Dict with dotted keys suitable for load_resourcery_config(overrides=...).
    """
    config_to_arg = {v: k for k, v in ARG_TO_CONFIG_KEY.items()}
    overrides = {}
    for config_key in known_config_keys:
        arg_name = config_to_arg.get(config_key)
        if arg_name and hasattr(args, arg_name):
            val = getattr(args, arg_name)
            if val is not None:
                overrides[f"{command}.{config_key}"] = val
    return overrides


def main():
    """Parse arguments, load config, and dispatch to the requested subcommand."""
    parser = _build_parser()
    args = parser.parse_args()

    from resourcery_ssg.config import load_resourcery_config

    if args.command == "all":
        _run_all(args)
        return

    if args.command not in COMMAND_FLAGS:
        parser.print_help()
        sys.exit(1)

    known_flags = COMMAND_FLAGS[args.command]
    overrides = _extract_overrides(args, args.command, known_flags)

    config = load_resourcery_config(
        config_path=args.config,
        overrides=overrides,
    )

    if args.command == "build":
        from resourcery_ssg.build import build_site

        build_site(**{k: v for k, v in config["build"].items() if k != "static_source"})

    elif args.command == "validate":
        from resourcery_ssg.validate import DataValidator

        validator = DataValidator(**config["validate"])
        success = validator.validate_all()
        sys.exit(0 if success else 1)

    elif args.command == "acquire-fonts":
        from resourcery_ssg.font_acquirer import acquire_fonts

        acquire_fonts(**config["acquire-fonts"])

    elif args.command == "acquire-images":
        from resourcery_ssg.image_acquirer import ImageAcquirer
        import json

        links_path = Path(config["acquire-images"]["links"])
        images_dir = Path(config["acquire-images"]["images_dir"])

        if not links_path.exists():
            print(f"❌ Links file not found: {links_path}")
            sys.exit(1)

        with open(links_path, "r", encoding="utf-8") as f:
            links_data = json.load(f)

        acquirer = ImageAcquirer(
            images_dir=images_dir,
            static_dir=config["build"]["static_dir"],
            links_path=links_path,
        )
        updated_data = acquirer.acquire_all(links_data, force=getattr(args, "force", False))

        backup_path = links_path.with_suffix(".json.bak")
        links_path.rename(backup_path)

        with open(links_path, "w", encoding="utf-8") as f:
            json.dump(updated_data, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Updated {links_path}")

    elif args.command == "ingest":
        _run_ingest(config)


def _run_ingest(config, args=None):
    """Run agentic data ingestion from the resolved config.

    Extracts ingest parameters from config["ingest"] and dispatches
    to ``run_ingestion``. Returns silently if no ``model`` is configured
    (ingestion is optional).

    Args:
        config: The resolved config dict (from load_resourcery_config).
        args: Optional argparse namespace (provides --debug and --opencode-path
            overrides not stored in config).
    """
    ingest_cfg = config.get("ingest")
    if not ingest_cfg:
        print("  ⚠️  No 'ingest' section in config — skipping ingestion")
        return

    model = ingest_cfg.get("model")
    if not model:
        print("  ⚠️  ingest.model not set — skipping ingestion")
        return

    note = ingest_cfg.get("note")
    site_prompt = ingest_cfg.get("site_prompt")
    if not note or not site_prompt:
        print(
            "  ⚠️  ingest.note and ingest.site_prompt are required — "
            "pass --note and --site-prompt on the command line",
            file=sys.stderr,
        )
        return

    from resourcery_ssg.data_ingestion import run_ingestion, run_multi_step_ingestion

    multi_step = ingest_cfg.get("multi_step", False)
    max_retries = ingest_cfg.get("max_retries", 3)
    opencode_bin = ingest_cfg.get("opencode_bin", "opencode")

    # Process stages configuration (per-stage overrides and selective execution)
    stages_cfg = ingest_cfg.get("stages")
    STAGE_KEYS = ["site.config", "links", "design"]

    stage_config = None
    requested_stages = None

    if stages_cfg and multi_step:
        # Validate stage keys
        for key in stages_cfg:
            if key not in STAGE_KEYS:
                print(
                    f"Error: Unknown stage key '{key}' in config.yaml ingest.stages. "
                    f"Valid keys are: {', '.join(STAGE_KEYS)}",
                    file=sys.stderr,
                )
                return

        # Build requested_stages in pipeline order
        requested_stages = [k for k in STAGE_KEYS if k in stages_cfg]

        # Build stage_config: only include stages that have actual overrides
        stage_config = {}
        for key in requested_stages:
            overrides = stages_cfg[key]
            if isinstance(overrides, dict) or hasattr(overrides, "items"):
                filtered = {k: v for k, v in overrides.items() if v is not None}
                if filtered:
                    stage_config[key] = filtered

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
    print("\n✓ Ingestion complete.")


def _seed_static_staging(config):
    """Copy base static assets from ``static_source`` to ``static_dir``.

    If the build section has a ``static_source`` key, only files and
    directories that do **not** already exist in the staging directory are
    copied.  This preserves generated content (acquired fonts, images,
    themed CSS) that was placed in the staging directory by earlier
    pipeline steps, while still making new base assets available.
    """
    build_cfg = config.get("build", {})
    source_raw = build_cfg.get("static_source")
    if not source_raw:
        return
    source = Path(source_raw)
    dest = Path(build_cfg["static_dir"])

    if not source.exists():
        print(f"  ⚠️  static_source not found: {source} — skipping")
        return

    print(f"  📦 Seeding static staging: {source} → {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.name == ".gitkeep":
            continue  # skip gitkeep files
        dst_path = dest / item.name
        if item.is_dir():
            # Merge: only copy items that don't already exist.
            # This preserves generated content (fonts, acquired images, etc.).
            dst_path.mkdir(exist_ok=True)
            for sub_item in item.iterdir():
                sub_dst = dst_path / sub_item.name
                if not sub_dst.exists():
                    if sub_item.is_dir():
                        shutil.copytree(sub_item, sub_dst)
                    else:
                        shutil.copy2(sub_item, sub_dst)
        else:
            if not dst_path.exists():
                shutil.copy2(item, dst_path)


def _run_all(args):
    """Run the full pipeline: ingest → validate → acquire-fonts → acquire-images → build.

    Ingestion is optional — skipped if no ``ingest.model`` is configured.
    Stops on first failure.
    """
    from resourcery_ssg.config import load_resourcery_config

    overrides = _extract_overrides(args, "build", COMMAND_FLAGS["build"])
    # Also extract flags for other commands — they share some flags with build
    overrides.update(
        _extract_overrides(args, "validate", COMMAND_FLAGS["validate"])
    )
    overrides.update(
        _extract_overrides(args, "acquire-fonts", COMMAND_FLAGS["acquire-fonts"])
    )
    overrides.update(
        _extract_overrides(args, "acquire-images", COMMAND_FLAGS["acquire-images"])
    )
    overrides.update(
        _extract_overrides(args, "ingest", COMMAND_FLAGS["ingest"])
    )

    config = load_resourcery_config(
        config_path=args.config,
        overrides=overrides,
    )

    # Seed the static staging directory from static_source (if configured).
    # This copies base static assets (js/, base images/, etc.) into the
    # staging dir so that acquire-fonts and acquire-images can add generated
    # files alongside them, and build can copy everything to the final output.
    _seed_static_staging(config)

    # Determine total steps (ingest is step 0 when configured)
    has_ingest = bool(config.get("ingest", {}).get("model"))
    total_steps = 5 if has_ingest else 4

    step = 0

    # Step 0: Ingest (optional)
    if has_ingest:
        step += 1
        print("\n" + "=" * 60)
        print(f"STEP {step}/{total_steps}: Ingest")
        print("=" * 60)
        _run_ingest(config, args)

    # 1. Validate
    step += 1
    print("\n" + "=" * 60)
    print(f"STEP {step}/{total_steps}: Validate")
    print("=" * 60)
    from resourcery_ssg.validate import DataValidator

    validator = DataValidator(**config["validate"])
    if not validator.validate_all():
        print("\n❌ Validation failed. Aborting pipeline.")
        sys.exit(1)
    print("\n✓ Validation passed.")

    # 2. Acquire fonts
    step += 1
    print("\n" + "=" * 60)
    print(f"STEP {step}/{total_steps}: Acquire fonts")
    print("=" * 60)
    from resourcery_ssg.font_acquirer import acquire_fonts

    try:
        acquire_fonts(**config["acquire-fonts"])
    except SystemExit as e:
        if e.code != 0:
            print("\n❌ Font acquisition failed. Aborting pipeline.")
            sys.exit(1)
    print("\n✓ Fonts acquired.")

    # 3. Acquire images
    step += 1
    print("\n" + "=" * 60)
    print(f"STEP {step}/{total_steps}: Acquire images")
    print("=" * 60)
    from resourcery_ssg.image_acquirer import ImageAcquirer
    import json

    links_path = Path(config["acquire-images"]["links"])
    images_dir = Path(config["acquire-images"]["images_dir"])

    if links_path.exists():
        with open(links_path, "r", encoding="utf-8") as f:
            links_data = json.load(f)

        acquirer = ImageAcquirer(
            images_dir=images_dir,
            static_dir=config["build"]["static_dir"],
            links_path=links_path,
        )
        updated_data = acquirer.acquire_all(links_data, force=getattr(args, "force", False))

        backup_path = links_path.with_suffix(".json.bak")
        links_path.rename(backup_path)

        with open(links_path, "w", encoding="utf-8") as f:
            json.dump(updated_data, f, indent=2, ensure_ascii=False)
        print("\n✓ Images acquired.")
    else:
        print(f"  ⚠️  Links file not found: {links_path} — skipping image acquisition")

    # 4. Build
    step += 1
    print("\n" + "=" * 60)
    print(f"STEP {step}/{total_steps}: Build")
    print("=" * 60)
    from resourcery_ssg.build import build_site

    build_kwargs = {k: v for k, v in config["build"].items() if k != "static_source"}
    build_site(**build_kwargs)
    print("\n✅ Pipeline complete!")


if __name__ == "__main__":
    main()
