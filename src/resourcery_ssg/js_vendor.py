#!/usr/bin/env python3
"""
JS vendor acquirer for Resourcery.ssg
Downloads the Nanostores library at build time into static/js/vendor/.
No CDN dependency at runtime — consistent with the project's zero-runtime-dependency philosophy.

Run before build.py:
    poetry run python js_vendor.py
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path


def read_cached_nanostores(vendor_path: Path) -> tuple[str, str] | None:
    """Read the cached Nanostores version and source URL from the header comment.

    vendor_path: path to the vendored nanostores.js file.

    Returns: (version, source_url) tuple if the header is valid, None otherwise.
    """
    if not vendor_path.exists():
        return None
    first_line = vendor_path.read_text(encoding="utf-8").split("\n")[0]
    match = re.match(
        r"/\*\s*nanostores\s+(\S+)\s+source:\s+(\S+)\s+acquired:\s+\S+\s*\*/",
        first_line,
    )
    if not match:
        return None
    return match.group(1), match.group(2)


def is_cache_valid(vendor_path: Path, wanted_version: str) -> bool:
    """Check whether the local vendored file is up to date.

    Verifies that the file exists and its header matches the wanted version.

    vendor_path: path to the vendored nanostores.js file.
    wanted_version: expected version string (e.g. "0.11.4").

    Returns: True if the cache is valid, False otherwise.
    """
    cached = read_cached_nanostores(vendor_path)
    if cached is None:
        return False
    return cached[0] == wanted_version


def download_nanostores(
    version: str,
    vendor_path: Path,
    *,
    source_url: str | None = None,
) -> None:
    """Download Nanostores from unpkg and write to vendor_path.

    Prepends a header comment with version, source URL, and acquisition date.
    Writes atomically: on failure the existing file (if any) is untouched.

    version: the Nanostores version to download.
    vendor_path: destination path for the vendored file.
    source_url: override the default unpkg URL.

    Raises:
        Exception: re-raises any network/IO error with a descriptive message.
    """
    import datetime

    if source_url is None:
        source_url = (
            f"https://esm.sh/nanostores@{version}/es2022/nanostores.mjs"
        )

    today = datetime.date.today().isoformat()
    header = (
        f"/* nanostores {version} source: {source_url} acquired: {today} */\n"
    )

    req = urllib.request.Request(
        source_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8")
    except Exception as e:
        print(f"  ✗ Failed to download {source_url}: {e}")
        raise

    # Write atomically: write to a temp file, then rename
    tmp_path = vendor_path.with_suffix(vendor_path.suffix + ".tmp")
    try:
        tmp_path.write_text(header + body, encoding="utf-8")
        tmp_path.rename(vendor_path)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        print(f"  ✗ Failed to write {vendor_path}: {e}")
        raise


def acquire_js(
    *,
    package_json_path: Path | None = None,
    vendor_dir: Path | None = None,
) -> None:
    """Orchestrate the acquisition of the Nanostores JS library.

    Reads package.json for the desired version, checks the local cache,
    and downloads if needed.

    Args:
        package_json_path: path to package.json. Defaults to repo root.
        vendor_dir: directory to write vendored JS files into. Defaults to
            ``./static/js/vendor/``.

    Raises:
        SystemExit: on any error, with exit code 1 and a clear message.
    """
    if package_json_path is None:
        package_json_path = (
            Path(__file__).resolve().parent.parent.parent / "package.json"
        )
    if vendor_dir is None:
        vendor_dir = Path("./static/js/vendor/")

    # Check package.json exists
    if not package_json_path.exists():
        print(f"Error: package.json not found at {package_json_path}", file=sys.stderr)
        sys.exit(1)

    # Load package.json
    try:
        pkg = json.loads(package_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(
            f"Error: package.json is not valid JSON: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Extract nanostores version
    deps = pkg.get("dependencies", {})
    version = deps.get("nanostores")
    if not version:
        print(
            "Error: package.json has no dependencies.nanostores entry",
            file=sys.stderr,
        )
        sys.exit(1)

    vendor_path = vendor_dir / "nanostores.js"

    # Check cache
    if is_cache_valid(vendor_path, version):
        print(
            f"ℹ  nanostores@{version} is up to date — skipping download"
        )
        return

    # Ensure vendor directory exists
    try:
        vendor_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(
            f"Error: cannot write to {vendor_dir}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check writability
    if vendor_dir.exists() and not os.access(str(vendor_dir), os.W_OK):
        print(
            f"Error: cannot write to {vendor_dir}: permission denied",
            file=sys.stderr,
        )
        sys.exit(1)

    # Download
    try:
        download_nanostores(version, vendor_path)
    except Exception as e:
        print(
            f"Error: failed to download https://esm.sh/nanostores@{version}/"
            f"es2022/nanostores.mjs: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"✓ nanostores@{version} acquired → {vendor_path}")


def main():
    """Entry-point for CLI (registered in pyproject.toml scripts).

    Parses CLI arguments, loads configuration, and dispatches to acquire_js().
    """
    import argparse

    parser = argparse.ArgumentParser(description="Acquire the Nanostores JS library")
    parser.add_argument(
        "--package-json", type=str, default=None, help="Path to package.json"
    )
    parser.add_argument(
        "--vendor-dir", type=str, default=None, help="Vendor output directory"
    )
    parser.add_argument(
        "--config", type=str, default=None, help="Path to config YAML"
    )
    args = parser.parse_args()

    from resourcery_ssg.config import load_resourcery_config

    overrides = {}
    flag_to_key = {
        "package_json": "package_json_path",
        "vendor_dir": "vendor_dir",
    }
    for flag, key in flag_to_key.items():
        val = getattr(args, flag, None)
        if val is not None:
            overrides[f"acquire-js.{key}"] = val

    config = load_resourcery_config(
        config_path=args.config,
        overrides=overrides,
    )
    acquire_js(**config["acquire-js"])


if __name__ == "__main__":
    main()
