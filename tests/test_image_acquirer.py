import json
import logging
import re
import sys
import pytest
from pathlib import Path
from resourcery_ssg.image_acquirer import ImageAcquirer, acquire_images_from_config
from resourcery_ssg.image_acquirer import main as image_acquirer_main


@pytest.fixture
def acquirer(tmp_path: Path) -> ImageAcquirer:
    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True)
    static_dir = tmp_path
    return ImageAcquirer(images_dir=images_dir, static_dir=static_dir)


class TestGenerateFilename:
    @pytest.mark.unit
    def test_returns_jpg_with_id_and_hash(self, acquirer):
        filename = acquirer._generate_filename(
            "https://example.com/test.jpg", "test-link"
        )
        assert filename.endswith(".jpg")
        assert "test-link" in filename

    @pytest.mark.unit
    def test_deterministic(self, acquirer):
        a = acquirer._generate_filename("https://example.com/img.jpg", "l1")
        b = acquirer._generate_filename("https://example.com/img.jpg", "l1")
        assert a == b


class TestIsValidImageUrl:
    @pytest.mark.unit
    def test_valid_urls(self, acquirer):
        assert acquirer._is_valid_image_url("https://example.com/image.jpg") is True
        assert acquirer._is_valid_image_url("http://example.com/photo.png") is True

    @pytest.mark.unit
    def test_invalid_urls(self, acquirer):
        assert acquirer._is_valid_image_url("") is False
        assert acquirer._is_valid_image_url("data:image/png;base64,abc") is False
        assert acquirer._is_valid_image_url("ftp://example.com/img.jpg") is True


class TestDownloadImage:
    @pytest.mark.unit
    def test_successful_download(self, acquirer, tmp_path: Path, monkeypatch):
        from resourcery_ssg.image_acquirer import requests

        class MockResp:
            status_code = 200

            def raise_for_status(self):
                pass

            @property
            def headers(self):
                return {"content-type": "image/jpeg"}

            def iter_content(self, chunk_size=8192):
                return [b"fake image bytes"]

        monkeypatch.setattr(requests.Session, "get", lambda *a, **kw: MockResp())

        save_path = tmp_path / "test.jpg"
        save_path.write_bytes(b"fake jpeg data")
        result = acquirer._download_image("https://example.com/fake.jpg", save_path)
        assert result is False

    @pytest.mark.unit
    def test_failed_download_returns_false(self, acquirer, tmp_path: Path, monkeypatch):
        from resourcery_ssg.image_acquirer import requests

        class MockResp:
            def raise_for_status(self):
                raise Exception("HTTP error")

            @property
            def headers(self):
                return {}

        monkeypatch.setattr(requests.Session, "get", lambda *a, **kw: MockResp())
        result = acquirer._download_image(
            "https://example.com/fail.jpg", tmp_path / "fail.jpg"
        )
        assert result is False


class TestExtractMetaImage:
    @pytest.mark.unit
    def test_finds_og_image(self, acquirer, monkeypatch):
        from resourcery_ssg.image_acquirer import requests

        class MockResp:
            text = '<html><head><meta property="og:image" content="https://example.com/og.jpg"></head></html>'

            def raise_for_status(self):
                pass

        monkeypatch.setattr(requests.Session, "get", lambda *a, **kw: MockResp())
        result = acquirer.extract_meta_image("https://example.com/page")
        assert result == "https://example.com/og.jpg"

    @pytest.mark.unit
    def test_returns_none_when_no_meta(self, acquirer, monkeypatch):
        from resourcery_ssg.image_acquirer import requests

        class MockResp:
            text = "<html><head></head></html>"

            def raise_for_status(self):
                pass

        monkeypatch.setattr(requests.Session, "get", lambda *a, **kw: MockResp())
        assert acquirer.extract_meta_image("https://example.com/no-image") is None

    @pytest.mark.unit
    def test_returns_none_on_error(self, acquirer, monkeypatch):
        from resourcery_ssg.image_acquirer import requests

        def mock_get(*a, **kw):
            raise Exception("Network error")

        monkeypatch.setattr(requests.Session, "get", mock_get)
        assert acquirer.extract_meta_image("https://example.com/error") is None


