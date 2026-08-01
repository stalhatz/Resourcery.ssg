"""Tests for resourcery_ssg.logutil — level parsing, stream split, log files."""

import logging
import re
from pathlib import Path

import pytest

from resourcery_ssg.config import load_resourcery_config
from resourcery_ssg.logutil import (
    INFO_USER,
    get_logger,
    log_user,
    log_timing,
    parse_log_level,
    setup_logging,
    _OWNED_HANDLERS,
)


class TestParseLogLevel:
    @pytest.mark.unit
    def test_parse_level_case_insensitive(self):
        assert parse_log_level("debug") == logging.DEBUG
        assert parse_log_level("DEBUG") == logging.DEBUG
        assert parse_log_level("Warn") == logging.WARN
        assert parse_log_level("error") == logging.ERROR

    @pytest.mark.unit
    def test_parse_level_warning_alias(self):
        assert parse_log_level("WARNING") == logging.WARN

    @pytest.mark.unit
    def test_parse_level_invalid_raises(self):
        for value in ("BOGUS", "", None):
            with pytest.raises(ValueError):
                parse_log_level(value)


class TestStreamSplit:
    @pytest.mark.unit
    def test_stream_split_capsys(self, capsys):
        setup_logging({"logging": {"level": "INFO"}})
        logger = get_logger("resourcery_ssg.test_stream")
        log_user("user message")
        logger.info("info message")
        logger.warning("warn message")
        logger.error("error message")
        captured = capsys.readouterr()
        assert "user message" in captured.out
        assert "info message" in captured.out
        assert "warn message" in captured.err
        assert "error message" in captured.err
        assert "warn message" not in captured.out
        assert "error message" not in captured.out

    @pytest.mark.unit
    def test_info_user_plain_text(self, capsys):
        setup_logging({"logging": {"level": "INFO"}})
        log_user("Hello user")
        assert capsys.readouterr().out.strip() == "Hello user"

    @pytest.mark.unit
    def test_info_user_hidden_at_warn_threshold(self, capsys):
        setup_logging({"logging": {"level": "WARN"}})
        logger = get_logger("resourcery_ssg.test_hidden")
        log_user("hidden user text")
        logger.warning("visible warn")
        captured = capsys.readouterr()
        assert "hidden user text" not in captured.out
        assert "visible warn" in captured.err

    @pytest.mark.unit
    def test_info_user_absent_from_file(self, tmp_path, capsys):
        setup_logging(
            {
                "logging": {
                    "level": "INFO",
                    "file_level": "DEBUG",
                    "logs_dir": str(tmp_path / "logs"),
                }
            }
        )
        logger = get_logger("resourcery_ssg.test_file_absent")
        log_user("user-only message")
        logger.debug("debug detail")
        logs = list((tmp_path / "logs").glob("resourcery-*.log"))
        assert len(logs) == 1
        content = logs[0].read_text(encoding="utf-8")
        assert "debug detail" in content
        assert "user-only message" not in content

    @pytest.mark.unit
    def test_file_name_pattern(self, tmp_path):
        setup_logging({"logging": {"logs_dir": str(tmp_path / "logs")}})
        logger = get_logger("resourcery_ssg.test_file_name")
        logger.info("ping")
        logs = list((tmp_path / "logs").glob("resourcery-*.log"))
        assert len(logs) == 1
        assert re.fullmatch(r"resourcery-\d{8}-\d{6}\.log", logs[0].name)

    @pytest.mark.unit
    def test_file_level_honored(self, tmp_path):
        setup_logging(
            {
                "logging": {
                    "level": "DEBUG",
                    "file_level": "INFO",
                    "logs_dir": str(tmp_path / "logs"),
                }
            }
        )
        logger = get_logger("resourcery_ssg.test_file_level")
        logger.debug("debug line")
        logger.info("info line")
        content = list((tmp_path / "logs").glob("resourcery-*.log"))[0].read_text(
            encoding="utf-8"
        )
        assert "info line" in content
        assert "debug line" not in content

        # file_level DEBUG → DEBUG detail lands in the file
        setup_logging(
            {
                "logging": {
                    "level": "DEBUG",
                    "file_level": "DEBUG",
                    "logs_dir": str(tmp_path / "logs2"),
                }
            }
        )
        logger.debug("debug line 2")
        content2 = list((tmp_path / "logs2").glob("resourcery-*.log"))[0].read_text(
            encoding="utf-8"
        )
        assert "debug line 2" in content2

    @pytest.mark.unit
    def test_structured_format_fields(self, capsys):
        setup_logging({"logging": {"level": "DEBUG"}})
        logger = get_logger("resourcery_ssg.test_format")
        logger.debug("debug message")
        out = capsys.readouterr().out
        pattern = re.compile(
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| "
            r"(DEBUG|INFO|WARN|ERROR) +\| [\w.]+:\d+ \w+ \| .+$"
        )
        assert pattern.match(out.strip())

    @pytest.mark.unit
    def test_logs_dir_created_on_demand(self, tmp_path):
        nested = tmp_path / "a" / "b" / "logs"
        assert not nested.exists()
        setup_logging({"logging": {"logs_dir": str(nested)}})
        assert nested.is_dir()

    @pytest.mark.unit
    def test_setup_logging_idempotent(self, tmp_path, capsys):
        config = {"logging": {"level": "INFO", "logs_dir": str(tmp_path / "logs")}}
        setup_logging(config)
        setup_logging(config)
        logger = get_logger("resourcery_ssg.test_idempotent")
        logger.info("only once")
        captured = capsys.readouterr()
        assert captured.out.count("only once") == 1
        # Re-configuration replaces the previous handlers (no duplicates,
        # no growth): exactly the 3 owned handlers remain attached.
        assert len(_OWNED_HANDLERS) == 3
        root = logging.getLogger()
        for handler in _OWNED_HANDLERS:
            assert handler in root.handlers

    @pytest.mark.unit
    def test_get_logger_works_without_setup_logging(self, capsys):
        root = logging.getLogger()
        old_handlers = list(root.handlers)
        try:
            root.handlers = []
            logger = get_logger("bare.logger")
            logger.warning("bare warning")
            logger.info("bare info")
            log_user("bare user")
            captured = capsys.readouterr()
            assert "bare warning" in captured.err
            assert "bare info" not in captured.out
            assert "bare user" not in captured.out
        finally:
            root.handlers = old_handlers

    @pytest.mark.unit
    def test_precedence_chain(self, tmp_path, monkeypatch):
        user_cfg = tmp_path / "user.yaml"
        user_cfg.write_text("logging:\n  level: WARN\n", encoding="utf-8")

        # Committed default (no env, no user config): INFO
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        assert load_resourcery_config()["logging"]["level"] == "INFO"

        # User config beats committed default
        assert (
            load_resourcery_config(config_path=user_cfg)["logging"]["level"] == "WARN"
        )

        # Env LOG_LEVEL beats committed default (via ${LOG_LEVEL})
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        assert load_resourcery_config()["logging"]["level"] == "DEBUG"

        # CLI override beats env
        config = load_resourcery_config(
            config_path=user_cfg, overrides={"logging.level": "ERROR"}
        )
        assert config["logging"]["level"] == "ERROR"


