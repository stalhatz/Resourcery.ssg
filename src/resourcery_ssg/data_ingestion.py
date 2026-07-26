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
from typing import Optional


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
        required=True,
        help="Path to the schemas directory.",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        required=True,
        help="Path to the ingestion prompt markdown file.",
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="LLM model identifier (e.g. gpt-4o).",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output directory for generated JSON files.",
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
        default="opencode",
        help="Path or name of the opencode binary (default: opencode, resolved from PATH).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Preserve temporary workspace on failure for debugging.",
    )

    args = parser.parse_args()

    # Resolve paths
    note_path = Path(args.note)
    site_prompt_path = Path(args.site_prompt)
    schemas_dir = Path(args.schemas)
    prompt_path = Path(args.prompt)
    output_dir = Path(args.output)
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

    try:
        run_ingestion(
            note_path=note_path,
            site_prompt_path=site_prompt_path,
            schemas_dir=schemas_dir,
            prompt_path=prompt_path,
            model=args.model,
            output_dir=output_dir,
            agent_path=agent_path,
            opencode_bin=args.opencode_path,
            debug=args.debug,
        )
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("Data ingestion completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