class TestAcquireForLink:
    @pytest.mark.unit
    def test_skips_existing_image(self, acquirer, monkeypatch):
        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.ImageAcquirer.extract_meta_image", lambda *a: None
        )
        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.ImageAcquirer._download_image", lambda *a: False
        )
        monkeypatch.setattr("resourcery_ssg.image_acquirer.PUPPETEER_AVAILABLE", False)

        # Create an existing image in the acquirer's output_dir
        existing_file = acquirer.output_dir / "existing.jpg"
        existing_file.touch()

        link = {
            "id": "existing",
            "url": "https://example.com/page",
            "image": f"{acquirer.image_url_prefix}existing.jpg",
        }
        result = acquirer.acquire_for_link(link)
        assert result == f"{acquirer.image_url_prefix}existing.jpg"

    @pytest.mark.unit
    def test_returns_none_when_all_fail(self, acquirer, monkeypatch):
        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.ImageAcquirer.extract_meta_image", lambda *a: None
        )
        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.ImageAcquirer._download_image", lambda *a: False
        )
        monkeypatch.setattr("resourcery_ssg.image_acquirer.PUPPETEER_AVAILABLE", False)

        link = {"id": "fail", "url": "https://example.com/fail", "image": ""}
        result = acquirer.acquire_for_link(link)
        assert result is None


class TestAcquireAll:
    @pytest.mark.unit
    def test_skips_inactive_links(self, acquirer, monkeypatch):
        call_count = 0

        def mock_acquire(link, force=False):
            nonlocal call_count
            call_count += 1
            return None

        monkeypatch.setattr(acquirer, "acquire_for_link", mock_acquire)
        links_data = {
            "links": [
                {"id": "a", "status": "active", "url": "https://a.com"},
                {"id": "b", "status": "archived", "url": "https://b.com"},
                {"id": "c", "status": "active", "url": "https://c.com"},
            ]
        }
        acquirer.acquire_all(links_data)
        assert call_count == 2

    @pytest.mark.unit
    def test_emits_operational_records(self, acquirer, monkeypatch, caplog):
        """INFO summary + per-image DEBUG source records."""
        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.ImageAcquirer.extract_meta_image",
            lambda *a: "https://example.com/og.png",
        )
        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.ImageAcquirer._download_image",
            lambda *a: True,
        )
        monkeypatch.setattr("resourcery_ssg.image_acquirer.PUPPETEER_AVAILABLE", False)

        links_data = {
            "links": [
                {"id": "acme", "url": "https://example.com/acme", "status": "active"},
                {"id": "skip", "url": "https://example.com/skip", "status": "archived"},
            ]
        }
        caplog.set_level(logging.DEBUG)
        acquirer.acquire_all(links_data)

        assert any(
            r.levelno == logging.INFO
            and re.search(r"^Acquired \d+, skipped \d+, failed \d+, total \d+$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.DEBUG
            and re.search(
                r"^Image 'acme': using meta source \(https://example\.com/og\.png\)$",
                r.message,
            )
            for r in caplog.records
        )


@pytest.mark.skip(reason="Needs PIL image fixture; covered by unit tests")
class TestIntegrationAcquireImages:
    @pytest.mark.integration
    def test_acquire_images_runs(self, acquirer, monkeypatch):
        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.ImageAcquirer.extract_meta_image", lambda *a: None
        )
        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.ImageAcquirer._download_image", lambda *a: False
        )
        monkeypatch.setattr("resourcery_ssg.image_acquirer.PUPPETEER_AVAILABLE", False)

        links_data = {
            "links": [{"id": "t1", "url": "https://example.com/t1", "status": "active"}]
        }
        result = acquirer.acquire_all(links_data)
        assert "links" in result