class TestLogTiming:
    @pytest.mark.unit
    def test_log_timing_emits_formatted_record(self, caplog):
        logger = get_logger("resourcery_ssg.test_timing")
        with caplog.at_level(logging.DEBUG):
            with log_timing(logger, "Phase"):
                pass
        assert any(
            re.search(r"^Phase completed in \d+\.\d+s$", r.message)
            for r in caplog.records
        )

    @pytest.mark.unit
    def test_log_timing_fires_on_exception(self, caplog):
        logger = get_logger("resourcery_ssg.test_timing_exc")
        with pytest.raises(RuntimeError):
            with caplog.at_level(logging.DEBUG):
                with log_timing(logger, "Phase"):
                    raise RuntimeError("x")
        assert any(
            re.search(r"^Phase completed in \d+\.\d+s$", r.message)
            for r in caplog.records
        )

    @pytest.mark.unit
    def test_log_timing_level_param(self, caplog):
        logger = get_logger("resourcery_ssg.test_timing_level")
        with caplog.at_level(logging.DEBUG):
            with log_timing(logger, "Command", level=logging.INFO):
                pass
        assert any(
            r.levelno == logging.INFO
            and re.search(r"^Command completed in \d+\.\d+s$", r.message)
            for r in caplog.records
        )


class TestNonEmptyLogFile:
    @pytest.mark.integration
    def test_successful_run_writes_nonempty_log_file(
        self, testdata_dir, tmp_path, monkeypatch
    ):
        """A real validate_all() run at DEBUG leaves a non-empty log file.

        Rides the autouse fixture's file handler (LOGS_DIR=tmp_path/logs):
        the file must contain structured INFO+DEBUG records and no
        INFO_USER text.
        """
        from resourcery_ssg.validate import DataValidator

        monkeypatch.setattr(
            "resourcery_ssg.font_acquirer.extract_google_font_candidates",
            lambda stack: [],
        )
        schemas_dir = Path(__file__).resolve().parent.parent / "schemas"
        validator = DataValidator(data_dir=testdata_dir, schemas_dir=schemas_dir)
        assert validator.validate_all()

        logs_dir = tmp_path / "logs"
        files = list(logs_dir.glob("resourcery-*.log"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert content.strip()  # non-empty
        assert "| INFO" in content
        assert "| DEBUG" in content
        assert "✅" not in content
        assert "Loaded 3 schemas" in content
        assert re.search(r"\d+ warnings, \d+ errors collected", content)
