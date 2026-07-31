"""Unit tests for resourcery_ssg.io_utils — JSON loading helpers."""

import json
import pytest
from pathlib import Path

from resourcery_ssg.io_utils import JsonLoadError, load_json, loads_json


class TestJsonLoadError:
    @pytest.mark.unit
    def test_is_value_error_subclass(self):
        assert issubclass(JsonLoadError, ValueError)

    @pytest.mark.unit
    def test_stores_path_and_cause(self):
        cause = ValueError("boom")
        exc = JsonLoadError("bad json", path=Path("/tmp/x.json"), cause=cause)
        assert exc.path == Path("/tmp/x.json")
        assert exc.cause is cause


class TestLoadJson:
    @pytest.mark.unit
    def test_loads_valid_json(self, testdata_dir: Path):
        config = load_json(testdata_dir / "site.config.json")
        assert isinstance(config, dict)
        assert "site_info" in config

    @pytest.mark.unit
    def test_raises_on_missing_file(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.json"
        with pytest.raises(JsonLoadError) as exc_info:
            load_json(missing)
        assert exc_info.value.path == missing
        assert "nonexistent.json" in str(exc_info.value)

    @pytest.mark.unit
    def test_raises_on_invalid_json(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{bad", encoding="utf-8")
        with pytest.raises(JsonLoadError) as exc_info:
            load_json(bad)
        assert exc_info.value.path == bad
        assert "bad.json" in str(exc_info.value)
        assert isinstance(exc_info.value.cause, json.JSONDecodeError)


class TestLoadsJson:
    @pytest.mark.unit
    def test_parses_valid_string(self):
        assert loads_json('{"a": 1}') == {"a": 1}

    @pytest.mark.unit
    def test_invalid_string_without_context(self):
        with pytest.raises(JsonLoadError) as exc_info:
            loads_json("{bad")
        assert exc_info.value.path is None
        assert "Failed to parse JSON:" in str(exc_info.value)
        assert isinstance(exc_info.value.cause, json.JSONDecodeError)

    @pytest.mark.unit
    def test_invalid_string_with_path(self, tmp_path: Path):
        path = tmp_path / "links.json"
        with pytest.raises(JsonLoadError) as exc_info:
            loads_json("{bad", path=path)
        assert exc_info.value.path == path
        assert str(path) in str(exc_info.value)

    @pytest.mark.unit
    def test_invalid_string_with_source(self):
        with pytest.raises(JsonLoadError) as exc_info:
            loads_json("{bad", source="fonts.css")
        assert "fonts.css" in str(exc_info.value)
        assert exc_info.value.path is None
