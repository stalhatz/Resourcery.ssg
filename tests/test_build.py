import json
import pytest
from pathlib import Path
from resourcery_ssg.build import (
    load_json,
    validate_data,
    shuffle_filter,
    build_category_map,
    build_all_tags,
    build_site,
)


class TestLoadJson:
    @pytest.mark.unit
    def test_loads_valid_json(self, testdata_dir: Path):
        config = load_json(testdata_dir / "site.config.json")
        assert "site_info" in config

    @pytest.mark.unit
    def test_raises_on_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_json(tmp_path / "nonexistent.json")

    @pytest.mark.unit
    def test_raises_on_invalid_json(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{bad", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_json(bad)


class TestValidateData:
    @pytest.mark.unit
    def test_valid_data_passes(self, sample_config: dict, sample_links: dict):
        validate_data(sample_config, sample_links)

    @pytest.mark.unit
    def test_missing_config_key_raises(self, sample_links: dict):
        with pytest.raises(ValueError, match="Missing required config key"):
            validate_data({}, sample_links)

    @pytest.mark.unit
    def test_missing_links_key_raises(self, sample_config: dict):
        with pytest.raises(ValueError, match="Missing required links key"):
            validate_data(sample_config, {})


class TestShuffleFilter:
    @pytest.mark.unit
    def test_returns_list_with_same_elements(self):
        original = [1, 2, 3, 4, 5]
        result = shuffle_filter(original)
        assert sorted(result) == sorted(original)

    @pytest.mark.unit
    def test_returns_new_list(self):
        original = [1, 2, 3]
        result = shuffle_filter(original)
        assert result is not original


class TestBuildCategoryMap:
    @pytest.mark.unit
    def test_maps_parents_and_children(self, sample_config: dict):
        result = build_category_map(sample_config)
        assert "tech" in result
        assert "programming" in result
        assert "programming" in result["tech"]

    @pytest.mark.unit
    def test_leaf_category_maps_to_self(self, sample_config: dict):
        result = build_category_map(sample_config)
        assert result["programming"] == ["programming"]


class TestBuildAllTags:
    @pytest.mark.unit
    def test_deduplicates_tags(self, sample_links: dict):
        result = build_all_tags(sample_links)
        assert "test" in result
        assert "example" in result
        assert "demo" in result

    @pytest.mark.unit
    def test_returns_sorted_list(self, sample_links: dict):
        result = build_all_tags(sample_links)
        assert result == sorted(result, key=str.lower)

    @pytest.mark.unit
    def test_empty_when_no_links(self):
        assert build_all_tags({"links": []}) == []


class TestIntegrationBuild:
    @pytest.mark.integration
    def test_build_creates_output(
        self, testdata_dir: Path, tmp_output_dir: Path, monkeypatch
    ):
        static_dir = testdata_dir / "static"
        monkeypatch.setattr("resourcery_ssg.build.DATA_DIR", testdata_dir)
        monkeypatch.setattr("resourcery_ssg.build.TEMPLATES_DIR", testdata_dir / "templates")
        monkeypatch.setattr("resourcery_ssg.build.STATIC_DIR", static_dir)
        monkeypatch.setattr("resourcery_ssg.build.OUTPUT_DIR", tmp_output_dir)

        build_site()
        assert (tmp_output_dir / "index.html").exists()
        assert (tmp_output_dir / "browse.html").exists()
        assert (tmp_output_dir / "static" / "css" / "style.css").exists()
