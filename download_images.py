#!/usr/bin/env python3
"""Download all product images from crawled HTML files"""

import sys
import io
import json
import re
import os
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import aiohttp

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Configuration
DATA_DIR = Path("d:/stepperonline_crawler_data")
HTML_CACHE = DATA_DIR / "html_cache"
IMAGES_DIR = DATA_DIR / "images"
BATCH_SIZE = 100

def get_image_urls():
    """Extract all image URLs from cached HTML"""
    image_urls = set()

    if not HTML_CACHE.exists():
        print(f"HTML cache not found: {HTML_CACHE}")
        return []

    for html_file in HTML_CACHE.glob("*.html"):
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                html = f.read()

            # Find all image URLs
            # Pattern 1: data-src or src attributes
            for match in re.findall(r'(?:data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I):
                if 'logo' not in match.lower() and 'menu' not in match.lower():
                    image_urls.add(match)

            # Pattern 2: Open Graph images
            for match in re.findall(r'<meta property="og:image" content="([^"]+)"', html):
                image_urls.add(match)

            # Pattern 3: Journal image data
            for match in re.findall(r'"[^"]*image[^"]*"\s*:\s*"([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', html, re.I):
                image_urls.add(match)

        except Exception as e:
            print(f"Error reading {html_file}: {e}")

    print(f"Found {len(image_urls)} unique image URLs")
    return list(image_urls)

def normalize_url(url):
    """Normalize image URL"""
    if not url:
        return None
    # Remove query params
    url = url.split('?')[0]
    # Ensure it's a valid image URL
    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
        return url
    return None

def download_image(session, url, dest_path):
    """Download single image"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36',
            'Referer': 'https://www.omc-stepperonline.com/'
        }
        response = session.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            with open(dest_path, 'wb') as f:
                f.write(response.content)
            return True, url
        return False, url
    except Exception as e:
        return False, f"{url}: {e}"

async def download_images_async(urls, max_concurrent=10):
    """Download images concurrently"""
    IMAGES_DIR.mkdir(exist_ok=True)

    downloaded = 0
    failed = []
    semaphore = asyncio.Semaphore(max_concurrent)

    async def download_with_semaphore(session, url):
        async with semaphore:
            try:
                # Normalize URL
                normalized = normalize_url(url)
                if not normalized:
                    return False, url

                # Create filename from URL
                parsed = urlparse(normalized)
                filename = parsed.path.split('/')[-1]
                if not filename or '.' not in filename:
                    filename = f"img_{hash(url)}.jpg"

                dest_path = IMAGES_DIR / filename

                # Skip if already exists
                if dest_path.exists():
                    return True, f"{url} (already exists)"

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36',
                    'Referer': 'https://www.omc-stepperonline.com/'
                }

                async with session.get(normalized, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(dest_path, 'wb') as f:
                            f.write(content)
                        return True, url
                    return False, f"{url} (status {response.status})"

            except Exception as e:
                return False, f"{url}: {e}"

    connector = aiohttp.TCPConnector(limit=max_concurrent)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [download_with_semaphore(session, url) for url in urls]
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            success, result = await coro
            if success:
                downloaded += 1
                if downloaded % 50 == 0:
                    print(f"Downloaded {downloaded}/{len(urls)} images...")
            else:
                failed.append(result)

    return downloaded, failed

def main():
    print("=" * 60)
    print("Download All Product Images")
    print("=" * 60)

    # Get all image URLs
    urls = get_image_urls()
    if not urls:
        print("No images to download")
        return

    print(f"\nDownloading {len(urls)} images...")
    print(f"Destination: {IMAGES_DIR}")
    print("-" * 60)

    # Download in batches
    downloaded = 0
    all_failed = []

    for i in range(0, len(urls), BATCH_SIZE):
        batch = urls[i:i+BATCH_SIZE]
        print(f"\nBatch {i//BATCH_SIZE + 1}: Downloading {len(batch)} images...")

        count, failed = asyncio.run(download_images_async(batch, max_concurrent=15))
        downloaded += count
        all_failed.extend(failed)

        print(f"Batch complete: {count}/{len(batch)} downloaded")

        # Small delay between batches
        time.sleep(1)

    print("\n" + "=" * 60)
    print(f"Download complete!")
    print(f"Downloaded: {downloaded}")
    print(f"Failed: {len(all_failed)}")
    print(f"Saved to: {IMAGES_DIR}")

    if all_failed[:10]:
        print("\nFirst 10 failures:")
        for f in all_failed[:10]:
            print(f"  - {f[:80]}")

if __name__ == "__main__":
    main()
