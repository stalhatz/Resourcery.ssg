"""Tests for the config module (src/resourcery_ssg/config.py)."""

import os
import argparse
import yaml
import pytest
from pathlib import Path
from types import MappingProxyType

from resourcery_ssg.config import (
    load_resourcery_config,
    ConfigError,
    build_cli_overrides,
    _resolve_var,
    _deep_merge,
)


class TestResolveVar:
    @pytest.mark.unit
    def test_resolves_from_env(self):
        env = {"HOME": "/home/user"}
        assert _resolve_var("${HOME}/data", env, {}) == "/home/user/data"

    @pytest.mark.unit
    def test_resolves_from_vars_dict(self):
        env = {}
        vars_dict = {"DATA_DIR": "./data"}
        assert _resolve_var("${DATA_DIR}/links.json", env, vars_dict) == "./data/links.json"

    @pytest.mark.unit
    def test_env_overrides_vars_dict(self):
        env = {"DATA_DIR": "/env/data"}
        vars_dict = {"DATA_DIR": "./data"}
        assert _resolve_var("${DATA_DIR}", env, vars_dict) == "/env/data"

    @pytest.mark.unit
    def test_leaves_unresolved_as_is(self):
        env = {}
        vars_dict = {}
        assert _resolve_var("${UNKNOWN}", env, vars_dict) == "${UNKNOWN}"

    @pytest.mark.unit
    def test_multiple_vars_in_string(self):
        env = {"A": "x", "B": "y"}
        assert _resolve_var("${A}/${B}", env, {}) == "x/y"


class TestDeepMerge:
    @pytest.mark.unit
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        overlay = {"b": 3, "c": 4}
        result = _deep_merge(base, overlay)
        assert result == {"a": 1, "b": 3, "c": 4}

    @pytest.mark.unit
    def test_nested_merge(self):
        base = {"build": {"data": "./data", "output": "./output"}}
        overlay = {"build": {"output": "/tmp/out"}}
        result = _deep_merge(base, overlay)
        assert result == {"build": {"data": "./data", "output": "/tmp/out"}}

    @pytest.mark.unit
    def test_does_not_mutate_base(self):
        base = {"a": [1, 2]}
        overlay = {"b": 3}
        result = _deep_merge(base, overlay)
        assert base == {"a": [1, 2]}
        assert result == {"a": [1, 2], "b": 3}


class TestBuildCliOverrides:
    @pytest.mark.unit
    def test_builds_dotted_keys(self):
        args = argparse.Namespace(data="x", output="y")
        result = build_cli_overrides(
            args, "build", {"data": "data_dir", "output": "output_dir"}
        )
        assert result == {"build.data_dir": "x", "build.output_dir": "y"}

    @pytest.mark.unit
    def test_skips_none_values(self):
        args = argparse.Namespace(data=None, output="y")
        result = build_cli_overrides(
            args, "build", {"data": "data_dir", "output": "output_dir"}
        )
        assert result == {"build.output_dir": "y"}

    @pytest.mark.unit
    def test_tolerates_missing_attribute(self):
        args = argparse.Namespace(data="x")
        result = build_cli_overrides(
            args, "build", {"data": "data_dir", "output": "output_dir"}
        )
        assert result == {"build.data_dir": "x"}

    @pytest.mark.unit
    def test_empty_mapping(self):
        assert build_cli_overrides(argparse.Namespace(), "build", {}) == {}


