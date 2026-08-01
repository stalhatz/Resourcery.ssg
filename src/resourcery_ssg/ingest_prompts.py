"""
Prompt composition for the data ingestion pipeline.

Pure string-composition helpers: the merged scoped agent-definition
generator, the multi-step instruction composer, and the text-file reader.
No I/O beyond ``read_file``; nothing logs here.
"""

from pathlib import Path
from typing import Optional


def generate_agent_def(
    work_dir: str,
    schemas_dir: str,
    *,
    agent_name: str,
    description: str,
    output_phrase: str,
) -> str:
    """Generate a scoped agent definition for an ingestion run or step.

    Shared template for the single-shot run (three output files) and each
    multi-step stage (one output file); the differing aspects — agent name,
    description, and the body-sentence tail — are parameters.

    param: work_dir — absolute path to the temp working directory (write scope).
    param: schemas_dir — absolute path to the schemas directory (read scope).
    param: agent_name — the agent's ``name`` frontmatter field.
    param: description — the agent's ``description`` frontmatter field.
    param: output_phrase — the entire tail of the body sentence after
        "...and generate " (e.g. "the three output files (links.json,
        site.config.json, design.json) ... produce the output files.").

    Returns: agent definition as a YAML-frontmatter markdown string.
    """
    return f"""---
name: {agent_name}
description: {description}
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

You are a data ingestion agent. Read the instruction carefully, use the inlined schemas to understand the required output format, and generate {output_phrase}
"""


def compose_step_instruction(
    step_prompt: str,
    note_content: str,
    site_prompt_content: str,
    schema_contents: dict,
    schema_keys: list[str],
    output_path: Path,
    context_files: Optional[dict[str, str]] = None,
) -> str:
    """Compose a step-specific instruction with only the relevant schemas inlined.

    param: step_prompt — the step-specific prompt markdown content.
    param: note_content — the raw markdown note content.
    param: site_prompt_content — the site prompt markdown content.
    param: schema_contents — dict mapping schema filename -> schema JSON string.
    param: schema_keys — list of schema filenames to inline in this step.
    param: output_path — the absolute path where the output file should be written.
    param: context_files — optional dict of {filename: content} for additional context
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


def read_file(path: Path) -> str:
    """Read a text file and return its contents.

    param: path — filesystem path to the file.

    Returns: file contents as a string.

    FileNotFoundError: raised if the file does not exist.
    """
    return path.read_text(encoding="utf-8")