class TestAcquireImagesFromConfig:
    """acquire_images_from_config: failure without side effects, success with backup."""

    def _make_config(self, tmp_path: Path, links_name: str = "links.json") -> tuple:
        """Build a config dict plus paths; images_dir sits inside static_dir."""
        static_dir = tmp_path / "static"
        images_dir = static_dir / "images" / "acquired"
        links_path = tmp_path / links_name
        config = {
            "acquire-images": {
                "links": str(links_path),
                "images_dir": str(images_dir),
            },
            "build": {"static_dir": str(static_dir)},
        }
        return config, links_path

    @pytest.mark.unit
    def test_missing_links_file_returns_false(self, tmp_path: Path, capsys):
        config, links_path = self._make_config(tmp_path)

        assert acquire_images_from_config(config) is False
        err = capsys.readouterr().err
        assert "Links file not found" in err
        assert str(links_path) in err
        assert not links_path.with_suffix(".json.bak").exists()

    @pytest.mark.unit
    def test_invalid_json_returns_false_untouched(self, tmp_path: Path, capsys):
        config, links_path = self._make_config(tmp_path)
        links_path.write_text("{bad json", encoding="utf-8")

        assert acquire_images_from_config(config) is False
        err = capsys.readouterr().err
        assert str(links_path) in err
        # Data on disk untouched, no backup created
        assert links_path.read_text(encoding="utf-8") == "{bad json"
        assert not links_path.with_suffix(".json.bak").exists()

    @pytest.mark.unit
    def test_success_writes_backup_and_updated_data(
        self, tmp_path: Path, monkeypatch, capsys
    ):
        config, links_path = self._make_config(tmp_path)
        original = {"links": [{"id": "a", "status": "active", "url": "https://a.com"}]}
        links_path.write_text(json.dumps(original), encoding="utf-8")
        updated = {"links": [{"id": "a", "image": "/static/images/acquired/a.jpg"}]}

        def mock_acquire_all(self, links_data, force=False):
            return updated

        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.ImageAcquirer.acquire_all",
            mock_acquire_all,
        )

        assert acquire_images_from_config(config) is True

        # Backup holds the original content
        backup_path = links_path.with_suffix(".json.bak")
        assert backup_path.exists()
        assert json.loads(backup_path.read_text(encoding="utf-8")) == original
        # links.json holds the updated data
        assert json.loads(links_path.read_text(encoding="utf-8")) == updated

        out = capsys.readouterr().out
        assert "✅ Updated" in out
        assert "Backup saved to" in out

    @pytest.mark.unit
    def test_force_forwarded_to_acquire_all(self, tmp_path: Path, monkeypatch):
        config, links_path = self._make_config(tmp_path)
        links_path.write_text('{"links": []}', encoding="utf-8")
        captured = {}

        def mock_acquire_all(self, links_data, force=False):
            captured["force"] = force
            return links_data

        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.ImageAcquirer.acquire_all",
            mock_acquire_all,
        )

        assert acquire_images_from_config(config, force=True) is True
        assert captured["force"] is True


class TestImageAcquirerMain:
    """Entry-point return codes of ``image_acquirer.main()`` (0/1, no exit)."""

    @pytest.mark.unit
    def test_main_returns_1_on_failure(self, monkeypatch):
        """A False acquisition result propagates as return code 1."""
        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.acquire_images_from_config",
            lambda config, force=False: False,
        )
        monkeypatch.setattr(sys, "argv", ["acquire-images"])

        assert image_acquirer_main() == 1

    @pytest.mark.unit
    def test_main_returns_0_on_success(self, monkeypatch):
        """A True acquisition result propagates as return code 0."""
        monkeypatch.setattr(
            "resourcery_ssg.image_acquirer.acquire_images_from_config",
            lambda config, force=False: True,
        )
        monkeypatch.setattr(sys, "argv", ["acquire-images"])

        assert image_acquirer_main() == 0