class TestLoadResourceryConfig:
    @pytest.mark.unit
    def test_loads_committed_config(self):
        """Loading without arguments should use the committed config.yaml defaults."""
        config = load_resourcery_config()
        assert "build" in config
        assert "validate" in config
        assert "acquire-fonts" in config
        assert "acquire-images" in config

        # Verify default paths resolve to Path objects
        build_cfg = config["build"]
        assert isinstance(build_cfg["data_dir"], Path)
        assert isinstance(build_cfg["output_dir"], Path)

    @pytest.mark.unit
    def test_env_var_overrides_vars_section(self, monkeypatch):
        """Environment variables should override vars in the committed config."""
        monkeypatch.setenv("DATA_DIR", "/env/data")
        monkeypatch.setenv("STATIC_DIR", "/env/static")
        config = load_resourcery_config()
        # build.data_dir should use DATA_DIR from env
        assert str(config["build"]["data_dir"]) == str(Path("/env/data").resolve())
        assert str(config["validate"]["data_dir"]) == str(Path("/env/data").resolve())

    @pytest.mark.unit
    def test_cli_overrides_config(self, tmp_path: Path):
        """CLI overrides should take highest priority."""
        config = load_resourcery_config(
            overrides={"build.output_dir": str(tmp_path / "custom-out")}
        )
        assert str(config["build"]["output_dir"]) == str((tmp_path / "custom-out").resolve())

    @pytest.mark.unit
    def test_var_resolution_chain(self, tmp_path: Path, monkeypatch):
        """Test the full resolution chain: env > user vars > committed vars."""
        user_cfg = tmp_path / "user_config.yaml"
        user_cfg.write_text(
            yaml.safe_dump({
                "vars": {"DATA_DIR": "./user-data"},
                "build": {"data_dir": "${DATA_DIR}"},
            }),
            encoding="utf-8",
        )

        # Without env var, should use user config's vars
        config = load_resourcery_config(config_path=user_cfg)
        assert str(config["build"]["data_dir"]).endswith("user-data")

        # With env var, should use env
        monkeypatch.setenv("DATA_DIR", "/env-override")
        config = load_resourcery_config(config_path=user_cfg)
        assert str(config["build"]["data_dir"]) == str(Path("/env-override").resolve())

    @pytest.mark.unit
    def test_user_config_merges_with_committed(self, tmp_path: Path):
        """User config should deep-merge with committed config."""
        user_cfg = tmp_path / "user_config.yaml"
        user_cfg.write_text(
            yaml.safe_dump({
                "build": {"output_dir": "./custom-output"},
            }),
            encoding="utf-8",
        )
        config = load_resourcery_config(config_path=user_cfg)
        # build.output_dir should be overridden
        assert str(config["build"]["output_dir"]).endswith("custom-output")
        # build.data_dir should still come from committed config
        assert config["build"]["data_dir"] is not None

    @pytest.mark.unit
    def test_returns_frozen_dict(self):
        """The returned config should be read-only."""
        config = load_resourcery_config()
        with pytest.raises(TypeError):
            config["build"] = {}  # type: ignore
        with pytest.raises(TypeError):
            config["build"]["data_dir"] = "/fake"  # type: ignore

    @pytest.mark.unit
    def test_missing_user_config_errors(self):
        """A non-existent user config path should raise ConfigError."""
        with pytest.raises(ConfigError, match="not found"):
            load_resourcery_config(config_path="/nonexistent/config.yaml")

    @pytest.mark.unit
    def test_validate_section_paths(self):
        """Validate section should have data_dir and schemas_dir as Paths."""
        config = load_resourcery_config()
        validate_cfg = config["validate"]
        assert isinstance(validate_cfg["data_dir"], Path)
        assert isinstance(validate_cfg["schemas_dir"], Path)

    @pytest.mark.unit
    def test_acquire_fonts_section_paths(self):
        """Acquire-fonts section should have data_dir, fonts_dir, css_dir as Paths."""
        config = load_resourcery_config()
        fonts_cfg = config["acquire-fonts"]
        assert isinstance(fonts_cfg["data_dir"], Path)
        assert isinstance(fonts_cfg["fonts_dir"], Path)
        assert isinstance(fonts_cfg["css_dir"], Path)

    @pytest.mark.unit
    def test_acquire_images_section_paths(self):
        """Acquire-images section should have links and images_dir as Paths."""
        config = load_resourcery_config()
        images_cfg = config["acquire-images"]
        assert isinstance(images_cfg["links"], Path)
        assert isinstance(images_cfg["images_dir"], Path)


class TestLoggingSection:
    """The new top-level ``logging`` section rides the config machinery unchanged."""

    @pytest.mark.unit
    def test_logging_section_resolves(self):
        config = load_resourcery_config()
        logging_cfg = config["logging"]
        assert logging_cfg["level"] == "INFO"  # level strings stay strings
        assert logging_cfg["file_level"] == "DEBUG"
        assert isinstance(logging_cfg["logs_dir"], Path)
        assert str(logging_cfg["logs_dir"]).endswith("logs")

    @pytest.mark.unit
    def test_logging_level_dotted_override(self):
        config = load_resourcery_config(overrides={"logging.level": "ERROR"})
        assert config["logging"]["level"] == "ERROR"

    @pytest.mark.unit
    def test_log_level_env_override(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        config = load_resourcery_config()
        assert config["logging"]["level"] == "DEBUG"

    @pytest.mark.unit
    def test_logs_dir_env_override(self, monkeypatch):
        monkeypatch.setenv("LOGS_DIR", "/tmp/custom-logs")
        config = load_resourcery_config()
        assert str(config["logging"]["logs_dir"]) == str(Path("/tmp/custom-logs").resolve())
