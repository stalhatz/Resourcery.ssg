"""Tests for resourcery_ssg.site — the ``site`` CLI command dispatch module."""

import sys
import types
from pathlib import Path
from unittest import mock

import pytest

from resourcery_ssg import site
from resourcery_ssg.errors import ResourceryError
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

        with pytest.raises(ResourceryError) as exc_info:
            _run_ingest(config)

        assert "ingest.note and ingest.site_prompt are required" in str(exc_info.value)
        assert "ingest.note and ingest.site_prompt are required" in capsys.readouterr().err

    @pytest.mark.unit
    def test_missing_site_prompt_exits_1(self, capsys):
        config = _ingest_config()
        del config["ingest"]["site_prompt"]

        with pytest.raises(ResourceryError) as exc_info:
            _run_ingest(config)

        assert "ingest.note and ingest.site_prompt are required" in str(exc_info.value)
        assert "ingest.note and ingest.site_prompt are required" in capsys.readouterr().err

    @pytest.mark.unit
    def test_empty_note_exits_1(self, capsys):
        config = _ingest_config(note="")

        with pytest.raises(ResourceryError) as exc_info:
            _run_ingest(config)

        assert "ingest.note and ingest.site_prompt are required" in str(exc_info.value)

    @pytest.mark.unit
    def test_empty_site_prompt_exits_1(self, capsys):
        config = _ingest_config(site_prompt="")

        with pytest.raises(ResourceryError) as exc_info:
            _run_ingest(config)

        assert "ingest.note and ingest.site_prompt are required" in str(exc_info.value)


class TestRunIngestUnknownStageKey:
    """Unknown keys in ``ingest.stages`` (multi-step mode) are a hard error."""

    @pytest.mark.unit
    def test_unknown_stage_key_exits_1(self, tmp_path, capsys):
        config = _real_ingest_config(
            tmp_path, multi_step=True, stages={"bogus-stage": {}}
        )

        with pytest.raises(ResourceryError) as exc_info:
            _run_ingest(config)

        assert "Unknown stage key" in str(exc_info.value)
        assert "Unknown stage key" in capsys.readouterr().err


class TestRunIngestHappyPath:
    """A complete valid config dispatches to the ingestion entry points."""

    def _patch_ingestion_module(self, monkeypatch):
        """Swap out resourcery_ssg.data_ingestion with a fake.

        ``_run_ingest`` imports ``run_ingestion``/``run_multi_step_ingestion``
        *inside* the function, so the module must be replaced in sys.modules
        for the import to pick up the fakes. The real ``build_stage_config``
        is kept so the stage-config parsing still runs against production
        code.
        """
        from resourcery_ssg.data_ingestion import build_stage_config

        fake = types.SimpleNamespace(
            run_ingestion=mock.Mock(return_value=None),
            run_multi_step_ingestion=mock.Mock(return_value=None),
            build_stage_config=build_stage_config,
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

        with pytest.raises(ResourceryError) as exc_info:
            _run_ingest(config)

        assert f"Error: {label} path does not exist" in str(exc_info.value)
        assert f"Error: {label} path does not exist" in capsys.readouterr().err

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "key, label", [("schemas_dir", "schemas_dir"), ("prompt", "prompt")]
    )
    def test_missing_required_path_key_exits_1(self, tmp_path, capsys, key, label):
        """Missing schemas_dir/prompt keys would KeyError at dispatch — clean error."""
        config = _real_ingest_config(tmp_path)
        del config["ingest"][key]

        with pytest.raises(ResourceryError) as exc_info:
            _run_ingest(config)

        assert f"Error: {label} is required" in str(exc_info.value)
        assert f"Error: {label} is required" in capsys.readouterr().err


class TestRunIngestIntentionalSkips:
    """Missing ``ingest`` section / ``ingest.model`` stay silent skips (exit 0).

    These are documented as optional ingestion: ``site all`` must not fail on
    machines without ingestion config. Do NOT turn them into hard errors.
    """

    @pytest.mark.unit
    def test_no_ingest_section_skips_without_exit(self, capsys):
        _run_ingest({})  # must not raise

        assert "No 'ingest' section" in capsys.readouterr().err

    @pytest.mark.unit
    def test_missing_model_skips_without_exit(self, capsys):
        config = _ingest_config(model=None)

        _run_ingest(config)  # must not raise

        assert "ingest.model not set" in capsys.readouterr().err


