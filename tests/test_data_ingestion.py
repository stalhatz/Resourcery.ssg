"""E2E and unit tests for data ingestion pipeline."""

import logging
import re
import sys
from types import MappingProxyType

import pytest
from pathlib import Path
from resourcery_ssg.errors import ResourceryError
from resourcery_ssg.validate import DataValidator
from resourcery_ssg.io_utils import load_json
from resourcery_ssg.data_ingestion import (
    run_ingestion,
    run_multi_step_ingestion,
    _resolve_stage_setting,
    build_stage_config,
    main as ingestion_main,
)


# ---------------------------------------------------------------------------
# Unit tests: _resolve_stage_setting
# ---------------------------------------------------------------------------


class TestResolveStageSetting:
    """Cascading fallback: per-stage override → global default."""

    def test_override_takes_precedence(self):
        result = _resolve_stage_setting(
            "design",
            {"design": {"model": "claude-sonnet"}},
            "model",
            "gpt-4o",
        )
        assert result == "claude-sonnet"

    def test_missing_stage_falls_back_to_global(self):
        result = _resolve_stage_setting(
            "links",
            {"design": {"model": "claude-sonnet"}},
            "model",
            "gpt-4o",
        )
        assert result == "gpt-4o"

    def test_stage_present_but_key_missing_falls_back(self):
        result = _resolve_stage_setting(
            "design",
            {"design": {"max_retries": 5}},
            "model",
            "gpt-4o",
        )
        assert result == "gpt-4o"

    def test_none_stage_config_falls_back(self):
        result = _resolve_stage_setting(
            "design", None, "model", "gpt-4o"
        )
        assert result == "gpt-4o"

    def test_empty_stage_config_falls_back(self):
        result = _resolve_stage_setting(
            "design", {}, "model", "gpt-4o"
        )
        assert result == "gpt-4o"

    def test_override_explicitly_none_falls_back(self):
        """A None override means 'not set' — fall back to global."""
        result = _resolve_stage_setting(
            "design",
            {"design": {"model": None}},
            "model",
            "gpt-4o",
        )
        assert result == "gpt-4o"

    def test_max_retries_override(self):
        result = _resolve_stage_setting(
            "design",
            {"design": {"max_retries": 7}},
            "max_retries",
            3,
        )
        assert result == 7

    def test_max_retries_missing_falls_back(self):
        result = _resolve_stage_setting(
            "site.config",
            {"design": {"max_retries": 7}},
            "max_retries",
            3,
        )
        assert result == 3


# ---------------------------------------------------------------------------
# Unit tests: stage_config building (production helper build_stage_config)
# ---------------------------------------------------------------------------


