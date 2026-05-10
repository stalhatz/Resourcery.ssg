import json
import pytest
from pathlib import Path
from font_acquirer import (
    read_cached_fonts,
    is_cache_valid,
    load_config,
    is_system_font,
    extract_google_font_candidates,
    fetch_google_fonts_css,
    find_first_downloadable,
    download_file,
    process_font,
    acquire_fonts,
)


class TestReadCachedFonts:
    @pytest.mark.unit
    def test_returns_list_from_comment(self, tmp_path: Path):
        css_file = tmp_path / "fonts.css"
        css_file.write_text(
            '/* ["Roboto","Open Sans"] */\n@font-face{}', encoding="utf-8"
        )
        assert read_cached_fonts(css_file) == ["Roboto", "Open Sans"]

    @pytest.mark.unit
    def test_empty_when_no_file(self, tmp_path: Path):
        assert read_cached_fonts(tmp_path / "nonexistent.css") == []

    @pytest.mark.unit
    def test_empty_when_malformed(self, tmp_path: Path):
        css_file = tmp_path / "fonts.css"
        css_file.write_text("no comment here", encoding="utf-8")
        assert read_cached_fonts(css_file) == []


class TestIsCacheValid:
    @pytest.mark.unit
    def test_missing_cache_returns_false(self, tmp_path: Path):
        assert is_cache_valid(tmp_path / "fonts.css", ["Roboto"]) is False


class TestLoadConfig:
    @pytest.mark.unit
    def test_loads_from_testdata(self, testdata_dir: Path, monkeypatch):
        monkeypatch.setattr("font_acquirer.DATA_DIR", testdata_dir)
        config = load_config()
        assert "site_info" in config


class TestIsSystemFont:
    @pytest.mark.unit
    def test_known_system_fonts(self):
        assert is_system_font("Arial") is True
        assert is_system_font("system-ui") is True
        assert is_system_font("sans-serif") is True

    @pytest.mark.unit
    def test_google_font_is_not_system(self):
        assert is_system_font("Roboto") is False
        assert is_system_font("Open Sans") is False

    @pytest.mark.unit
    def test_handles_quotes(self):
        assert is_system_font('"Arial"') is True
        assert is_system_font("'Helvetica Neue'") is True


class TestExtractGoogleFontCandidates:
    @pytest.mark.unit
    def test_returns_non_system_fonts(self):
        result = extract_google_font_candidates("Roboto, system-ui, sans-serif")
        assert result == ["Roboto"]

    @pytest.mark.unit
    def test_system_only_stack(self):
        assert extract_google_font_candidates("system-ui, sans-serif") == []

    @pytest.mark.unit
    def test_multiple_candidates(self):
        result = extract_google_font_candidates(
            "Open Sans, Roboto, system-ui, sans-serif"
        )
        assert result == ["Open Sans", "Roboto"]


class TestFetchGoogleFontsCss:
    @pytest.mark.unit
    def test_returns_css_on_success(self, monkeypatch):
        def mock_urlopen(req, **kw):
            class MockResp:
                def read(self):
                    return b"@font-face { font-family: 'Test'; }"

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

            return MockResp()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        css = fetch_google_fonts_css("TestFont", "0,400")
        assert css is not None
        assert "@font-face" in css

    @pytest.mark.unit
    def test_returns_none_on_no_font_face(self, monkeypatch):
        def mock_urlopen(req, **kw):
            class MockResp:
                def read(self):
                    return b"/* no font-face here */"

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

            return MockResp()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        assert fetch_google_fonts_css("BadFont", "0,400") is None

    @pytest.mark.unit
    def test_returns_none_on_error(self, monkeypatch):
        def mock_urlopen(req, **kw):
            raise Exception("Network error")

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        assert fetch_google_fonts_css("BadFont", "0,400") is None


class TestFindFirstDownloadable:
    @pytest.mark.unit
    def test_returns_first_candidate(self, monkeypatch):
        def mock_fetch(name, weights):
            return (
                f"@font-face {{ font-family: '{name}'; }}" if name == "Roboto" else None
            )

        monkeypatch.setattr("font_acquirer.fetch_google_fonts_css", mock_fetch)
        name, css = find_first_downloadable("Roboto, system-ui", "0,400")
        assert name == "Roboto"
        assert css is not None

    @pytest.mark.unit
    def test_returns_none_when_no_candidate(self, monkeypatch):
        def mock_fetch(name, weights):
            return None

        monkeypatch.setattr("font_acquirer.fetch_google_fonts_css", mock_fetch)
        name, css = find_first_downloadable("UnknownFont, system-ui", "0,400")
        assert name is None
        assert css is None


class TestDownloadFile:
    @pytest.mark.unit
    def test_successful_download(self, monkeypatch, tmp_path: Path):
        def mock_urlopen(req, **kw):
            class MockResp:
                def read(self):
                    return b"font binary data"

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

            return MockResp()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        dest = tmp_path / "test.woff2"
        assert download_file("https://example.com/font.woff2", dest) is True
        assert dest.read_bytes() == b"font binary data"

    @pytest.mark.unit
    def test_failed_download_returns_false(self, monkeypatch, tmp_path: Path):
        def mock_urlopen(req, **kw):
            raise Exception("Timeout")

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        assert download_file("https://example.com/font.woff2", tmp_path / "x") is False


class TestIntegrationAcquireFonts:
    @pytest.mark.integration
    def test_acquire_fonts_creates_fonts_css(
        self, testdata_dir: Path, monkeypatch, tmp_path: Path
    ):
        font_dir = tmp_path / "fonts"
        font_dir.mkdir(parents=True)
        css_dir = tmp_path / "css"
        css_dir.mkdir(parents=True)

        monkeypatch.setattr("font_acquirer.DATA_DIR", testdata_dir)
        monkeypatch.setattr("font_acquirer.FONTS_DIR", font_dir)
        monkeypatch.setattr("font_acquirer.CSS_DIR", css_dir)

        def mock_urlopen(req, **kw):
            class MockResp:
                def read(self):
                    return b"/* latin */ @font-face { font-family: 'Inter'; font-style: normal; font-weight: 400; src: url(https://example.com/inter.woff2); }"

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

            return MockResp()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        acquire_fonts()
        assert (css_dir / "fonts.css").exists()
        content = (css_dir / "fonts.css").read_text(encoding="utf-8")
        assert "@font-face" in content
