#!/usr/bin/env python3
"""
Image Acquisition Module for Static Link Aggregation Site.
Extracts images from linked websites via meta tags or screenshots.
"""

import os
import re
import json
import hashlib
import asyncio
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image
import io

try:
    from pyppeteer import launch

    PUPPETEER_AVAILABLE = True
except ImportError:
    PUPPETEER_AVAILABLE = False
    print("⚠️  pyppeteer not installed. Screenshot fallback disabled.")


class ImageAcquirer:
    """Handles image acquisition from linked websites."""

    def __init__(self, root_dir: Path = None):
        """Initialise the acquirer with project root and output directory.

        root_dir: project root directory. Defaults to the directory
            containing this file.

        Side-effects: creates the acquired images output directory if it
            does not exist.
        """

        self.root_dir = root_dir or Path(__file__).parent
        self.output_dir = self.root_dir / "static" / "images" / "acquired"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

        self.stats = {
            "total": 0,
            "from_meta": 0,
            "from_screenshot": 0,
            "failed": 0,
            "skipped": 0,
        }

    def _generate_filename(self, url: str, link_id: str) -> str:
        """Generate a unique, deterministic filename for a link image.

        Combines a sanitised link ID with an MD5 prefix of the URL
        to produce a filename that is both human-readable and unique.

        url: the source URL of the link.
        link_id: the link's alphanumeric identifier.

        Returns: filename string ending in .jpg.
        """

        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        safe_id = re.sub(r"[^a-z0-9]", "-", link_id.lower())
        return f"{safe_id}_{url_hash}.jpg"

    def _is_valid_image_url(self, url: str) -> bool:
        """Check whether a URL has the basic structure of a valid image URL.

        url: the URL string to check.

        Returns: True if the URL has a scheme and network location, False otherwise.
        """

        if not url:
            return False
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        return True

    def _download_image(self, url: str, save_path: Path) -> bool:
        """Download, validate, and optimise an image from a URL.

        Fetches the image, verifies the content-type, saves to disk,
        validates with Pillow, converts to RGB, resizes if wider than
        800 px, and re-saves as optimised JPEG.

        url: the remote image URL.
        save_path: local filesystem path to save to.

        Returns: True if the download and processing succeeded, False otherwise.

        Exception: any network, IO, or image-processing error is caught
            internally and returns False.
        """

        try:
            response = self.session.get(url, timeout=10, stream=True)
            response.raise_for_status()

            # Verify it's an image
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                return False

            # Save to file
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Validate and optimize image
            img = Image.open(save_path)
            img.verify()

            # Reopen and convert to JPEG if needed
            img = Image.open(save_path)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Resize if too large (max 800px width)
            max_width = 800
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            # Save optimized version
            temp_path = save_path.with_suffix(".tmp.jpg")
            img.save(temp_path, "JPEG", quality=85, optimize=True)
            temp_path.replace(save_path)

            return True

        except Exception as e:
            print(f"      ❌ Download failed: {e}")
            return False

    def extract_meta_image(self, url: str) -> Optional[str]:
        """Extract an image URL from a webpage's meta tags.

        Checks og:image, og:image:secure_url, twitter:image, and
        link[rel=image_src] in order of preference. Returns the first
        valid image URL found.

        url: the webpage URL to scrape.

        Returns: absolute image URL string, or None if no suitable tag found.

        Exception: any network or parse error is caught internally and
            returns None.
        """

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Try various meta tags in order of preference
            meta_selectors = [
                ("meta", {"property": "og:image"}),
                ("meta", {"property": "og:image:secure_url"}),
                ("meta", {"name": "twitter:image"}),
                ("meta", {"name": "twitter:image:src"}),
                ("meta", {"property": "twitter:image"}),
                ("link", {"rel": "image_src"}),
            ]

            for tag, attrs in meta_selectors:
                meta_tag = soup.find(tag, attrs)
                if meta_tag:
                    img_url = meta_tag.get("content") or meta_tag.get("href")
                    if img_url:
                        # Convert relative URLs to absolute
                        img_url = urljoin(url, img_url)
                        if self._is_valid_image_url(img_url):
                            print(f"      ✓ Found in meta tags: {img_url[:60]}...")
                            return img_url

            return None

        except Exception as e:
            print(f"      ⚠️  Meta extraction failed: {e}")
            return None

    async def capture_screenshot(self, url: str, save_path: Path) -> bool:
        """Capture a screenshot of a webpage using headless Puppeteer.

        Launches a headless Chromium browser, navigates to the URL,
        takes a JPEG screenshot, crops to the top 40% (hero area),
        and resizes to a standard width.

        url: the webpage URL to capture.
        save_path: local filesystem path for the screenshot.

        Returns: True if the screenshot was captured and saved, False otherwise.

        Exception: any browser, navigation, or processing error is caught
            internally and returns False.
        """

        if not PUPPETEER_AVAILABLE:
            print("      ⚠️  Puppeteer not available")
            return False

        try:
            browser = await launch(headless=True, args=["--no-sandbox"])
            page = await browser.newPage()

            # Set viewport for consistent screenshots
            await page.setViewport({"width": 1200, "height": 800})

            # Navigate to page
            await page.goto(url, waitUntil="networkidle2", timeout=30000)

            # Take screenshot
            screenshot = await page.screenshot(
                {"type": "jpeg", "quality": 85, "fullPage": False}
            )

            await browser.close()

            # Save and optimize
            with open(save_path, "wb") as f:
                f.write(screenshot)

            # Crop to top portion (hero area) - typically more useful
            img = Image.open(save_path)
            width, height = img.size
            # Crop top 40% of screenshot (usually contains logo/hero)
            crop_height = int(height * 0.4)
            img = img.crop((0, 0, width, crop_height))

            # Resize to standard width
            max_width = 800
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            # Save final version
            temp_path = save_path.with_suffix(".tmp.jpg")
            img.save(temp_path, "JPEG", quality=85, optimize=True)
            temp_path.replace(save_path)

            print(f"      ✓ Screenshot captured")
            return True

        except Exception as e:
            print(f"      ❌ Screenshot failed: {e}")
            try:
                await browser.close()
            except:
                pass
            return False

    def acquire_for_link(self, link: Dict, force: bool = False) -> Optional[str]:
        """Acquire an image for a single link entry.

        Attempts to acquire an image via meta tag extraction first,
        then falls back to Puppeteer screenshot. Skips if the image
        already exists locally (unless force is True).

        link: link dictionary with at least 'id', 'url', and 'image' keys.
        force: if True, re-acquire even if the image already exists.

        Returns: the local path string to the acquired image, or None on failure.

        Side-effects: prints status messages; downloads files to output_dir.
        """

        link_id = link.get("id", "unknown")
        url = link.get("url", "")
        existing_image = link.get("image", "")

        self.stats["total"] += 1

        # Check if image already exists locally
        if existing_image and existing_image.startswith("/static/images/acquired/"):
            existing_path = self.root_dir / existing_image.lstrip("/")
            if existing_path.exists() and not force:
                print(f"  ⏭️  {link_id}: Already acquired (skipping)")
                self.stats["skipped"] += 1
                return existing_image

        print(f"  📷 {link_id}: {url[:50]}...")

        # Generate filename
        filename = self._generate_filename(url, link_id)
        save_path = self.output_dir / filename

        # Skip if file exists and not forcing
        if save_path.exists() and not force:
            print(f"      ⏭️  File exists (use --force to re-acquire)")
            self.stats["skipped"] += 1
            return f"/static/images/acquired/{filename}"

        # Method 1: Try meta tags
        meta_image_url = self.extract_meta_image(url)
        if meta_image_url:
            if self._download_image(meta_image_url, save_path):
                print(f"      ✅ Acquired from meta tags")
                self.stats["from_meta"] += 1
                return f"/static/images/acquired/{filename}"

        # Method 2: Try screenshot
        if PUPPETEER_AVAILABLE:
            print(f"      📸 Trying screenshot...")
            if asyncio.run(self.capture_screenshot(url, save_path)):
                self.stats["from_screenshot"] += 1
                return f"/static/images/acquired/{filename}"

        # Failed
        self.stats["failed"] += 1
        print(f"      ❌ Failed to acquire image")
        return None

    def acquire_all(self, links_data: Dict, force: bool = False) -> Dict:
        """Acquire images for every active link in the dataset.

        Iterates over all links, skips inactive ones, calls
        acquire_for_link for each, and updates the link's 'image' field
        with the acquired local path.

        links_data: dictionary with a 'links' key containing link records.
        force: if True, re-acquire all images regardless of cache.

        Returns: the updated links_data dictionary with image paths populated.

        Side-effects: prints acquisition summary to stdout; mutates link
            entries in place; downloads files to output_dir.
        """

        print("\n🖼️  Image Acquisition")
        print("=" * 60)

        for link in links_data.get("links", []):
            if link.get("status") != "active":
                continue

            image_path = self.acquire_for_link(link, force)
            if image_path:
                link["image"] = image_path

        print("\n" + "=" * 60)
        print("📊 Acquisition Summary:")
        print(f"   Total links:     {self.stats['total']}")
        print(f"   From meta tags:  {self.stats['from_meta']}")
        print(f"   From screenshots: {self.stats['from_screenshot']}")
        print(f"   Failed:          {self.stats['failed']}")
        print(f"   Skipped:         {self.stats['skipped']}")
        print("=" * 60)

        return links_data


