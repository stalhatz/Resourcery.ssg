"""Tests for resourcery_ssg.site — the ``site`` CLI command dispatch module."""

import sys
import types
from unittest import mock

import pytest

from resourcery_ssg.site import _run_ingest


def _ingest_config(**overrides):
    """Build a minimal config dict with a fully populated ``ingest`` section.

    Keys match what ``_run_ingest`` reads from ``config["ingest"]``.
    Path values are fake strings — only for error-path tests that fail
    before path validation. For tests that reach dispatch, use
    ``_real_ingest_config`` instead.
    """
    ingest = {
        "model": "gpt-4o",
        "note": "data/notes/note.md",
        "site_prompt": "data/notes/site-prompt.md",
        "schemas_dir": "data/schemas",
        "prompt": "data/prompts",
        "output_dir": "data/output",
        "multi_step": False,
    }
    ingest.update(overrides)
    return {"ingest": ingest}


def _real_ingest_config(tmp_path, **overrides):
    """Build a config whose referenced input paths exist on disk.

    ``_run_ingest`` validates that note/site_prompt/schemas_dir/prompt exist
    before dispatching, so tests exercising dispatch (or later validation
    like the unknown-stage check) must point at real files.
    """
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    (notes_dir / "note.md").write_text("# Note", encoding="utf-8")
    (notes_dir / "site-prompt.md").write_text("# Prompt", encoding="utf-8")
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "data-ingestion.md").write_text("# Ingest", encoding="utf-8")

    ingest = {
        "model": "gpt-4o",
        "note": str(notes_dir / "note.md"),
        "site_prompt": str(notes_dir / "site-prompt.md"),
        "schemas_dir": str(schemas_dir),
        "prompt": str(prompts_dir / "data-ingestion.md"),
        "output_dir": str(tmp_path / "output"),
        "multi_step": False,
    }
    ingest.update(overrides)
    return {"ingest": ingest}


class TestRunIngestMissingRequiredValues:
    """Missing ``note``/``site_prompt`` must be a hard error (exit code 1).

    Regression for B4: ``site ingest`` used to print the error but return
    without exiting non-zero, so scripts/CI saw success.
    """

    @pytest.mark.unit
    def test_missing_note_exits_1(self, capsys):
        config = _ingest_config()
        del config["ingest"]["note"]

        with pytest.raises(SystemExit) as exc_info:
            _run_ingest(config)

        assert exc_info.value.code == 1
        assert "ingest.note and ingest.site_prompt are required" in capsys.readouterr().err

    @pytest.mark.unit
    def test_missing_site_prompt_exits_1(self, capsys):
        config = _ingest_config()
        del config["ingest"]["site_prompt"]

        with pytest.raises(SystemExit) as exc_info:
            _run_ingest(config)

        assert exc_info.value.code == 1
        assert "ingest.note and ingest.site_prompt are required" in capsys.readouterr().err

    @pytest.mark.unit
    def test_empty_note_exits_1(self, capsys):
        config = _ingest_config(note="")

        with pytest.raises(SystemExit) as exc_info:
            _run_ingest(config)

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_empty_site_prompt_exits_1(self, capsys):
        config = _ingest_config(site_prompt="")

        with pytest.raises(SystemExit) as exc_info:
            _run_ingest(config)

        assert exc_info.value.code == 1


class TestRunIngestUnknownStageKey:
    """Unknown keys in ``ingest.stages`` (multi-step mode) are a hard error."""

    @pytest.mark.unit
    def test_unknown_stage_key_exits_1(self, tmp_path, capsys):
        config = _real_ingest_config(
            tmp_path, multi_step=True, stages={"bogus-stage": {}}
        )

        with pytest.raises(SystemExit) as exc_info:
            _run_ingest(config)

        assert exc_info.value.code == 1
        assert "Unknown stage key" in capsys.readouterr().err


