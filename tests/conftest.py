from pathlib import Path
import json
import io
import pytest


@pytest.fixture(scope="session")
def testdata_dir() -> Path:
    return Path(__file__).parent.parent / "data" / "testdata"


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "output"
    out.mkdir(parents=True)
    return out


@pytest.fixture
def sample_config(testdata_dir: Path) -> dict:
    return json.loads((testdata_dir / "site.config.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_links(testdata_dir: Path) -> dict:
    return json.loads((testdata_dir / "links.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_design(testdata_dir: Path) -> dict:
    return json.loads((testdata_dir / "design.json").read_text(encoding="utf-8"))


@pytest.fixture
def build_paths(testdata_dir: Path, tmp_output_dir: Path) -> dict:
    """Return a dict of paths suitable for passing to build_site()."""
    return {
        "data_dir": testdata_dir,
        "templates_dir": testdata_dir / "templates",
        "static_dir": testdata_dir / "static",
        "output_dir": tmp_output_dir,
    }


@pytest.fixture
def committed_config_path() -> Path:
    """Return the path to the committed config.yaml bundled with the package."""
    return Path(__file__).parent.parent / "src" / "resourcery_ssg" / "config.yaml"


class MockResponse:
    def __init__(self, data: bytes, headers: dict = None):
        self._data = data
        self.headers = headers or {"content-type": "image/jpeg"}

    def read(self):
        return self._data

    def decode(self, encoding="utf-8"):
        return self._data.decode(encoding)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def mock_urlopen(monkeypatch):
    """Mock urllib.request.urlopen to return fake font CSS and woff2 data."""

    def _mock_urlopen(url, *args, **kwargs):
        if ".woff2" in url or "font" in url.lower():
            return MockResponse(b"fake woff2 binary data")
        return MockResponse(
            b'@font-face { font-family: "TestFont"; src: url(https://example.com/test.woff2); }'
        )

    monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen)


@pytest.fixture
def mock_requests(monkeypatch):
    """Mock requests.get / requests.Session.get to return fixture HTML/images."""
    import requests

    class MockSessionResponse:
        def __init__(self, content: bytes, text: str = "", headers: dict = None):
            self.content = content
            self.text = text
            self.headers = headers or {"content-type": "image/jpeg"}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=8192):
            yield self.content

    class MockSession:
        def get(self, url, *args, **kwargs):
            if "image.jpg" in url or any(
                ext in url for ext in [".jpg", ".png", ".gif", ".webp"]
            ):
                return MockSessionResponse(
                    content=b"fake image bytes",
                    headers={"content-type": "image/jpeg"},
                )
            html = (
                "<html><head>"
                '<meta property="og:image" content="https://example.com/og-image.jpg">'
                "</head></html>"
            )
            if "no-image" in url:
                html = "<html><head></head></html>"
            return MockSessionResponse(content=html.encode(), text=html)

    monkeypatch.setattr(requests.Session, "get", MockSession().get)


def pytest_addoption(parser):
    parser.addoption(
        "--network", action="store_true", help="run network-dependent tests"
    )
    parser.addoption(
        "--model",
        action="store",
        default=None,
        help="Model to use for E2E tests (required for -m e2e)",
    )
    parser.addoption(
        "--opencode-path",
        action="store",
        default="opencode",
        help="Path to opencode binary for E2E tests",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--network"):
        skip_network = pytest.mark.skip(reason="use --network to run")
        for item in items:
            if "network" in item.keywords:
                item.add_marker(skip_network)
    if not config.getoption("--model"):
        skip_e2e = pytest.mark.skip(reason="use --model <name> to run E2E tests")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)