class TestBuildStageConfig:
    """Stage config extraction from the merged config dict."""

    def test_mapping_proxy_type_overrides_extracted(self):
        """MappingProxyType (frozen config) must work — this is the bug we caught."""
        stages = MappingProxyType({
            "design": MappingProxyType({"model": "claude-sonnet", "max_retries": 5}),
        })
        stage_config, requested_stages = build_stage_config(stages)
        assert stage_config == {"design": {"model": "claude-sonnet", "max_retries": 5}}
        assert requested_stages == ["design"]

    def test_plain_dict_overrides_extracted(self):
        stages = {
            "design": {"model": "claude-sonnet", "max_retries": 5},
        }
        stage_config, requested_stages = build_stage_config(stages)
        assert stage_config == {"design": {"model": "claude-sonnet", "max_retries": 5}}
        assert requested_stages == ["design"]

    def test_bare_stage_not_included(self):
        """A stage listed with no overrides (empty dict) should not appear."""
        stages = {"site.config": {}}
        stage_config, requested_stages = build_stage_config(stages)
        assert stage_config == {}
        assert requested_stages == ["site.config"]

    def test_bare_stage_mapping_proxy_not_included(self):
        stages = MappingProxyType({
            "site.config": MappingProxyType({}),
        })
        stage_config, requested_stages = build_stage_config(stages)
        assert stage_config == {}
        assert requested_stages == ["site.config"]

    def test_stage_with_only_model(self):
        stages = {"design": {"model": "claude-sonnet"}}
        stage_config, requested_stages = build_stage_config(stages)
        assert stage_config == {"design": {"model": "claude-sonnet"}}
        assert requested_stages == ["design"]

    def test_stage_with_none_overrides_skipped(self):
        """A None value (empty YAML) should be skipped entirely."""
        stages = {"design": None}
        stage_config, requested_stages = build_stage_config(stages)
        assert stage_config == {}
        assert requested_stages == ["design"]

    def test_multiple_stages_mixed(self):
        stages = MappingProxyType({
            "site.config": MappingProxyType({}),
            "design": MappingProxyType({"model": "claude-sonnet"}),
            "links": MappingProxyType({"max_retries": 10}),
        })
        stage_config, requested_stages = build_stage_config(stages)
        assert stage_config == {
            "design": {"model": "claude-sonnet"},
            "links": {"max_retries": 10},
        }
        assert requested_stages == ["site.config", "links", "design"]

    def test_only_stages_with_overrides_included(self):
        """Only stages that have non-None overrides appear in stage_config."""
        stages = {
            "site.config": {"model": "gpt-4o"},
            "links": {},
            "design": {"max_retries": 5},
        }
        stage_config, requested_stages = build_stage_config(stages)
        assert stage_config == {
            "site.config": {"model": "gpt-4o"},
            "design": {"max_retries": 5},
        }
        assert requested_stages == ["site.config", "links", "design"]

    def test_unknown_stage_key_exits_1(self, capsys, caplog):
        stages = {"bogus-stage": {}}
        with pytest.raises(ResourceryError) as exc_info:
            build_stage_config(stages)
        assert "Unknown stage key" in str(exc_info.value)
        assert "Unknown stage key" in capsys.readouterr().err
        assert any(
            r.levelno == logging.ERROR and "Unknown stage key" in r.message
            for r in caplog.records
        )

    def test_multi_step_false_warns_and_returns_none(self, capsys, caplog):
        stages = {"design": {"model": "claude-sonnet"}}
        stage_config, requested_stages = build_stage_config(stages, multi_step=False)
        assert stage_config is None
        assert requested_stages is None
        err = capsys.readouterr().err
        assert "'stages:' is configured but 'multi_step' is false" in err
        assert any(
            r.levelno == logging.WARNING
            and "'stages:' is configured but 'multi_step' is false" in r.message
            for r in caplog.records
        )

    def test_falsy_stages_cfg_returns_none(self):
        for stages in (None, {}):
            stage_config, requested_stages = build_stage_config(stages)
            assert stage_config is None
            assert requested_stages is None

    def test_multi_step_false_without_stages_no_warning(self, capsys):
        stage_config, requested_stages = build_stage_config({}, multi_step=False)
        assert stage_config is None
        assert requested_stages is None
        assert capsys.readouterr().err == ""