class TestRunIngestHappyPath:
    """A complete valid config dispatches to the ingestion entry points."""

    def _patch_ingestion_module(self, monkeypatch):
        """Swap out resourcery_ssg.data_ingestion with a fake.

        ``_run_ingest`` imports ``run_ingestion``/``run_multi_step_ingestion``
        *inside* the function, so the module must be replaced in sys.modules
        for the import to pick up the fakes.
        """
        fake = types.SimpleNamespace(
            run_ingestion=mock.Mock(return_value=None),
            run_multi_step_ingestion=mock.Mock(return_value=None),
        )
        monkeypatch.setitem(sys.modules, "resourcery_ssg.data_ingestion", fake)
        return fake

    @pytest.mark.unit
    def test_valid_single_step_dispatches_to_run_ingestion(
        self, tmp_path, monkeypatch
    ):
        fake = self._patch_ingestion_module(monkeypatch)
        config = _real_ingest_config(tmp_path)

        _run_ingest(config)

        fake.run_ingestion.assert_called_once()
        fake.run_multi_step_ingestion.assert_not_called()

    @pytest.mark.unit
    def test_valid_multi_step_dispatches_to_run_multi_step_ingestion(
        self, tmp_path, monkeypatch
    ):
        fake = self._patch_ingestion_module(monkeypatch)
        config = _real_ingest_config(
            tmp_path,
            multi_step=True,
            stages={"site.config": {"model": "gpt-4o"}, "links": {}},
        )

        _run_ingest(config)

        fake.run_multi_step_ingestion.assert_called_once()
        fake.run_ingestion.assert_not_called()


class TestRunIngestMissingInputFiles:
    """Referenced input paths must exist before dispatch.

    Regression: a deleted note file (path still in config) crashed with a
    raw FileNotFoundError traceback from ``Path(...).resolve(strict=True)``
    inside run_ingestion/run_multi_step_ingestion. Must be a clean
    ``Error: <label> path does not exist`` + exit 1, mirroring
    data_ingestion.main().
    """

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "key, label",
        [
            ("note", "note"),
            ("site_prompt", "site_prompt"),
            ("schemas_dir", "schemas_dir"),
            ("prompt", "prompt"),
        ],
    )
    def test_nonexistent_input_path_exits_1(self, tmp_path, capsys, key, label):
        config = _real_ingest_config(tmp_path)
        config["ingest"][key] = str(tmp_path / f"nonexistent-{key}")

        with pytest.raises(SystemExit) as exc_info:
            _run_ingest(config)

        assert exc_info.value.code == 1
        assert f"Error: {label} path does not exist" in capsys.readouterr().err

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "key, label", [("schemas_dir", "schemas_dir"), ("prompt", "prompt")]
    )
    def test_missing_required_path_key_exits_1(self, tmp_path, capsys, key, label):
        """Missing schemas_dir/prompt keys would KeyError at dispatch — clean error."""
        config = _real_ingest_config(tmp_path)
        del config["ingest"][key]

        with pytest.raises(SystemExit) as exc_info:
            _run_ingest(config)

        assert exc_info.value.code == 1
        assert f"Error: {label} is required" in capsys.readouterr().err


class TestRunIngestIntentionalSkips:
    """Missing ``ingest`` section / ``ingest.model`` stay silent skips (exit 0).

    These are documented as optional ingestion: ``site all`` must not fail on
    machines without ingestion config. Do NOT turn them into hard errors.
    """

    @pytest.mark.unit
    def test_no_ingest_section_skips_without_exit(self, capsys):
        _run_ingest({})  # must not raise SystemExit

        assert "No 'ingest' section" in capsys.readouterr().out

    @pytest.mark.unit
    def test_missing_model_skips_without_exit(self, capsys):
        config = _ingest_config(model=None)

        _run_ingest(config)  # must not raise SystemExit

        assert "ingest.model not set" in capsys.readouterr().out