class TestRunAllFailureAborts:
    """Failure handling in the ``all`` pipeline (``_run_all``/``main`` catch-all).

    The font and JS steps carry their own abort lines; build/ingest failures
    propagate to the ``site.main()`` catch-all, which adds no text (exit 1).
    """

    @staticmethod
    def _write_all_config(
        tmp_path: Path, testdata_dir: Path, *, js_section: bool = False
    ) -> Path:
        """Write a minimal 5-step pipeline config (ingest disabled).

        ``ingest.model`` is nulled so the pipeline has 5 steps; no
        ``build.static_source`` so ``seed_static_staging`` no-ops; the
        links file does not exist so the real ``acquire_images_from_config``
        warn-and-continues (row 14 unchanged). With ``js_section=True`` an
        ``acquire-js`` section pointing at tmp paths is appended.
        """
        lines = [
            "build:",
            f"  data_dir: {testdata_dir}",
            f"  templates_dir: {testdata_dir / 'templates'}",
            f"  static_dir: {testdata_dir / 'static'}",
            f"  output_dir: {tmp_path / 'output'}",
            "validate:",
            f"  data_dir: {testdata_dir}",
            f"  schemas_dir: {Path(__file__).resolve().parent.parent / 'schemas'}",
            "acquire-fonts:",
            f"  data_dir: {testdata_dir}",
            f"  fonts_dir: {tmp_path / 'fonts'}",
            f"  css_dir: {tmp_path / 'css'}",
            "acquire-images:",
            f"  links: {tmp_path / 'nonexistent-links.json'}",
            f"  images_dir: {tmp_path / 'images'}",
            "ingest:",
            "  model: null",
        ]
        if js_section:
            lines += [
                "acquire-js:",
                f"  package_json_path: {tmp_path / 'pkg.json'}",
                f"  vendor_dir: {tmp_path / 'vendor'}",
            ]
        cfg = tmp_path / "config.yaml"
        cfg.write_text("\n".join(lines), encoding="utf-8")
        return cfg

    @pytest.mark.unit
    def test_run_all_font_failure_aborts(self, tmp_path, testdata_dir, monkeypatch, capsys):
        """Font failure keeps its abort line and exits 1 from ``_run_all``."""
        cfg = self._write_all_config(tmp_path, testdata_dir)

        def raising_fonts(**kwargs):
            raise ResourceryError("boom")

        monkeypatch.setattr("resourcery_ssg.font_acquirer.acquire_fonts", raising_fonts)

        args = site._build_parser().parse_args(["--config", str(cfg), "all"])
        with pytest.raises(SystemExit) as exc_info:
            site._run_all(args)

        assert exc_info.value.code == 1
        assert "Font acquisition failed. Aborting pipeline." in capsys.readouterr().err

    @pytest.mark.unit
    def test_run_all_build_failure_no_abort_line(
        self, tmp_path, testdata_dir, monkeypatch, capsys
    ):
        """Build failure exits 1 via the main() catch-all with no abort line."""
        cfg = self._write_all_config(tmp_path, testdata_dir)
        monkeypatch.setattr(
            "resourcery_ssg.font_acquirer.acquire_fonts", lambda **kwargs: None
        )
        monkeypatch.setattr("resourcery_ssg.js_vendor.acquire_js", lambda **kwargs: None)

        def raising_build(**kwargs):
            raise ResourceryError("boom")

        monkeypatch.setattr("resourcery_ssg.build.build_site", raising_build)
        monkeypatch.setattr(sys, "argv", ["site", "--config", str(cfg), "all"])

        with pytest.raises(SystemExit) as exc_info:
            site.main()

        assert exc_info.value.code == 1
        assert "Aborting pipeline" not in capsys.readouterr().out

    @pytest.mark.unit
    def test_run_all_validate_failure_aborts(self, tmp_path, testdata_dir, monkeypatch, capsys):
        """Validate step failure keeps its abort line and exits 1 from ``_run_all``."""
        cfg = self._write_all_config(tmp_path, testdata_dir)
        monkeypatch.setattr(
            "resourcery_ssg.validate.DataValidator.validate_all", lambda self: False
        )

        args = site._build_parser().parse_args(["--config", str(cfg), "all"])
        with pytest.raises(SystemExit) as exc_info:
            site._run_all(args)

        assert exc_info.value.code == 1
        assert "Validation failed. Aborting pipeline." in capsys.readouterr().err

    @pytest.mark.unit
    def test_main_catchall_ingest_failure_exits_1(self, tmp_path, monkeypatch, capsys):
        """``site.main()`` catch-all: ingest failure → SystemExit(1), no print."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text("ingest:\n  model: gpt-4o\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["site", "--config", str(cfg), "ingest"])

        with pytest.raises(SystemExit) as exc_info:
            site.main()

        assert exc_info.value.code == 1
        assert "ingest.note and ingest.site_prompt are required" in capsys.readouterr().err


class TestRunAllJsStep:
    """``site all`` step 3 (acquire-js): config kwargs and abort behavior."""

    @pytest.mark.unit
    def test_run_all_acquire_js_receives_config_kwargs(
        self, tmp_path, testdata_dir, monkeypatch
    ):
        """``_run_all`` must pass ``config["acquire-js"]`` to ``acquire_js``.

        Regression: the bare ``acquire_js()`` call silently ignored
        overridden ``acquire-js`` keys (and the ``--package-json`` /
        ``--vendor-dir`` flags). The spy kwargs must equal the *resolved*
        config values (Path objects), never raw YAML strings.
        """
        cfg = TestRunAllFailureAborts._write_all_config(
            tmp_path, testdata_dir, js_section=True
        )

        captured_kwargs = {}

        def js_spy(**kwargs):
            captured_kwargs.update(kwargs)

        monkeypatch.setattr("resourcery_ssg.js_vendor.acquire_js", js_spy)
        monkeypatch.setattr(
            "resourcery_ssg.font_acquirer.acquire_fonts", lambda **kwargs: None
        )
        monkeypatch.setattr("resourcery_ssg.build.build_site", lambda **kwargs: None)
        captured = TestLogLevelFlag._spy_load_config(monkeypatch)
        args = site._build_parser().parse_args(["--config", str(cfg), "all"])
        site._run_all(args)

        assert len(captured_kwargs) == 2
        assert captured_kwargs == dict(captured["config"]["acquire-js"])

    @pytest.mark.unit
    def test_run_all_js_failure_aborts(
        self, tmp_path, testdata_dir, monkeypatch, capsys
    ):
        """JS failure keeps its abort line and exits 1 from ``_run_all``."""
        cfg = TestRunAllFailureAborts._write_all_config(tmp_path, testdata_dir)
        monkeypatch.setattr(
            "resourcery_ssg.font_acquirer.acquire_fonts", lambda **kwargs: None
        )

        def raising_js(**kwargs):
            raise ResourceryError("boom")

        monkeypatch.setattr("resourcery_ssg.js_vendor.acquire_js", raising_js)
        args = site._build_parser().parse_args(["--config", str(cfg), "all"])
        with pytest.raises(SystemExit) as exc_info:
            site._run_all(args)

        assert exc_info.value.code == 1
        assert "JS acquisition failed. Aborting pipeline." in capsys.readouterr().err


class TestBuildMainDispatch:
    """Standalone ``build`` main() dispatch semantics (kwargs + staging seed)."""

    @pytest.mark.unit
    def test_build_main_filters_static_source(
        self, tmp_path, testdata_dir, monkeypatch
    ):
        """``static_source`` must never reach ``build_site`` kwargs.

        Regression: ``build_kwargs = dict(config["build"])`` forwarded
        ``static_source`` into ``build_site()`` (no such parameter → latent
        TypeError on every real-world config).
        """
        from resourcery_ssg.build import main as build_main

        cfg = TestLogLevelFlag._write_build_config(
            tmp_path, testdata_dir, static_source=tmp_path / "source"
        )
        captured = {}

        def build_spy(**kwargs):
            captured["kwargs"] = kwargs

        monkeypatch.setattr("resourcery_ssg.build.build_site", build_spy)
        monkeypatch.setattr(sys, "argv", ["build", "--config", str(cfg)])

        build_main()

        assert "static_source" not in captured["kwargs"]
        assert set(captured["kwargs"]) >= {
            "data_dir",
            "templates_dir",
            "static_dir",
            "output_dir",
            "ingest_note",
            "ingest_site_prompt",
        }

    @pytest.mark.unit
    def test_build_main_seeds_staging_before_build(
        self, tmp_path, testdata_dir, monkeypatch
    ):
        """Standalone ``build`` seeds static staging before dispatching.

        The file-exists assertion inside the ``build_site`` spy proves both
        that seeding ran and that it ran *before* the build dispatch (the
        seed is the only writer of that file).
        """
        from resourcery_ssg.build import main as build_main

        source = tmp_path / "source"
        source.mkdir()
        (source / "asset.txt").write_text("A", encoding="utf-8")
        static_dir = tmp_path / "static"
        cfg = TestLogLevelFlag._write_build_config(
            tmp_path, testdata_dir, static_source=source, static_dir=static_dir
        )
        captured = {"kwargs": None}

        def build_spy(**kwargs):
            assert (static_dir / "asset.txt").exists()  # seeded before build
            captured["kwargs"] = kwargs

        monkeypatch.setattr("resourcery_ssg.build.build_site", build_spy)
        monkeypatch.setattr(sys, "argv", ["build", "--config", str(cfg)])

        build_main()

        assert captured["kwargs"] is not None
        assert "static_source" not in captured["kwargs"]
        assert (static_dir / "asset.txt").read_text(encoding="utf-8") == "A"

    @pytest.mark.unit
    def test_build_main_missing_static_source_warns_and_builds(
        self, tmp_path, testdata_dir, monkeypatch, capsys
    ):
        """A nonexistent ``static_source`` warns and skips, build still runs."""
        from resourcery_ssg.build import main as build_main

        cfg = TestLogLevelFlag._write_build_config(
            tmp_path, testdata_dir, static_source=tmp_path / "nonexistent"
        )
        captured = {"kwargs": None}

        def build_spy(**kwargs):
            captured["kwargs"] = kwargs

        monkeypatch.setattr("resourcery_ssg.build.build_site", build_spy)
        monkeypatch.setattr(sys, "argv", ["build", "--config", str(cfg)])

        build_main()
        captured_streams = capsys.readouterr()

        assert "static_source not found" in captured_streams.err
        assert "— skipping" in captured_streams.err
        assert captured["kwargs"] is not None
        assert "static_source" not in captured["kwargs"]


class TestLogLevelFlag:
    """--log-level is accepted on every subparser and maps to logging.level."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "command",
        [
            "build",
            "validate",
            "acquire-fonts",
            "acquire-js",
            "acquire-images",
            "ingest",
            "all",
        ],
    )
    def test_all_subparsers_accept_log_level(self, command):
        args = site._build_parser().parse_args([command, "--log-level", "debug"])
        assert args.log_level == "debug"

    @staticmethod
    def _write_build_config(
        tmp_path: Path,
        testdata_dir: Path,
        *,
        static_source: Path | None = None,
        static_dir: Path | None = None,
    ) -> Path:
        lines = [
            "build:",
            f"  data_dir: {testdata_dir}",
            f"  templates_dir: {testdata_dir / 'templates'}",
            f"  static_dir: {static_dir or (testdata_dir / 'static')}",
            f"  output_dir: {tmp_path / 'output'}",
        ]
        if static_source is not None:
            lines.append(f"  static_source: {static_source}")
        cfg = tmp_path / "config.yaml"
        cfg.write_text("\n".join(lines), encoding="utf-8")
        return cfg

    @staticmethod
    def _spy_load_config(monkeypatch):
        """Wrap load_resourcery_config, capturing the resolved config."""
        import resourcery_ssg.config as config_mod

        captured = {}
        original = config_mod.load_resourcery_config

        def spy(config_path=None, overrides=None):
            result = original(config_path=config_path, overrides=overrides)
            captured["config"] = result
            return result

        monkeypatch.setattr(config_mod, "load_resourcery_config", spy)
        return captured

    @pytest.mark.unit
    def test_main_build_log_level_reaches_config(
        self, tmp_path, testdata_dir, monkeypatch
    ):
        cfg = self._write_build_config(tmp_path, testdata_dir)
        captured = self._spy_load_config(monkeypatch)
        monkeypatch.setattr("resourcery_ssg.build.build_site", lambda **kwargs: None)
        monkeypatch.setattr(
            sys,
            "argv",
            ["site", "--config", str(cfg), "build", "--log-level", "DEBUG"],
        )

        site.main()

        assert captured["config"]["logging"]["level"] == "DEBUG"

    @pytest.mark.unit
    def test_build_main_log_level_reaches_config(
        self, tmp_path, testdata_dir, monkeypatch
    ):
        from resourcery_ssg.build import main as build_main

        cfg = self._write_build_config(tmp_path, testdata_dir)
        captured = self._spy_load_config(monkeypatch)
        monkeypatch.setattr("resourcery_ssg.build.build_site", lambda **kwargs: None)
        monkeypatch.setattr(
            sys,
            "argv",
            ["build", "--config", str(cfg), "--log-level", "debug"],
        )

        build_main()

        assert captured["config"]["logging"]["level"] == "debug"