class TestOperationalRecords:
    """Step 7 operational INFO/DEBUG records from the multi-step pipeline."""

    @pytest.mark.unit
    def test_multi_step_emits_stage_records(self, tmp_path, monkeypatch, caplog):
        """Stage attempt/resolved-config/retry records fire network-free.

        The fake subprocess.run writes an invalid links.json into the
        step's working dir, driving the invalid-JSON retry path.
        """
        from types import SimpleNamespace

        from resourcery_ssg.data_ingestion import (
            REQUIRED_OUTPUTS,
            run_multi_step_ingestion,
        )

        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "note.md").write_text("# Note", encoding="utf-8")
        (notes_dir / "site-prompt.md").write_text("# Prompt", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        for fname in REQUIRED_OUTPUTS:
            (output_dir / fname).write_text("{}", encoding="utf-8")

        def fake_run(cmd, **kwargs):
            work_dir = Path(cmd[cmd.index("--dir") + 1])
            (work_dir / "links.json").write_text("{not json", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(
            "resourcery_ssg.opencode_runner.subprocess.run", fake_run
        )
        monkeypatch.setattr("shutil.which", lambda name: "/fake/opencode")

        caplog.set_level(logging.DEBUG)
        with pytest.raises(RuntimeError):
            run_multi_step_ingestion(
                note_path=notes_dir / "note.md",
                site_prompt_path=notes_dir / "site-prompt.md",
                schemas_dir=_PROJECT_DIR / "schemas",
                prompts_dir=_PROJECT_DIR / "prompts",
                global_model="gpt-4o",
                output_dir=output_dir,
                global_max_retries=2,
                stage_config={"links": {"max_retries": 2}},
                requested_stages=["links"],
                opencode_bin="opencode",
            )

        assert any(
            r.levelno == logging.INFO
            and re.search(r"^Stage 'links' \(model gpt-4o\) attempt 1/2$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.DEBUG
            and re.search(r"^Stage 'links' resolved config: max_retries$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.DEBUG
            and re.search(r"^Retry 1/2 for stage 'links': invalid JSON$", r.message)
            for r in caplog.records
        )


# Root of the test directory — used to locate fixtures and project dirs
_TEST_DIR = Path(__file__).parent
_FIXTURES_DIR = _TEST_DIR / "fixtures"
_PROJECT_DIR = _TEST_DIR.parent


@pytest.mark.e2e
def test_data_ingestion_e2e(tmp_path, pytestconfig):
    """Run the full ingestion pipeline and validate output against schemas.

    This test requires --model to be passed via pytest CLI.
    It is skipped by default (use `pytest -m e2e --model <name>`).
    """
    model = pytestconfig.getoption("--model")
    if not model:
        pytest.skip("use --model to run E2E test")

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Pick a note and site prompt from test fixtures
    note = _FIXTURES_DIR / "markdown" / "notes" / "tech-links.md"
    site_prompt = _FIXTURES_DIR / "markdown" / "site_prompts" / "dev-portal.md"
    schemas_dir = _PROJECT_DIR / "schemas"
    prompt_path = _PROJECT_DIR / "prompts" / "data-ingestion.md"

    run_ingestion(
        note_path=note,
        site_prompt_path=site_prompt,
        schemas_dir=schemas_dir,
        prompt_path=prompt_path,
        model=model,
        output_dir=output_dir,
        opencode_bin=pytestconfig.getoption("--opencode-path"),
        debug=True,  # preserve workspace for debugging on failure
    )

    # Validate output files exist
    assert (output_dir / "links.json").exists(), "links.json missing"
    assert (output_dir / "site.config.json").exists(), "site.config.json missing"
    assert (output_dir / "design.json").exists(), "design.json missing"

    # Use DataValidator for schema + cross-validation
    validator = DataValidator(
        data_dir=output_dir,  # point to output, not default data/
        schemas_dir=_PROJECT_DIR / "schemas",
    )

    # Load schemas (from canonical schemas/ dir)
    assert validator.load_schemas(), "Failed to load schemas"

    # Load generated data
    validator.config_data = load_json(output_dir / "site.config.json")
    validator.links_data = load_json(output_dir / "links.json")
    validator.design_data = load_json(output_dir / "design.json")
    assert validator.config_data, "site.config.json is empty/invalid"
    assert validator.links_data, "links.json is empty/invalid"
    assert validator.design_data, "design.json is empty/invalid"

    # Schema validation
    config_valid = validator.validate_schema(
        validator.config_data, validator.config_schema, "site.config.json"
    )
    links_valid = validator.validate_schema(
        validator.links_data, validator.links_schema, "links.json"
    )
    design_valid = validator.validate_schema(
        validator.design_data, validator.design_schema, "design.json"
    )

    assert config_valid, (
        f"site.config.json schema validation failed: "
        f"{validator.errors[-1] if validator.errors else 'unknown'}"
    )
    assert links_valid, (
        f"links.json schema validation failed: "
        f"{validator.errors[-1] if validator.errors else 'unknown'}"
    )
    assert design_valid, (
        f"design.json schema validation failed: "
        f"{validator.errors[-1] if validator.errors else 'unknown'}"
    )

    # Cross-validation
    cross_valid = validator.cross_validate()
    assert cross_valid, "Cross-validation failed"
    assert len(validator.errors) == 0, (
        f"Errors during validation: {validator.errors}"
    )


@pytest.mark.e2e
def test_data_ingestion_multi_step_e2e(tmp_path, pytestconfig):
    """Run the multi-step ingestion pipeline and validate output against schemas.

    Same fixtures as the single-shot test, but uses --multi-step mode.
    """
    model = pytestconfig.getoption("--model")
    if not model:
        pytest.skip("use --model to run E2E test")

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    note = _FIXTURES_DIR / "markdown" / "notes" / "tech-links.md"
    site_prompt = _FIXTURES_DIR / "markdown" / "site_prompts" / "dev-portal.md"
    schemas_dir = _PROJECT_DIR / "schemas"
    prompts_dir = _PROJECT_DIR / "prompts"

    run_multi_step_ingestion(
        note_path=note,
        site_prompt_path=site_prompt,
        schemas_dir=schemas_dir,
        prompts_dir=prompts_dir,
        global_model=model,
        output_dir=output_dir,
        global_max_retries=3,
        opencode_bin=pytestconfig.getoption("--opencode-path"),
        debug=True,
    )

    # Validate output files exist
    assert (output_dir / "site.config.json").exists()
    assert (output_dir / "links.json").exists()
    assert (output_dir / "design.json").exists()

    # Use DataValidator for schema + cross-validation
    validator = DataValidator(
        data_dir=output_dir,
        schemas_dir=_PROJECT_DIR / "schemas",
    )
    assert validator.load_schemas()

    validator.config_data = load_json(output_dir / "site.config.json")
    validator.links_data = load_json(output_dir / "links.json")
    validator.design_data = load_json(output_dir / "design.json")

    assert validator.config_data
    assert validator.links_data
    assert validator.design_data

    config_valid = validator.validate_schema(
        validator.config_data, validator.config_schema, "site.config.json"
    )
    links_valid = validator.validate_schema(
        validator.links_data, validator.links_schema, "links.json"
    )
    design_valid = validator.validate_schema(
        validator.design_data, validator.design_schema, "design.json"
    )

    assert config_valid
    assert links_valid
    assert design_valid

    cross_valid = validator.cross_validate()
    assert cross_valid
    assert len(validator.errors) == 0


class TestIngestionMainExits:
    """Entry-point exits of ``data_ingestion.main()`` (no LLM orchestration)."""

    @staticmethod
    def _prepare_inputs(tmp_path: Path) -> dict:
        """Create valid note/site-prompt/schemas/prompt files under tmp_path."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "note.md").write_text("# Note", encoding="utf-8")
        (notes_dir / "site-prompt.md").write_text("# Prompt", encoding="utf-8")
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "data-ingestion.md").write_text("# Ingest", encoding="utf-8")
        return {
            "notes_dir": notes_dir,
            "schemas_dir": schemas_dir,
            "prompts_dir": prompts_dir,
        }

    @staticmethod
    def _base_argv(tmp_path: Path) -> list:
        inputs = TestIngestionMainExits._prepare_inputs(tmp_path)
        return [
            "ingest",
            "--note", str(inputs["notes_dir"] / "note.md"),
            "--site-prompt", str(inputs["notes_dir"] / "site-prompt.md"),
            "--schemas", str(inputs["schemas_dir"]),
            "--prompt", str(inputs["prompts_dir"] / "data-ingestion.md"),
            "--model", "gpt-4o",
            "--output", str(tmp_path / "output"),
        ]

    @pytest.mark.unit
    def test_main_missing_required_value_exits_1(self, tmp_path, monkeypatch, capsys, caplog):
        """A required ingest value absent from CLI and config → SystemExit(1).

        The committed config.yaml provides ingest defaults, so the user
        config nulls them out to force the required-value check to fire.
        """
        inputs = self._prepare_inputs(tmp_path)
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "\n".join(
                [
                    "ingest:",
                    "  schemas_dir: null",
                    "  prompt: null",
                    "  model: null",
                    "  output_dir: null",
                ]
            ),
            encoding="utf-8",
        )
        argv = [
            "ingest",
            "--note", str(inputs["notes_dir"] / "note.md"),
            "--site-prompt", str(inputs["notes_dir"] / "site-prompt.md"),
            "--config", str(cfg),
            # --schemas/--prompt/--model/--output omitted on purpose
        ]
        monkeypatch.setattr(sys, "argv", argv)

        with pytest.raises(SystemExit) as exc_info:
            ingestion_main()

        assert exc_info.value.code == 1
        assert "Error: --schemas is required" in capsys.readouterr().err
        assert any(
            r.levelno == logging.ERROR and "Error: --schemas is required" in r.message
            for r in caplog.records
        )

    @pytest.mark.unit
    def test_main_runtime_error_exits_1(self, tmp_path, monkeypatch, capsys, caplog):
        """run_ingestion raising RuntimeError → caught → SystemExit(1)."""
        def raising_run(**kwargs):
            raise RuntimeError("opencode failed")

        monkeypatch.setattr(
            "resourcery_ssg.data_ingestion.run_ingestion", raising_run
        )
        monkeypatch.setattr(sys, "argv", self._base_argv(tmp_path))

        with pytest.raises(SystemExit) as exc_info:
            ingestion_main()

        assert exc_info.value.code == 1
        assert "opencode failed" in capsys.readouterr().err
        assert any(
            r.levelno == logging.ERROR and "opencode failed" in r.message
            for r in caplog.records
        )

    @pytest.mark.unit
    def test_main_unknown_stage_key_exits_1(self, tmp_path, monkeypatch, capsys, caplog):
        """build_stage_config raising ResourceryError → wrapped → SystemExit(1)."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "ingest:\n  stages:\n    bogus: {}\n", encoding="utf-8"
        )
        argv = self._base_argv(tmp_path)
        argv += ["--multi-step", "--config", str(cfg)]
        monkeypatch.setattr(sys, "argv", argv)

        with pytest.raises(SystemExit) as exc_info:
            ingestion_main()

        assert exc_info.value.code == 1
        assert "Unknown stage key" in capsys.readouterr().err
        assert any(
            r.levelno == logging.ERROR and "Unknown stage key" in r.message
            for r in caplog.records
        )
