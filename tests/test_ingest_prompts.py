"""Unit tests for resourcery_ssg.ingest_prompts — prompt composition helpers."""

from pathlib import Path

import pytest

from resourcery_ssg.ingest_prompts import (
    compose_step_instruction,
    generate_agent_def,
    read_file,
)


class TestGenerateAgentDef:
    """The merge's safety contract: byte-identical output at both call sites.

    The expected strings below are the exact current outputs of the
    pre-split single-shot and step agent-def generators, captured before
    their deletion, including the trailing newline.
    """

    SINGLE_SHOT_EXPECTED = """---
name: data-ingestion
description: Data ingestion agent
mode: primary
permission:
  read:
    "/tmp/sd/**": allow
  write:
    "/tmp/wd/**": allow
  edit:
    "/tmp/wd/**": allow
  bash:
    "/tmp/wd/**": allow
  webfetch: allow
  websearch: allow
---

You are a data ingestion agent. Read the instruction carefully, use the inlined schemas to understand the required output format, and generate the three output files (links.json, site.config.json, design.json) at the exact absolute paths specified in the instruction. Use the write tool. Do not ask questions — produce the output files.
"""

    STEP_EXPECTED = """---
name: data-ingestion-site.config.json
description: generate the output file site.config.json
mode: primary
permission:
  read:
    "/tmp/sd/**": allow
  write:
    "/tmp/wd/**": allow
  edit:
    "/tmp/wd/**": allow
  bash:
    "/tmp/wd/**": allow
  webfetch: allow
  websearch: allow
---

You are a data ingestion agent. Read the instruction carefully, use the inlined schemas to understand the required output format, and generate the output file site.config.json at the exact absolute path specified in the instruction. Use the write tool. Do not ask questions — produce the output file.
"""

    @pytest.mark.unit
    def test_single_shot_output_byte_identical(self):
        result = generate_agent_def(
            work_dir="/tmp/wd",
            schemas_dir="/tmp/sd",
            agent_name="data-ingestion",
            description="Data ingestion agent",
            output_phrase=(
                "the three output files (links.json, site.config.json, design.json) "
                "at the exact absolute paths specified in the instruction. Use the "
                "write tool. Do not ask questions — produce the output files."
            ),
        )
        assert result == self.SINGLE_SHOT_EXPECTED
        assert result.endswith("\n")

    @pytest.mark.unit
    def test_step_output_byte_identical(self):
        result = generate_agent_def(
            work_dir="/tmp/wd",
            schemas_dir="/tmp/sd",
            agent_name="data-ingestion-site.config.json",
            description="generate the output file site.config.json",
            output_phrase=(
                "the output file site.config.json at the exact absolute path "
                "specified in the instruction. Use the write tool. Do not ask "
                "questions — produce the output file."
            ),
        )
        assert result == self.STEP_EXPECTED
        assert result.endswith("\n")

    @pytest.mark.unit
    def test_structure(self):
        result = generate_agent_def(
            work_dir="/tmp/wd",
            schemas_dir="/tmp/sd",
            agent_name="data-ingestion",
            description="Data ingestion agent",
            output_phrase="the output file",
        )
        assert "name: data-ingestion" in result
        assert "description: Data ingestion agent" in result
        assert "mode: primary" in result
        assert '"/tmp/sd/**": allow' in result
        assert '"/tmp/wd/**": allow' in result
        assert "webfetch: allow" in result
        assert "websearch: allow" in result


class TestComposeStepInstruction:
    @pytest.mark.unit
    def test_sections_in_order(self):
        instruction = compose_step_instruction(
            step_prompt="# Generate the design.",
            note_content="note",
            site_prompt_content="site",
            schema_contents={"design.schema.json": '{"type": "object"}'},
            schema_keys=["design.schema.json"],
            output_path=Path("/tmp/out.json"),
        )
        expected_order = [
            "# Generate the design.",
            "## Input Files",
            "### Note",
            "### Site Prompt",
            "### Schema: design.schema.json",
            "Write the output file to: /tmp/out.json",
        ]
        positions = [instruction.index(part) for part in expected_order]
        assert positions == sorted(positions)

    @pytest.mark.unit
    def test_exact_output_with_minimal_inputs(self):
        instruction = compose_step_instruction(
            step_prompt="Generate the design.",
            note_content="# My Note",
            site_prompt_content="# Site Prompt",
            schema_contents={"design.schema.json": '{"type": "object"}'},
            schema_keys=["design.schema.json"],
            output_path=Path("/tmp/out.json"),
        )
        assert instruction == (
            "Generate the design.\n"
            "\n"
            "## Input Files\n"
            "\n"
            "### Note\n"
            "```markdown\n"
            "# My Note\n"
            "```\n"
            "\n"
            "### Site Prompt\n"
            "```markdown\n"
            "# Site Prompt\n"
            "```\n"
            "\n"
            "### Schema: design.schema.json\n"
            "```json\n"
            '{"type": "object"}\n'
            "```\n"
            "\n"
            "Write the output file to: /tmp/out.json"
        )


class TestReadFile:
    @pytest.mark.unit
    def test_reads_utf8_file(self, tmp_path):
        path = tmp_path / "note.md"
        path.write_text("hello world", encoding="utf-8")
        assert read_file(path) == "hello world"

    @pytest.mark.unit
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_file(tmp_path / "nope.md")
