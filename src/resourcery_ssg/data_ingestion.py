#!/usr/bin/env python3
"""
CLI tool for agentic data ingestion and enrichment.

Orchestrates opencode as an LLM agent to transform raw markdown notes into
structured JSON files (links.json, site.config.json, design.json) that
validate against the project's JSON Schemas.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from resourcery_ssg.errors import ResourceryError
from resourcery_ssg.io_utils import loads_json, JsonLoadError
from resourcery_ssg.validate import DataValidator


# Expected output files
REQUIRED_OUTPUTS = ["links.json", "site.config.json", "design.json"]

# Schema file names
SCHEMA_FILES = [
    "links.schema.json",
    "site.config.schema.json",
    "design.schema.json",
]

# Default timeout for the opencode subprocess (seconds)
OPENCODE_TIMEOUT = 300


def _generate_agent_def(work_dir: str, schemas_dir: str) -> str:
    """Generate a scoped agent definition for the ingestion run.

    work_dir: absolute path to the temp working directory (write scope).
    schemas_dir: absolute path to the schemas directory (read scope).

    Returns: agent definition as a YAML-frontmatter markdown string.
    """
    return f"""---
name: data-ingestion
description: Data ingestion agent
mode: primary
permission:
  read:
    "{schemas_dir}/**": allow
  write:
    "{work_dir}/**": allow
  edit:
    "{work_dir}/**": allow
  bash:
    "{work_dir}/**": allow
  webfetch: allow
  websearch: allow
---

You are a data ingestion agent. Read the instruction carefully, use the inlined schemas to understand the required output format, and generate the three output files (links.json, site.config.json, design.json) at the exact absolute paths specified in the instruction. Use the write tool. Do not ask questions — produce the output files.
"""


def _read_file(path: Path) -> str:
    """Read a text file and return its contents.

    path: filesystem path to the file.

    Returns: file contents as a string.

    FileNotFoundError: raised if the file does not exist.
    """
    return path.read_text(encoding="utf-8")


def _generate_step_agent_def(
    work_dir: str, schemas_dir: str, step_name: str, output_file: str
) -> str:
    """Generate a scoped agent definition for a single ingestion step.

    work_dir: absolute path to the temp working directory (write scope).
    schemas_dir: absolute path to the schemas directory (read scope).
    step_name: short label for the step (e.g. 'site-config', 'links', 'design').
    output_file: the single output file this step generates (e.g. 'site.config.json').

    Returns: agent definition as a YAML-frontmatter markdown string.
    """
    return f"""---
name: data-ingestion-{step_name}
description: generate the output file {output_file}
mode: primary
permission:
  read:
    "{schemas_dir}/**": allow
  write:
    "{work_dir}/**": allow
  edit:
    "{work_dir}/**": allow
  bash:
    "{work_dir}/**": allow
  webfetch: allow
  websearch: allow
---

