import json
import pytest
from pathlib import Path
from resourcery_ssg.js_vendor import (
    read_cached_nanostores,
    is_cache_valid,
    download_nanostores,
    acquire_js,
)


class TestReadCachedNanostores:
    @pytest.mark.unit
    def test_returns_tuple_from_valid_header(self, tmp_path: Path):
        vendor = tmp_path / "nanostores.js"
        vendor.write_text(
            '/* nanostores 0.11.4 source: https://esm.sh/nanostores@0.11.4/es2022/nanostores.mjs acquired: 2026-07-30 */\nexport {};',
            encoding="utf-8",
        )
        result = read_cached_nanostores(vendor)
        assert result == (
            "0.11.4",
            "https://esm.sh/nanostores@0.11.4/es2022/nanostores.mjs",
        )

    @pytest.mark.unit
    def test_returns_none_when_missing(self, tmp_path: Path):
        assert read_cached_nanostores(tmp_path / "nonexistent.js") is None

    @pytest.mark.unit
    def test_returns_none_when_malformed(self, tmp_path: Path):
        vendor = tmp_path / "nanostores.js"
        vendor.write_text("no header comment here", encoding="utf-8")
        assert read_cached_nanostores(vendor) is None


class TestIsCacheValid:
    @pytest.mark.unit
    def test_missing_file_returns_false(self, tmp_path: Path):
        assert is_cache_valid(tmp_path / "nanostores.js", "0.11.4") is False

    @pytest.mark.unit
    def test_version_mismatch_returns_false(self, tmp_path: Path):
        vendor = tmp_path / "nanostores.js"
        vendor.write_text(
            '/* nanostores 0.10.0 source: https://esm.sh/nanostores@0.10.0/es2022/nanostores.mjs acquired: 2026-07-30 */',
            encoding="utf-8",
        )
        assert is_cache_valid(vendor, "0.11.4") is False

    @pytest.mark.unit
    def test_match_returns_true(self, tmp_path: Path):
        vendor = tmp_path / "nanostores.js"
        vendor.write_text(
            '/* nanostores 0.11.4 source: https://esm.sh/nanostores@0.11.4/es2022/nanostores.mjs acquired: 2026-07-30 */',
            encoding="utf-8",
        )
        assert is_cache_valid(vendor, "0.11.4") is True


class TestDownloadNanostores:
    @pytest.mark.unit
    def test_writes_file_with_header_and_body(self, monkeypatch, tmp_path: Path):
        def mock_urlopen(req, **kw):
            class MockResp:
                def read(self):
                    return b"export const atom = () => {};"

                def decode(self, enc="utf-8"):
                    return "export const atom = () => {};"

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

            return MockResp()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        vendor_path = tmp_path / "nanostores.js"
        download_nanostores("0.11.4", vendor_path)

        content = vendor_path.read_text(encoding="utf-8")
        assert "/* nanostores 0.11.4" in content
        assert "source: https://esm.sh/nanostores@0.11.4/es2022/nanostores.mjs" in content
        assert "export const atom = () => {};" in content

    @pytest.mark.unit
    def test_failure_leaves_file_untouched(self, monkeypatch, tmp_path: Path):
        def mock_urlopen(req, **kw):
            raise Exception("Network error")

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        vendor_path = tmp_path / "nanostores.js"
        # Create an existing file
        vendor_path.write_text("existing content", encoding="utf-8")

        with pytest.raises(Exception, match="Network error"):
            download_nanostores("0.11.4", vendor_path)

        # Existing content should be preserved
        assert vendor_path.read_text(encoding="utf-8") == "existing content"


class TestAcquireJs:
    @pytest.mark.unit
    def test_creates_vendor_file(self, monkeypatch, tmp_path: Path):
        # Create package.json in tmp_path
        pkg_path = tmp_path / "package.json"
        pkg_path.write_text(
            json.dumps({
                "name": "test",
                "private": True,
                "dependencies": {"nanostores": "0.11.4"},
            }),
            encoding="utf-8",
        )

        vendor_dir = tmp_path / "js" / "vendor"

        def mock_urlopen(req, **kw):
            class MockResp:
                def read(self):
                    return b"export const atom = () => {};"

                def decode(self, enc="utf-8"):
                    return "export const atom = () => {};"

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

            return MockResp()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        acquire_js(package_json_path=pkg_path, vendor_dir=vendor_dir)

        vendor_file = vendor_dir / "nanostores.js"
        assert vendor_file.exists()
        content = vendor_file.read_text(encoding="utf-8")
        assert "/* nanostores 0.11.4" in content
        assert "export const atom = () => {};" in content

    @pytest.mark.unit
    def test_second_call_is_noop(self, monkeypatch, tmp_path: Path):
        pkg_path = tmp_path / "package.json"
        pkg_path.write_text(
            json.dumps({
                "name": "test",
                "private": True,
                "dependencies": {"nanostores": "0.11.4"},
            }),
            encoding="utf-8",
        )

        vendor_dir = tmp_path / "js" / "vendor"
        vendor_dir.mkdir(parents=True, exist_ok=True)
        vendor_file = vendor_dir / "nanostores.js"
        # Create a valid cached file
        vendor_file.write_text(
            '/* nanostores 0.11.4 source: https://esm.sh/nanostores@0.11.4/es2022/nanostores.mjs acquired: 2026-07-30 */\nexport {};',
            encoding="utf-8",
        )

        call_count = 0

        def mock_urlopen(req, **kw):
            nonlocal call_count
            call_count += 1
            class MockResp:
                def read(self):
                    return b"should not be called"

                def decode(self, enc="utf-8"):
                    return "should not be called"

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

            return MockResp()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        acquire_js(package_json_path=pkg_path, vendor_dir=vendor_dir)

        # urlopen should NOT have been called
        assert call_count == 0

    @pytest.mark.unit
    def test_missing_package_json_raises(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.json"
        vendor_dir = tmp_path / "vendor"

        with pytest.raises(SystemExit):
            acquire_js(package_json_path=missing, vendor_dir=vendor_dir)

    @pytest.mark.unit
    def test_missing_nanostores_key_raises(self, tmp_path: Path):
        pkg_path = tmp_path / "package.json"
        pkg_path.write_text(
            json.dumps({"name": "test", "dependencies": {}}),
            encoding="utf-8",
        )
        vendor_dir = tmp_path / "vendor"

        with pytest.raises(SystemExit):
            acquire_js(package_json_path=pkg_path, vendor_dir=vendor_dir)