def main():
    """Run image acquisition from the command line.

    Parses --force and --links arguments, loads the links data file,
    acquires images for all active links, backs up the original file,
    and writes the updated data in place.

    Returns: 0 on success, 1 if the links file is not found.

    Side-effects: overwrites data/links.json (with a .json.bak backup);
        prints progress to stdout.
    """

    import argparse

    parser = argparse.ArgumentParser(
        description="Acquire images for link aggregation site"
    )
    parser.add_argument("--force", action="store_true", help="Re-acquire all images")
    parser.add_argument(
        "--links", type=str, default="data/links.json", help="Path to links.json"
    )
    args = parser.parse_args()

    root_dir = Path(__file__).parent
    links_path = root_dir / args.links

    if not links_path.exists():
        print(f"❌ Links file not found: {links_path}")
        return 1

    # Load links
    with open(links_path, "r", encoding="utf-8") as f:
        links_data = json.load(f)

    # Acquire images
    acquirer = ImageAcquirer(root_dir)
    updated_data = acquirer.acquire_all(links_data, force=args.force)

    # Save updated links
    backup_path = links_path.with_suffix(".json.bak")
    links_path.rename(backup_path)

    with open(links_path, "w", encoding="utf-8") as f:
        json.dump(updated_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Updated {links_path}")
    print(f"   Backup saved to: {backup_path}")

    return 0


if __name__ == "__main__":
    exit(main())