You are a data ingestion agent. Read the instruction carefully, use the inlined schemas to understand the required output format, and generate the output file {output_file} at the exact absolute path specified in the instruction. Use the write tool. Do not ask questions — produce the output file.
"""


def _compose_step_instruction(
    step_prompt: str,
    note_content: str,
    site_prompt_content: str,
    schema_contents: dict,
    schema_keys: list[str],
    output_path: Path,
    context_files: Optional[dict[str, str]] = None,
) -> str:
    """Compose a step-specific instruction with only the relevant schemas inlined.

    step_prompt: the step-specific prompt markdown content.
    note_content: the raw markdown note content.
    site_prompt_content: the site prompt markdown content.
    schema_contents: dict mapping schema filename -> schema JSON string.
    schema_keys: list of schema filenames to inline in this step.
    output_path: the absolute path where the output file should be written.
    context_files: optional dict of {filename: content} for additional context
        (e.g. site.config.json for Step 2).

    Returns: the composed instruction string.
    """
    instruction_parts = [
        step_prompt,
        "",
        "## Input Files",
        "",
        "### Note",
        "```markdown",
        note_content,
        "```",
        "",
        "### Site Prompt",
        "```markdown",
        site_prompt_content,
        "```",
    ]

    for schema_key in schema_keys:
        if schema_key in schema_contents:
            instruction_parts.extend([
                "",
                f"### Schema: {schema_key}",
                "```json",
                schema_contents[schema_key],
                "```",
            ])

    if context_files:
        for filename, content in context_files.items():
            instruction_parts.extend([
                "",
                f"### Context: {filename}",
                "```json",
                content,
                "```",
            ])

    instruction_parts.extend([
        "",
        f"Write the output file to: {output_path}",
    ])

    return "\n".join(instruction_parts)


def run_ingestion(
    note_path: Path,
    site_prompt_path: Path,
    schemas_dir: Path,
    prompt_path: Path,
    model: str,
    output_dir: Path,
    agent_path: Optional[Path] = None,
    opencode_bin: str = "opencode",
    debug: bool = False,
) -> None:
    """Run the data ingestion pipeline.

    Reads the note, site-prompt, and instruction prompt files, composes a
    full instruction with inlined schemas, invokes opencode as an LLM agent
    in a temporary working directory, and copies the generated output files
    to output_dir.

    Args:
        note_path: Path to the raw markdown note file.
        site_prompt_path: Path to the site prompt markdown file.
        schemas_dir: Path to the directory containing schema JSON files.
        prompt_path: Path to the ingestion prompt markdown file.
        model: LLM model identifier to use (e.g. "gpt-4o").
        output_dir: Directory to write the generated JSON files into.
        agent_path: Optional path to a custom agent definition file. If not
            provided, a scoped default is generated.
        opencode_bin: Path or name of the opencode binary.
        debug: If True, preserve the temporary workspace on failure.

    Raises:
        FileNotFoundError: If any input file or binary is missing.
        RuntimeError: If the subprocess fails or output files are missing.
    """
    # Resolve all input paths
    note_path = Path(note_path).resolve(strict=True)
    site_prompt_path = Path(site_prompt_path).resolve(strict=True)
    schemas_dir = Path(schemas_dir).resolve(strict=True)
    prompt_path = Path(prompt_path).resolve(strict=True)
    output_dir = Path(output_dir).resolve()

    # Check opencode binary exists
    opencode_bin_resolved = shutil.which(opencode_bin)
    if opencode_bin_resolved is None:
        raise FileNotFoundError(
            f"opencode binary '{opencode_bin}' not found on PATH. "
            f"Use --opencode-path or set PATH accordingly."
        )

    # Read input files
    note_content = _read_file(note_path)
    site_prompt_content = _read_file(site_prompt_path)
    prompt_content = _read_file(prompt_path)

    # Read schemas
    schema_contents = {}
    for schema_file in SCHEMA_FILES:
        schema_path = schemas_dir / schema_file
        if not schema_path.exists():
            raise FileNotFoundError(
                f"Schema file not found: {schema_path}"
            )
        schema_contents[schema_file] = _read_file(schema_path)

    # Create temporary working directory
    tmp_dir_obj = tempfile.mkdtemp(prefix="data_ingestion_")
    tmp_dir = Path(tmp_dir_obj)

    print("⚡ Running single-shot data ingestion...", file=sys.stderr)

    try:
        # Generate or resolve agent definition
        if agent_path:
            agent_def_file = Path(agent_path).resolve(strict=True)
        else:
            agent_def_content = _generate_agent_def(
                work_dir=str(tmp_dir),
                schemas_dir=str(schemas_dir),
            )
            agent_def_file = tmp_dir / "agent.md"
            agent_def_file.write_text(agent_def_content, encoding="utf-8")

        # Compose the final instruction
        instruction_parts = [
            prompt_content,
            "",
            "## Input Files",
            "",
            "### Note",
            "```markdown",
            note_content,
            "```",
            "",
            "### Site Prompt",
            "```markdown",
            site_prompt_content,
            "```",
        ]

        for schema_file in SCHEMA_FILES:
            instruction_parts.extend([
                "",
                f"### Schema: {schema_file}",
                "```json",
                schema_contents[schema_file],
                "```",
            ])

        instruction_parts.extend([
            "",
            f"Write the three output files to the directory: {tmp_dir}",
            "",
            f"  - {tmp_dir}/links.json",
            f"  - {tmp_dir}/site.config.json",
            f"  - {tmp_dir}/design.json",
        ])

        composed_instruction = "\n".join(instruction_parts)

        # Write instruction to a temp file to avoid shell argument length limits
        instruction_file = tmp_dir / "instruction.md"
        instruction_file.write_text(composed_instruction, encoding="utf-8")

        # Prepare environment
        env = os.environ.copy()
        env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"

        cmd = [
            opencode_bin_resolved,
            "run",
            "Execute the instructions in the attached file.",
            "--file", str(instruction_file),
            "--model", model,
            "--agent", str(agent_def_file),
            "--auto",
            "--dir", str(tmp_dir),
        ]

        if debug:
            print(f"  Command: {' '.join(cmd)}", file=sys.stderr)
            print(f"  Working directory: {tmp_dir}", file=sys.stderr)
            print(f"  Instruction file: {instruction_file}", file=sys.stderr)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=OPENCODE_TIMEOUT,
        )

        if result.returncode != 0:
            error_msg = (
                f"opencode process failed with exit code {result.returncode}.\n"
            )
            if result.stdout:
                error_msg += f"stdout:\n{result.stdout}\n"
            if result.stderr:
                error_msg += f"stderr:\n{result.stderr}\n"
            raise RuntimeError(error_msg)

        # Check for expected output files
        missing = []
        for filename in REQUIRED_OUTPUTS:
            if not (tmp_dir / filename).exists():
                missing.append(filename)

        if missing:
            error_msg = (
                f"Missing output files: {', '.join(missing)}. "
                f"Check that the model and prompt are correct.\n"
            )
            if result.stdout:
                error_msg += f"opencode stdout:\n{result.stdout}\n"
            if result.stderr:
                error_msg += f"opencode stderr:\n{result.stderr}\n"
            raise RuntimeError(error_msg)

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Copy output files
        for filename in REQUIRED_OUTPUTS:
            src = tmp_dir / filename
            dst = output_dir / filename
            shutil.copy2(str(src), str(dst))

        print("  ✓ All three output files generated", file=sys.stderr)
        print(f"\n✅ Ingestion complete!", file=sys.stderr)
        print(f"📁 Output files: {output_dir}", file=sys.stderr)
        for filename in REQUIRED_OUTPUTS:
            if (output_dir / filename).exists():
                print(f"   • {filename}", file=sys.stderr)

        if debug:
            print(f"  Output files written to: {output_dir}", file=sys.stderr)

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"opencode process timed out after {OPENCODE_TIMEOUT} seconds. "
            f"Check the model and prompt, or increase the timeout."
        )
    finally:
        if not debug:
            shutil.rmtree(tmp_dir_obj, ignore_errors=True)


def _resolve_stage_setting(step_key, stage_config, setting_key, global_value):
    """Resolve a per-stage setting with cascading fallback.

    step_key: stage key (e.g. "design").
    stage_config: dict of stage_key → overrides dict.
    setting_key: "model" or "max_retries".
    global_value: fallback value from global_* params.

    Returns: the effective value.
    """
    if stage_config and step_key in stage_config:
        val = stage_config[step_key].get(setting_key)
        if val is not None:
            return val
    return global_value


def build_stage_config(
    stages_cfg,
    *,
    stage_keys: Optional[list] = None,
    multi_step: bool = True,
) -> Tuple[Optional[dict], Optional[list]]:
    """Build the per-stage config and requested-stage list from ``ingest.stages``.

    Validates stage keys unconditionally (unknown key → stderr + exit 1).
    With ``multi_step`` true, builds ``requested_stages`` in pipeline order
    and ``stage_config`` keeping only stages whose overrides dict has at
    least one non-``None`` value. With ``multi_step`` false, prints the
    canonical warning and ignores the stages configuration.

    param: stages_cfg — the ``ingest.stages`` config subsection (may be a
        frozen MappingProxyType, a plain dict, or None/empty).
    param: stage_keys — valid stage keys in pipeline order; defaults to
        ["site.config", "links", "design"].
    param: multi_step — whether multi-step mode is enabled.

    Returns: (stage_config, requested_stages) tuple; both None when the
        configuration is absent or ignored (multi_step false).

    ResourceryError: exit 1 if stages_cfg contains an unknown stage key.
    """
    if stage_keys is None:
        stage_keys = ["site.config", "links", "design"]

    if not stages_cfg:
        return None, None

    # Always validate stage keys (canonical data_ingestion.py order)
    for key in stages_cfg:
        if key not in stage_keys:
            msg = (
                f"Error: Unknown stage key '{key}' in config.yaml ingest.stages. "
                f"Valid keys are: {', '.join(stage_keys)}"
            )
            print(msg, file=sys.stderr)
            raise ResourceryError(msg)

    if not multi_step:
        print(
            "⚠️  Warning: 'stages:' is configured but 'multi_step' is false. "
            "Per-stage configuration requires multi_step mode. "
            "Ignoring stages configuration.",
            file=sys.stderr,
        )
        return None, None

    # Build requested_stages in pipeline order
    requested_stages = [k for k in stage_keys if k in stages_cfg]

    # Build stage_config: only include stages that have actual overrides
    stage_config = {}
    for key in requested_stages:
        overrides = stages_cfg[key]
        if isinstance(overrides, dict) or hasattr(overrides, "items"):
            # Only include if there are actual overrides
            filtered = {k: v for k, v in overrides.items() if v is not None}
            if filtered:
                stage_config[key] = filtered
        # If overrides is None (YAML empty value), no overrides — skip

    return stage_config, requested_stages


def run_multi_step_ingestion(
    note_path: Path,
    site_prompt_path: Path,
    schemas_dir: Path,
    prompts_dir: Path,
    global_model: str,
    output_dir: Path,
    global_max_retries: int = 3,
    stage_config: Optional[dict] = None,
    requested_stages: Optional[list] = None,
    agent_path: Optional[Path] = None,
    opencode_bin: str = "opencode",
    debug: bool = False,
) -> None:
    """Run the multi-step data ingestion pipeline.

    Executes three sequential opencode calls, each focused on a single output
    file with its own prompt, schema validation, retry logic, and final
    cross-validation.

    Args:
        note_path: Path to the raw markdown note file.
        site_prompt_path: Path to the site prompt markdown file.
        schemas_dir: Path to the directory containing schema JSON files.
        prompts_dir: Path to the directory containing step prompt files.
        global_model: LLM model identifier used as the default for all stages
            unless overridden per-stage in *stage_config*.
        output_dir: Directory to write the generated JSON files into.
        global_max_retries: Maximum retries per step (default for all stages).
        stage_config: Optional dict mapping stage key (e.g. "design") to a dict
            of overrides (e.g. {"model": "claude-sonnet-4", "max_retries": 5}).
            Only stages with actual overrides need entries. If None, all stages
            use *global_model* and *global_max_retries*.
        requested_stages: Optional ordered list of stage keys to execute. Stages
            not in this list are skipped. If None, all three stages execute.
            Ignored when *stage_config* is also None.
        agent_path: Optional path to a custom agent definition file. If not
            provided, a scoped default is generated per step.
        opencode_bin: Path or name of the opencode binary.
        debug: If True, preserve the temporary workspace on failure.

    Raises:
        FileNotFoundError: If any input file or binary is missing.
        RuntimeError: If a step exhausts retries or cross-validation fails.
    """
    # Resolve all input paths
    note_path = Path(note_path).resolve(strict=True)
    site_prompt_path = Path(site_prompt_path).resolve(strict=True)
    schemas_dir = Path(schemas_dir).resolve(strict=True)
    prompts_dir = Path(prompts_dir).resolve(strict=True)
    output_dir = Path(output_dir).resolve()

    # Check opencode binary exists
    opencode_bin_resolved = shutil.which(opencode_bin)
    if opencode_bin_resolved is None:
        raise FileNotFoundError(
            f"opencode binary '{opencode_bin}' not found on PATH. "
            f"Use --opencode-path or set PATH accordingly."
        )

    # Read input files
    note_content = _read_file(note_path)
    site_prompt_content = _read_file(site_prompt_path)

    # Read schemas
    schema_contents = {}
    for schema_file in SCHEMA_FILES:
        schema_path = schemas_dir / schema_file
        if not schema_path.exists():
            raise FileNotFoundError(
                f"Schema file not found: {schema_path}"
            )
        schema_contents[schema_file] = _read_file(schema_path)

    # Read step prompts
    step_prompts = {}

    # Step definitions
    STEPS = [
        {
            "name": "site.config.json",
            "stage_key": "site.config",
            "prompt_file": "ingest-site-config.md",
            "output_file": "site.config.json",
            "schema_keys": ["site.config.schema.json"],
            "context_files": None,
            "depends_on": None,
        },
        {
            "name": "links.json",
            "stage_key": "links",
            "prompt_file": "ingest-links.md",
            "output_file": "links.json",
            "schema_keys": ["links.schema.json"],
            "context_files": {"site.config.json": None},  # populated at runtime
            "depends_on": "site.config.json",
        },
        {
            "name": "design.json",
            "stage_key": "design",
            "prompt_file": "ingest-design.md",
            "output_file": "design.json",
            "schema_keys": ["design.schema.json"],
            "context_files": None,
            "depends_on": None,
        },
    ]

    # Read step prompt files
    for step in STEPS:
        prompt_path = prompts_dir / step["prompt_file"]
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Step prompt file not found: {prompt_path}"
            )
        step_prompts[step["prompt_file"]] = _read_file(prompt_path)

    # Create temporary working directory
    tmp_dir_obj = tempfile.mkdtemp(prefix="multi_step_ingestion_")
    tmp_dir = Path(tmp_dir_obj)

    print("🧩 Starting multi-step data ingestion...\n", file=sys.stderr)

    try:
        # Determine which steps to execute based on requested_stages
        selected_steps = STEPS  # default: all three

        if requested_stages is not None:
            # --- Completeness check: do all three output files exist in output_dir? ---
            all_exist = all((output_dir / f).exists() for f in REQUIRED_OUTPUTS)

            if not all_exist:
                missing = [f for f in REQUIRED_OUTPUTS if not (output_dir / f).exists()]
                if global_model:
                    # Auto-expand: run full pipeline
                    print(
                        f"ℹ️  Output set incomplete — {', '.join(missing)} not found in "
                        f"output directory. Automatically running full pipeline to "
                        f"generate all required output files. Stages listed in config "
                        f"use their per-stage settings; auto-added stages use global defaults.",
                        file=sys.stderr,
                    )
                    selected_steps = STEPS
                else:
                    # Error: no global model to auto-generate missing files
                    raise RuntimeError(
                        f"Output set incomplete — {', '.join(missing)} not found in "
                        f"output directory and no global 'model' is defined to "
                        f"auto-generate {'it' if len(missing) == 1 else 'them'}. "
                        f"All three output files ({', '.join(REQUIRED_OUTPUTS)}) are "
                        f"required to build the website.\n"
                        f"Either:\n"
                        f"  1. Set 'ingest.model' in config.yaml as a global default, or\n"
                        f"  2. Run the full pipeline first to generate all output files, or\n"
                        f"  3. Provide per-stage 'model' for all missing stages in the "
                        f"stages: section."
                    )
            else:
                # All three exist — run only the requested stages (in pipeline order)
                selected_steps = [
                    s for s in STEPS if s["stage_key"] in requested_stages
                ]
                # Prime tmp_dir with existing output files so context feeding
                # and cross-validation have access to unexecuted stages' data.
                for filename in REQUIRED_OUTPUTS:
                    src = output_dir / filename
                    if src.exists():
                        shutil.copy2(str(src), str(tmp_dir / filename))

        # Run each step
        step_labels = {
            "site.config.json": "Defining site identity, taxonomy, and content copy",
            "links.json": "Extracting and enriching links with category assignments",
            "design.json": "Designing visual theme (colors, typography, layout, effects)",
        }
        step_index = 0
        for step in selected_steps:
            step_name = step["name"]
            step_key = step["stage_key"]
            output_file = step["output_file"]
            prompt_file = step["prompt_file"]
            schema_keys = step["schema_keys"]
            context_files = step.get("context_files")

            # Resolve effective model and max_retries for this step
            # Auto-added stages (not in requested_stages when auto-expanding)
            # should only use globals — their key won't be in stage_config.
            effective_model = _resolve_stage_setting(
                step_key, stage_config, "model", global_model
            )
            effective_max_retries = _resolve_stage_setting(
                step_key, stage_config, "max_retries", global_max_retries
            )

            if not effective_model:
                raise RuntimeError(
                    f"No model configured for stage '{step_key}'. "
                    f"Set either 'ingest.model' in config.yaml as a global default "
                    f"or provide a per-stage 'model' override."
                )

            # If step has context from a previous step, read the file
            resolved_context = None
            if context_files:
                resolved_context = {}
                for ctx_filename, _ in context_files.items():
                    ctx_path = tmp_dir / ctx_filename
                    if ctx_path.exists():
                        resolved_context[ctx_filename] = _read_file(ctx_path)
                    else:
                        # If the dependency file doesn't exist yet, it's a
                        # step that hasn't been processed; skip context
                        print(
                            f"WARNING  Context file '{ctx_filename}' not found for step "
                            f"'{step_name}' — skipping context.",
                            file=sys.stderr,
                        )

            # Compose step instruction
            output_path = tmp_dir / output_file
            step_prompt_content = step_prompts[prompt_file]

            composed_instruction = _compose_step_instruction(
                step_prompt=step_prompt_content,
                note_content=note_content,
                site_prompt_content=site_prompt_content,
                schema_contents=schema_contents,
                schema_keys=schema_keys,
                output_path=output_path,
                context_files=resolved_context,
            )

            # Generate step agent definition
            if agent_path:
                agent_def_file = Path(agent_path).resolve(strict=True)
            else:
                agent_def_content = _generate_step_agent_def(
                    work_dir=str(tmp_dir),
                    schemas_dir=str(schemas_dir),
                    step_name=step_name,
                    output_file=output_file,
                )
                agent_def_file = tmp_dir / f"agent_{step_name}.md"
                agent_def_file.write_text(agent_def_content, encoding="utf-8")

            # Write instruction to a temp file
            instruction_file = tmp_dir / f"instruction_{step_name}.md"
            instruction_file.write_text(composed_instruction, encoding="utf-8")

            step_index += 1
            step_desc = step_labels.get(step_name, f"Generating {step_name}")
            print(f"  Step {step_index}/{len(selected_steps)}: {step_desc}...", file=sys.stderr)

            # Retry loop
            last_validation_errors = []
            last_output_content = None
            step_succeeded = False

            for attempt in range(1, effective_max_retries + 1):
                # Determine which instruction to use
                if attempt == 1:
                    current_instruction = composed_instruction
                else:
                    # Retry instruction: include previous output + validation errors
                    retry_parts = [
                        composed_instruction,
                        "",
                        "## Previous (Invalid) Output",
                        "```json",
                        last_output_content,
                        "```",
                        "",
                        "## Validation Errors",
                    ]
                    for err in last_validation_errors:
                        retry_parts.append(f"- {err}")
                    retry_parts.extend([
                        "",
                        "## Fix Request",
                        "Please fix the specific errors above and regenerate the corrected output.",
                    ])
                    current_instruction = "\n".join(retry_parts)
                    instruction_file.write_text(current_instruction, encoding="utf-8")

                # Prepare environment
                env = os.environ.copy()
                env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"

                cmd = [
                    opencode_bin_resolved,
                    "run",
                    "Execute the instructions in the attached file.",
                    "--file", str(instruction_file),
                    "--model", effective_model,
                    "--agent", str(agent_def_file),
                    "--auto",
                    "--dir", str(tmp_dir),
                ]

                if debug:
                    print(f"  Command: {' '.join(cmd)}", file=sys.stderr)
                    print(f"  Working directory: {tmp_dir}", file=sys.stderr)
                    print(f"  Instruction file: {instruction_file}", file=sys.stderr)
                    print(f"  Step: {step_name}, attempt: {attempt}/{effective_max_retries}", file=sys.stderr)

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=OPENCODE_TIMEOUT,
                )

                if result.returncode != 0:
                    error_msg = (
                        f"opencode process failed with exit code {result.returncode}.\n"
                    )
                    if result.stdout:
                        error_msg += f"stdout:\n{result.stdout}\n"
                    if result.stderr:
                        error_msg += f"stderr:\n{result.stderr}\n"
                    raise RuntimeError(error_msg)

                # Check that the output file exists
                if not output_path.exists():
                    raise RuntimeError(
                        f"Step '{step_name}' did not produce output file: {output_path}\n"
                        f"opencode stdout:\n{result.stdout}\n"
                        f"opencode stderr:\n{result.stderr}\n"
                    )

                # Read the output for validation
                last_output_content = output_path.read_text(encoding="utf-8")

                # Validate against schema using DataValidator
                step_validator = DataValidator(
                    data_dir=tmp_dir,
                    schemas_dir=schemas_dir,
                )
                step_validator.load_schemas()

                try:
                    output_data = loads_json(last_output_content, path=output_path)
                except JsonLoadError as e:
                    last_validation_errors = [f"Invalid JSON: {e}"]
                    if attempt < effective_max_retries:
                        print(
                            f"  ⚠️  Step {step_index}/{len(selected_steps)} '{step_name}' invalid JSON — "
                            f"retry {attempt}/{effective_max_retries}",
                            file=sys.stderr,
                        )
                        continue
                    else:
                        raise RuntimeError(
                            f"Step '{step_name}' failed after {effective_max_retries} retries.\n"
                            f"Last validation errors: {last_validation_errors}\n"
                            f"Last invalid output: {output_path}"
                        )

                # Determine which schema to validate against
                if output_file == "site.config.json":
                    schema = step_validator.config_schema
                elif output_file == "links.json":
                    schema = step_validator.links_schema
                elif output_file == "design.json":
                    schema = step_validator.design_schema
                else:
                    schema = None

                if schema is None:
                    raise RuntimeError(f"Unknown output file: {output_file}")

                validation_passed = step_validator.validate_schema(
                    output_data, schema, output_file
                )

                if validation_passed:
                    step_succeeded = True
                    print(
                        f"  ✓ {step_name} generated and validated",
                        file=sys.stderr,
                    )
                    if debug:
                        print(
                            f"  Step '{step_name}' validation passed.",
                            file=sys.stderr,
                        )
                    break
                else:
                    last_validation_errors = list(step_validator.errors)
                    if attempt < effective_max_retries:
                        print(
                            f"  ⚠️  Step {step_index}/{len(selected_steps)} '{step_name}' failed validation — "
                            f"retry {attempt}/{effective_max_retries}",
                            file=sys.stderr,
                        )
                    else:
                        raise RuntimeError(
                            f"Step '{step_name}' failed after {effective_max_retries} retries.\n"
                            f"Last validation errors: {last_validation_errors}\n"
                            f"Last invalid output: {output_path}"
                        )

            if not step_succeeded:
                raise RuntimeError(
                    f"Step '{step_name}' did not complete successfully."
                )

        # Cross-validation at the end
        print("\n🔗 Cross-validating output files...", file=sys.stderr)
        cross_validator = DataValidator(
            data_dir=tmp_dir,
            schemas_dir=schemas_dir,
        )
        cross_validator.load_schemas()

        if not cross_validator.load_data():
            # Some expected files are missing (intentionally skipped with
            # no prior output). Warn instead of failing.
            print(
                "  ⚠️  Skipping cross-validation — one or more output files are "
                "absent (intentionally skipped stages).",
                file=sys.stderr,
            )
        else:
            cross_valid = cross_validator.cross_validate()
            if not cross_valid:
                if requested_stages is not None:
                    # Selective execution: cross-validation failures are warnings,
                    # since some files may come from a different run.
                    for err in cross_validator.errors:
                        print(f"  ⚠️  {err}", file=sys.stderr)
                else:
                    # Full run: cross-validation failures are still errors.
                    raise RuntimeError(
                        f"Cross-validation failed. Errors: {cross_validator.errors}"
                    )
            if cross_validator.warnings:
                for w in cross_validator.warnings:
                    print(f"  ⚠️  {w}", file=sys.stderr)
            print("  ✓ Cross-validation passed", file=sys.stderr)

        # Copy output files to output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename in REQUIRED_OUTPUTS:
            src = tmp_dir / filename
            if src.exists():
                dst = output_dir / filename
                shutil.copy2(str(src), str(dst))

        print(f"\n✅ Ingestion complete!", file=sys.stderr)
        print(f"📁 Output files: {output_dir}", file=sys.stderr)
        for filename in REQUIRED_OUTPUTS:
            if (output_dir / filename).exists():
                print(f"   • {filename}", file=sys.stderr)

        if debug:
            print(f"  Output files written to: {output_dir}", file=sys.stderr)

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"opencode process timed out after {OPENCODE_TIMEOUT} seconds. "
            f"Check the model and prompt, or increase the timeout."
        )
    finally:
        if not debug:
            shutil.rmtree(tmp_dir_obj, ignore_errors=True)


def main():
    """Parse CLI arguments and run the ingestion pipeline."""
    parser = argparse.ArgumentParser(
        description="Agentic data ingestion: transform markdown notes into structured JSON files."
    )
    parser.add_argument(
        "--note",
        type=str,
        required=True,
        help="Path to the raw markdown note file.",
    )
    parser.add_argument(
        "--site-prompt",
        type=str,
        required=True,
        help="Path to the site prompt markdown file.",
    )
    parser.add_argument(
        "--schemas",
        type=str,
        default=None,
        help="Path to the schemas directory (default: from config.yaml).",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Path to the ingestion prompt markdown file (ignored when --multi-step is used; default: from config.yaml).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model identifier (e.g. gpt-4o; default: from config.yaml).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for generated JSON files (default: from config.yaml).",
    )
    parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Path to a custom agent definition file (optional).",
    )
    parser.add_argument(
        "--opencode-path",
        type=str,
        default=None,
        help="Path or name of the opencode binary (default: 'opencode' or from config.yaml).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Preserve temporary workspace on failure for debugging.",
    )
    parser.add_argument(
        "--multi-step",
        action="store_true",
        default=None,
        help="Enable 3-step pipeline instead of single-shot mode (default: from config.yaml).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Maximum retries per step when --multi-step is used (default: 3 or from config.yaml).",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to a user config YAML file (optional; layered on top of committed config.yaml).",
    )

    args = parser.parse_args()

    # Load config
    from resourcery_ssg.config import load_resourcery_config, build_cli_overrides

    # Build CLI overrides (only for values that were explicitly provided)
    overrides = build_cli_overrides(
        args,
        "ingest",
        {
            "schemas": "schemas_dir",
            "prompt": "prompt",
            "model": "model",
            "output": "output_dir",
            "opencode_path": "opencode_bin",
            "multi_step": "multi_step",
            "max_retries": "max_retries",
        },
    )

    config = load_resourcery_config(
        config_path=args.config,
        overrides=overrides,
    )
    ingest_cfg = config.get("ingest", {})
    stages_cfg = ingest_cfg.get("stages")

    # Resolve values: CLI (via overrides already merged into config) > config defaults
    schemas_dir = ingest_cfg.get("schemas_dir")
    prompt_path = ingest_cfg.get("prompt")
    model = ingest_cfg.get("model")
    output_dir = ingest_cfg.get("output_dir")
    opencode_bin = ingest_cfg.get("opencode_bin", "opencode")
    multi_step = ingest_cfg.get("multi_step", False)
    max_retries = ingest_cfg.get("max_retries", 3)

    # Validate that required values are present
    if not schemas_dir:
        print("Error: --schemas is required (and not set in config.yaml)", file=sys.stderr)
        sys.exit(1)
    if not prompt_path:
        print("Error: --prompt is required (and not set in config.yaml)", file=sys.stderr)
        sys.exit(1)
    if not model:
        print("Error: --model is required (and not set in config.yaml)", file=sys.stderr)
        sys.exit(1)
    if not output_dir:
        print("Error: --output is required (and not set in config.yaml)", file=sys.stderr)
        sys.exit(1)

    # Resolve paths
    note_path = Path(args.note)
    site_prompt_path = Path(args.site_prompt)
    schemas_dir = Path(schemas_dir)
    prompt_path = Path(prompt_path)
    output_dir = Path(output_dir)
    agent_path = Path(args.agent) if args.agent else None

    # Validate inputs
    for path, label in [
        (note_path, "--note"),
        (site_prompt_path, "--site-prompt"),
        (schemas_dir, "--schemas"),
        (prompt_path, "--prompt"),
    ]:
        if not path.exists():
            print(f"Error: {label} path does not exist: {path}", file=sys.stderr)
            sys.exit(1)

    # Process stages configuration (per-stage overrides and selective execution)
    try:
        stage_config, requested_stages = build_stage_config(
            stages_cfg, multi_step=multi_step
        )
    except ResourceryError:
        sys.exit(1)

    try:
        if multi_step:
            # Derive prompts_dir from the parent of the prompt file
            prompts_dir = prompt_path.resolve().parent

            run_multi_step_ingestion(
                note_path=note_path,
                site_prompt_path=site_prompt_path,
                schemas_dir=schemas_dir,
                prompts_dir=prompts_dir,
                global_model=model,
                output_dir=output_dir,
                global_max_retries=max_retries,
                stage_config=stage_config,
                requested_stages=requested_stages,
                agent_path=agent_path,
                opencode_bin=opencode_bin,
                debug=args.debug,
            )
        else:
            run_ingestion(
                note_path=note_path,
                site_prompt_path=site_prompt_path,
                schemas_dir=schemas_dir,
                prompt_path=prompt_path,
                model=model,
                output_dir=output_dir,
                agent_path=agent_path,
                opencode_bin=opencode_bin,
                debug=args.debug,
            )
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("Data ingestion completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
