import json
import logging
import re
import sys
import pytest
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from resourcery_ssg.build import (
    validate_data,
    shuffle_filter,
    build_category_map,
    build_all_tags,
    build_site,
)
from resourcery_ssg.errors import ResourceryError
from resourcery_ssg.io_utils import load_json, JsonLoadError


class TestLoadJson:
    @pytest.mark.unit
    def test_loads_valid_json(self, testdata_dir: Path):
        config = load_json(testdata_dir / "site.config.json")
        assert "site_info" in config

    @pytest.mark.unit
    def test_raises_on_missing_file(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.json"
        with pytest.raises(JsonLoadError) as exc_info:
            load_json(missing)
        assert exc_info.value.path == missing

    @pytest.mark.unit
    def test_raises_on_invalid_json(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{bad", encoding="utf-8")
        with pytest.raises(JsonLoadError) as exc_info:
            load_json(bad)
        assert exc_info.value.path == bad


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
    def test_build_creates_output(self, build_paths: dict):
        build_site(**build_paths)
        assert (build_paths["output_dir"] / "index.html").exists()
        assert (build_paths["output_dir"] / "browse.html").exists()
        assert (build_paths["output_dir"] / "static" / "css" / "style.css").exists()
        # Verify no attribution when not configured
        assert not (build_paths["output_dir"] / "note.html").exists()
        assert not (build_paths["output_dir"] / "prompt.html").exists()
        index_html = (build_paths["output_dir"] / "index.html").read_text("utf-8")
        assert "attribution-note" not in index_html

    @pytest.mark.integration
    def test_build_emits_operational_records(self, build_paths: dict, caplog):
        """INFO/DEBUG records document what a build actually did."""
        caplog.set_level(logging.DEBUG)
        build_site(**build_paths)

        assert any(
            r.levelno == logging.INFO
            and re.search(r"^Rendered \d+ templates$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.INFO
            and re.search(r"^Generated \d+ CSS custom properties$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.INFO
            and re.search(
                r"^Copied \d+ files: images \d+, js \d+, fonts \d+$", r.message
            )
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.DEBUG
            and re.search(r"^Rendering \w+\.\w+ from .+$", r.message)
            for r in caplog.records
        )


class TestSearchBarFeatureFlag:
    """Regression: search bar disappeared despite features.search.enabled=true.

    The template reads config.features.search.enabled (single nesting, per
    specs/refactors/data_design_split.md). The schema accidentally gained an
    extra nesting level (features.search.search.enabled) which made the flag
    resolve to falsy and hid the search bar.
    """

    @staticmethod
    def _render_base(config: dict, links: dict) -> str:
        env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
        return env.get_template("base.html").render(
            config=config,
            links=links,
            category_map=build_category_map(config),
            all_tags=build_all_tags(links),
            theme_tokens={},
            heading_weight="normal",
            heading_letter_spacing="normal",
            attribution_enabled=False,
        )

    @pytest.mark.unit
    def test_schema_pins_single_nesting_for_search_flag(self, testdata_dir: Path):
        """The schema must declare features.search.enabled (not .search.search.enabled)."""
        schema = json.loads(
            (testdata_dir.parent.parent / "schemas" / "site.config.schema.json")
            .read_text(encoding="utf-8")
        )
        search_schema = schema["properties"]["features"]["properties"]["search"]["properties"]
        assert "enabled" in search_schema
        assert "search" not in search_schema

    @pytest.mark.unit
    def test_committed_configs_resolve_search_enabled(self):
        """Every committed site.config.json must expose features.search.enabled as a bool."""
        root = Path(__file__).parent.parent
        config_files = [root / "data" / "site.config.json"]
        config_files += sorted((root / "userdata").glob("*/data/site.config.json"))
        assert config_files, "no site.config.json files found"
        for path in config_files:
            config = json.loads(path.read_text(encoding="utf-8"))
            enabled = config.get("features", {}).get("search", {}).get("enabled")
            assert isinstance(enabled, bool), f"{path}: features.search.enabled is {enabled!r}"

    @pytest.mark.unit
    def test_search_bar_rendered_with_committed_config(self):
        """Rendering base.html with the real data/site.config.json must emit the search input."""
        root = Path(__file__).parent.parent
        config = json.loads((root / "data" / "site.config.json").read_text(encoding="utf-8"))
        design = json.loads((root / "data" / "design.json").read_text(encoding="utf-8"))
        links = json.loads((root / "data" / "links.json").read_text(encoding="utf-8"))
        config["theme"] = design["theme"]  # build.py merges design.json into config

        html = self._render_base(config, links)
        assert 'id="searchInput"' in html


class TestMarkdownConversion:
    """Unit tests for mistune markdown conversion."""

    @pytest.fixture(autouse=True)
    def setup_markdown(self):
        import mistune
        self.md = mistune.create_markdown(
            escape=False,
            plugins=["strikethrough", "footnotes", "table", "speedup"]
        )

    @pytest.mark.unit
    def test_renders_headings(self):
        result = self.md("# H1\n\n## H2\n\n### H3")
        assert "<h1>H1</h1>" in result
        assert "<h2>H2</h2>" in result
        assert "<h3>H3</h3>" in result

    @pytest.mark.unit
    def test_renders_lists(self):
        result = self.md("- item1\n- item2\n- item3")
        assert "<ul>" in result
        assert "<li>item1</li>" in result
        assert "<li>item2</li>" in result

    @pytest.mark.unit
    def test_renders_code_blocks(self):
        result = self.md("```python\nprint('hello')\n```")
        assert "<pre>" in result
        assert "<code" in result
        assert "print" in result

    @pytest.mark.unit
    def test_renders_links(self):
        result = self.md("[text](https://example.com)")
        assert '<a href="https://example.com">text</a>' in result

    @pytest.mark.unit
    def test_renders_tables(self):
        result = self.md("| a | b |\n|---|---|\n| 1 | 2 |")
        assert "<table>" in result
        assert "<th>a</th>" in result
        assert "<td>1</td>" in result

    @pytest.mark.unit
    def test_renders_inline_html(self):
        result = self.md("text with <strong>bold</strong> html")
        assert "<strong>bold</strong>" in result

    @pytest.mark.unit
    def test_renders_emphasis(self):
        result = self.md("**bold** and *italic* and ~~strike~~")
        assert "<strong>bold</strong>" in result
        assert "<em>italic</em>" in result
        assert "<del>strike</del>" in result


class TestBuildAttribution:
    """Unit tests for attribution logic (error paths, conditional rendering)."""

    @pytest.mark.unit
    def test_attribution_none_skips_source_pages(self, build_paths: dict):
        """With attribution=None, verify note.html and prompt.html are NOT generated."""
        paths = dict(build_paths)
        paths["attribution"] = None
        build_site(**paths)
        assert not (paths["output_dir"] / "note.html").exists()
        assert not (paths["output_dir"] / "prompt.html").exists()

    @pytest.mark.unit
    def test_attribution_false_skips_source_pages(self, build_paths: dict):
        """With attribution=False, verify note.html and prompt.html are NOT generated."""
        paths = dict(build_paths)
        paths["attribution"] = False
        build_site(**paths)
        assert not (paths["output_dir"] / "note.html").exists()
        assert not (paths["output_dir"] / "prompt.html").exists()

    @pytest.mark.unit
    def test_missing_ingest_note_raises(self, build_paths: dict):
        """With attribution=True but ingest_note=None, verify ResourceryError."""
        paths = dict(build_paths)
        paths["attribution"] = True
        paths["ingest_note"] = None
        paths["ingest_site_prompt"] = None
        with pytest.raises(ResourceryError) as exc_info:
            build_site(**paths)
        assert "build.attribution is enabled but ingest.note is not set" in str(
            exc_info.value
        )

    @pytest.mark.unit
    def test_missing_ingest_site_prompt_raises(self, build_paths: dict, tmp_path: Path):
        """With attribution=True but ingest_site_prompt=None, verify ResourceryError."""
        note_file = tmp_path / "test-note.md"
        note_file.write_text("# Test Note")
        paths = dict(build_paths)
        paths["attribution"] = True
        paths["ingest_note"] = str(note_file)
        paths["ingest_site_prompt"] = None
        with pytest.raises(ResourceryError) as exc_info:
            build_site(**paths)
        assert (
            "build.attribution is enabled but ingest.site_prompt is not set"
            in str(exc_info.value)
        )

    @pytest.mark.unit
    def test_missing_note_file_raises(self, build_paths: dict, tmp_path: Path):
        """With attribution=True but ingest_note pointing to non-existent file."""
        prompt_file = tmp_path / "test-prompt.md"
        prompt_file.write_text("# Test Prompt")
        paths = dict(build_paths)
        paths["attribution"] = True
        paths["ingest_note"] = str(tmp_path / "nonexistent.md")
        paths["ingest_site_prompt"] = str(prompt_file)
        with pytest.raises(ResourceryError) as exc_info:
            build_site(**paths)
        assert "Cannot read note file" in str(exc_info.value)

    @pytest.mark.unit
    def test_missing_prompt_file_raises(self, build_paths: dict, tmp_path: Path):
        """With attribution=True but ingest_site_prompt pointing to non-existent file."""
        note_file = tmp_path / "test-note.md"
        note_file.write_text("# Test Note")
        paths = dict(build_paths)
        paths["attribution"] = True
        paths["ingest_note"] = str(note_file)
        paths["ingest_site_prompt"] = str(tmp_path / "nonexistent.md")
        with pytest.raises(ResourceryError) as exc_info:
            build_site(**paths)
        assert "Cannot read site prompt file" in str(exc_info.value)

    @pytest.mark.unit
    def test_utf8_decode_error(self, build_paths: dict, tmp_path: Path):
        """Create a non-UTF-8 file and verify ResourceryError with decode error."""
        note_file = tmp_path / "test-note.md"
        note_file.write_text("# Test Note")
        prompt_file = tmp_path / "test-prompt.md"
        # Write non-UTF-8 bytes
        prompt_file.write_bytes(b"\x80\x81\x82")
        paths = dict(build_paths)
        paths["attribution"] = True
        paths["ingest_note"] = str(note_file)
        paths["ingest_site_prompt"] = str(prompt_file)
        with pytest.raises(ResourceryError) as exc_info:
            build_site(**paths)
        assert "Cannot decode test-prompt.md as UTF-8" in str(exc_info.value)

    @pytest.mark.unit
    def test_missing_fonts_css_raises(
        self, build_paths: dict, tmp_path: Path, capsys, caplog
    ):
        """Without static/css/fonts.css, verify ResourceryError on stderr."""
        paths = dict(build_paths)
        paths["static_dir"] = tmp_path / "static-empty"
        with pytest.raises(ResourceryError) as exc_info:
            build_site(**paths)
        assert "static/css/fonts.css not found" in str(exc_info.value)
        captured = capsys.readouterr()
        assert "static/css/fonts.css not found" in captured.err
        assert "static/css/fonts.css not found" not in captured.out
        error_records = [
            r for r in caplog.records if r.levelno >= logging.ERROR
        ]
        assert any(
            "static/css/fonts.css not found" in r.message for r in error_records
        )

    @pytest.mark.unit
    def test_utf8_decode_error_note_file(self, build_paths: dict, tmp_path: Path):
        """A non-UTF-8 note file verifies the note-twin of the decode error."""
        note_file = tmp_path / "test-note.md"
        # Write non-UTF-8 bytes
        note_file.write_bytes(b"\xff\xfe\x00invalid")
        prompt_file = tmp_path / "test-prompt.md"
        prompt_file.write_text("# Test Prompt")
        paths = dict(build_paths)
        paths["attribution"] = True
        paths["ingest_note"] = str(note_file)
        paths["ingest_site_prompt"] = str(prompt_file)
        with pytest.raises(ResourceryError) as exc_info:
            build_site(**paths)
        assert "Cannot decode test-note.md as UTF-8" in str(exc_info.value)

    def test_footer_contains_attribution(self, attribution_paths: dict):
        """Verify index.html contains the .attribution-note element with correct links."""
        build_site(**attribution_paths)
        index_html = (attribution_paths["output_dir"] / "index.html").read_text("utf-8")
        assert "attribution-note" in index_html
        assert "https://github.com/stalhatz/Resourcery.ssg" in index_html
        assert "note.html" in index_html
        assert "prompt.html" in index_html


class TestIntegrationAttribution:
    """Integration tests for the full build with attribution."""

    @pytest.mark.integration
    def test_build_with_attribution(self, attribution_paths: dict):
        build_site(**attribution_paths)
        out = attribution_paths["output_dir"]
        # Verify all 4 pages exist
        assert (out / "index.html").exists()
        assert (out / "browse.html").exists()
        assert (out / "note.html").exists()
        assert (out / "prompt.html").exists()
        # Verify index.html contains attribution footer
        index_html = (out / "index.html").read_text("utf-8")
        assert "attribution-note" in index_html
        # Verify note.html contains rendered markdown content
        note_html = (out / "note.html").read_text("utf-8")
        assert "Test Note" in note_html
        assert "<strong>test</strong>" in note_html
        # Verify prompt.html contains rendered markdown content
        prompt_html = (out / "prompt.html").read_text("utf-8")
        assert "Test Prompt" in prompt_html
        assert "<li>Item 1</li>" in prompt_html
        # Verify source pages extend base (contain footer)
        assert "main-footer" in note_html
        assert "main-footer" in prompt_html