class TestOperationalRecords:
    """Step 7 operational INFO/DEBUG records emitted by the site dispatch."""

    @pytest.mark.unit
    def test_main_all_emits_dispatch_and_timing_records(
        self, tmp_path, testdata_dir, monkeypatch, caplog
    ):
        """`site all --log-level DEBUG` documents dispatch, overrides, timings.

        Uses the same hermetic config as TestRunAllFailureAborts; the
        Dispatch record carries the config-path variant because --config
        is required to point the pipeline at testdata.
        """
        import logging
        import re

        cfg = TestRunAllFailureAborts._write_all_config(tmp_path, testdata_dir)
        monkeypatch.setattr(
            "resourcery_ssg.font_acquirer.acquire_fonts", lambda **kwargs: None
        )
        monkeypatch.setattr("resourcery_ssg.js_vendor.acquire_js", lambda **kwargs: None)
        monkeypatch.setattr("resourcery_ssg.build.build_site", lambda **kwargs: None)
        monkeypatch.setattr(
            sys,
            "argv",
            ["site", "--config", str(cfg), "all", "--log-level", "DEBUG"],
        )

        caplog.set_level(logging.DEBUG)
        site.main()

        assert any(
            r.levelno == logging.INFO
            and re.search(r"^Dispatch: all \(config .+\)$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.DEBUG
            and re.search(r"^Config overrides: logging\.level=DEBUG$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.DEBUG
            and re.search(r"^Step 'validate' completed in \d+\.\d+s$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.INFO
            and re.search(r"^Command completed in \d+\.\d+s$", r.message)
            for r in caplog.records
        )


class TestSiteDispatchExits:
    """Entry-point dispatch exits in ``site.main()`` (non-``all`` commands)."""

    @staticmethod
    def _write_validate_config(tmp_path: Path, testdata_dir: Path) -> Path:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "\n".join(
                [
                    "validate:",
                    f"  data_dir: {testdata_dir}",
                    f"  schemas_dir: {Path(__file__).resolve().parent.parent / 'schemas'}",
                ]
            ),
            encoding="utf-8",
        )
        return cfg

    @pytest.mark.unit
    def test_validate_dispatch_exits_1_on_failure(
        self, tmp_path, testdata_dir, monkeypatch, capsys
    ):
        """``site validate`` with failed validation → SystemExit(1)."""
        cfg = self._write_validate_config(tmp_path, testdata_dir)
        monkeypatch.setattr(
            "resourcery_ssg.validate.DataValidator.validate_all", lambda self: False
        )
        monkeypatch.setattr(sys, "argv", ["site", "--config", str(cfg), "validate"])

        with pytest.raises(SystemExit) as exc_info:
            site.main()

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_acquire_images_dispatch_exits_1_on_missing_links(
        self, tmp_path, monkeypatch, capsys
    ):
        """``site acquire-images`` with a missing links file → SystemExit(1)."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "\n".join(
                [
                    "acquire-images:",
                    f"  links: {tmp_path / 'nonexistent-links.json'}",
                    f"  images_dir: {tmp_path / 'images'}",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            sys, "argv", ["site", "--config", str(cfg), "acquire-images"]
        )

        with pytest.raises(SystemExit) as exc_info:
            site.main()

        assert exc_info.value.code == 1
        assert "Links file not found" in capsys.readouterr().err
