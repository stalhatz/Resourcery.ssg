import json
import logging
import re
import pytest
from pathlib import Path
from resourcery_ssg.errors import ResourceryError
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
    def test_creates_vendor_file(self, monkeypatch, tmp_path: Path, caplog):
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

        caplog.set_level(logging.DEBUG)
        acquire_js(package_json_path=pkg_path, vendor_dir=vendor_dir)

        vendor_file = vendor_dir / "nanostores.js"
        assert vendor_file.exists()
        content = vendor_file.read_text(encoding="utf-8")
        assert "/* nanostores 0.11.4" in content
        assert "export const atom = () => {};" in content

        assert any(
            r.levelno == logging.INFO
            and re.search(r"^Downloaded nanostores@0\.11\.4$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.DEBUG
            and re.search(r"^Vendor: resolved nanostores@0\.11\.4 from .+$", r.message)
            for r in caplog.records
        )

    @pytest.mark.unit
    def test_second_call_is_noop(self, monkeypatch, tmp_path: Path, caplog):
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

        caplog.set_level(logging.DEBUG)
        acquire_js(package_json_path=pkg_path, vendor_dir=vendor_dir)

        # urlopen should NOT have been called
        assert call_count == 0

        assert any(
            r.levelno == logging.INFO
            and re.search(r"^Vendor file up to date: nanostores@0\.11\.4$", r.message)
            for r in caplog.records
        )

    @pytest.mark.unit
    def test_missing_package_json_raises(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.json"
        vendor_dir = tmp_path / "vendor"

        with pytest.raises(ResourceryError) as exc_info:
            acquire_js(package_json_path=missing, vendor_dir=vendor_dir)
        assert "Error: package.json not found" in str(exc_info.value)

    @pytest.mark.unit
    def test_missing_nanostores_key_raises(self, tmp_path: Path):
        pkg_path = tmp_path / "package.json"
        pkg_path.write_text(
            json.dumps({"name": "test", "dependencies": {}}),
            encoding="utf-8",
        )
        vendor_dir = tmp_path / "vendor"

        with pytest.raises(ResourceryError) as exc_info:
            acquire_js(package_json_path=pkg_path, vendor_dir=vendor_dir)
        assert "no dependencies.nanostores entry" in str(exc_info.value)

    @pytest.mark.unit
    def test_invalid_package_json_raises(self, tmp_path: Path, capsys, caplog):
        """Malformed package.json verifies the invalid-JSON branch (stderr, ERROR)."""
        pkg_path = tmp_path / "package.json"
        pkg_path.write_text("{not valid json", encoding="utf-8")
        vendor_dir = tmp_path / "vendor"

        with pytest.raises(ResourceryError) as exc_info:
            acquire_js(package_json_path=pkg_path, vendor_dir=vendor_dir)
        assert "package.json is not valid JSON" in str(exc_info.value)
        assert "package.json is not valid JSON" in capsys.readouterr().err
        assert any(
            r.levelno == logging.ERROR
            and "package.json is not valid JSON" in r.message
            for r in caplog.records
        )

    @pytest.mark.unit
    def test_uncreatable_vendor_dir_raises(self, tmp_path: Path, capsys, caplog):
        """vendor_dir pointing at an existing file verifies the mkdir branch."""
        pkg_path = tmp_path / "package.json"
        pkg_path.write_text(
            json.dumps({
                "name": "test",
                "private": True,
                "dependencies": {"nanostores": "0.11.4"},
            }),
            encoding="utf-8",
        )
        blocker = tmp_path / "vendor"
        blocker.write_text("i am a file, not a directory", encoding="utf-8")

        with pytest.raises(ResourceryError) as exc_info:
            acquire_js(package_json_path=pkg_path, vendor_dir=blocker)
        assert "cannot write to" in str(exc_info.value)
        assert "cannot write to" in capsys.readouterr().err
        assert any(
            r.levelno == logging.ERROR and "cannot write to" in r.message
            for r in caplog.records
        )

    @pytest.mark.unit
    def test_vendor_dir_not_writable_raises(self, monkeypatch, tmp_path: Path, capsys, caplog):
        """os.access patched to False verifies the permission-denied branch.

        chmod-based tests are unreliable when running as root, where
        os.access returns True — hence the monkeypatch.
        """
        monkeypatch.setattr(
            "resourcery_ssg.js_vendor.os.access", lambda path, mode: False
        )
        pkg_path = tmp_path / "package.json"
        pkg_path.write_text(
            json.dumps({
                "name": "test",
                "private": True,
                "dependencies": {"nanostores": "0.11.4"},
            }),
            encoding="utf-8",
        )
        vendor_dir = tmp_path / "vendor"

        with pytest.raises(ResourceryError) as exc_info:
            acquire_js(package_json_path=pkg_path, vendor_dir=vendor_dir)
        assert "permission denied" in str(exc_info.value)
        assert "permission denied" in capsys.readouterr().err
        assert any(
            r.levelno == logging.ERROR and "permission denied" in r.message
            for r in caplog.records
        )

    @pytest.mark.unit
    def test_download_failure_raises(self, monkeypatch, tmp_path: Path, capsys, caplog):
        """A failing download verifies the download-failure branch (stderr)."""
        def failing_download(*args, **kwargs):
            raise Exception("Network unreachable")

        monkeypatch.setattr(
            "resourcery_ssg.js_vendor.download_nanostores", failing_download
        )
        pkg_path = tmp_path / "package.json"
        pkg_path.write_text(
            json.dumps({
                "name": "test",
                "private": True,
                "dependencies": {"nanostores": "0.11.4"},
            }),
            encoding="utf-8",
        )
        vendor_dir = tmp_path / "vendor"

        with pytest.raises(ResourceryError) as exc_info:
            acquire_js(package_json_path=pkg_path, vendor_dir=vendor_dir)
        assert "failed to download" in str(exc_info.value)
        assert "failed to download" in capsys.readouterr().err
        assert any(
            r.levelno == logging.ERROR and "failed to download" in r.message
            for r in caplog.records
        )
