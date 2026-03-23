#!/usr/bin/env python3
"""Download product images to local storage"""

import sys
import io
import json
import re
import os
import time
import hashlib
from pathlib import Path
from urllib.parse import urlparse, unquote
import subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = Path("d:/stepmotech_crawler")
HTML_CACHE = DATA_DIR / "html_cache"
OUTPUT_DIR = Path("d:/stepmotech_crawler_images")
OUTPUT_DIR.mkdir(exist_ok=True)

def convert_cache_url_to_original(url):
    """Convert cached image URL to original URL"""
    # Replace image/cache with image/data
    url = url.replace('/image/cache/', '/image/data/')
    # Remove size suffixes like -200x, -500x, etc
    url = re.sub(r'-\d{2,4}x\d{0,4}(?=\.(?:jpg|jpeg|png|webp))', '', url)
    return url

def download_image(url, output_path, headers=None):
    """Download image using curl"""
    if headers is None:
        headers = [
            'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer: https://www.omc-stepperonline.com/',
            'Accept: image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language: en-US,en;q=0.9',
        ]

    cmd = ['curl', '-s', '-L', '-o', str(output_path), '-w', '%{http_code}']
    for h in headers:
        cmd.extend(['-H', h])
    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except:
        return False

def get_filename_from_url(url):
    """Generate filename from URL"""
    parsed = urlparse(url)
    filename = unquote(parsed.path.split('/')[-1])

    # If no filename or just extension, generate one
    if not filename or '.' not in filename:
        # Generate from URL hash
        hash_name = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"image_{hash_name}.jpg"

    # Ensure valid filename
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

    return filename

def main():
    print("=" * 60)
    print("Download Product Images")
    print("=" * 60)

    # Load complete data
    data_file = Path("d:/stepperonline_crawler_data/consolidated/complete_data.json")
    if not data_file.exists():
        print("Error: complete_data.json not found!")
        return

    with open(data_file, 'r', encoding='utf-8') as f:
        products = json.load(f)

    print(f"\nTotal products: {len(products)}")

    # Collect all unique images
    all_images = []
    seen = set()

    for product in products:
        slug = product['slug']
        for img_url in product.get('images', []):
            # Skip logo and menu images
            if 'logo' in img_url.lower() or 'menu' in img_url.lower():
                continue

            # Convert to original URL
            original_url = convert_cache_url_to_original(img_url)

            if original_url not in seen:
                seen.add(original_url)
                all_images.append({
                    'product_slug': slug,
                    'cache_url': img_url,
                    'original_url': original_url,
                    'filename': get_filename_from_url(original_url)
                })

    print(f"Unique images to download: {len(all_images)}")

    # Create product directories
    for product in products:
        slug = product['slug']
        product_dir = OUTPUT_DIR / slug
        product_dir.mkdir(exist_ok=True)

    # Download images
    success_count = 0
    fail_count = 0
    skip_count = 0

    print("\nDownloading images...")

    for i, img in enumerate(all_images):
        product_dir = OUTPUT_DIR / img['product_slug']
        output_path = product_dir / img['filename']

        # Skip if already exists
        if output_path.exists() and output_path.stat().st_size > 1000:
            skip_count += 1
            continue

        # Try original URL first, then cache URL
        urls_to_try = [img['original_url'], img['cache_url']]

        downloaded = False
        for url in urls_to_try:
            if download_image(url, output_path):
                # Verify file size
                if output_path.exists() and output_path.stat().st_size > 1000:
                    downloaded = True
                    break
            # Retry with cache URL format
            output_path = product_dir / ("cache_" + img['filename'])
            if download_image(img['cache_url'], output_path):
                if output_path.exists() and output_path.stat().st_size > 1000:
                    downloaded = True
                    break

        if downloaded:
            success_count += 1
        else:
            fail_count += 1

        if (i + 1) % 100 == 0:
            print(f"  Progress: {i + 1}/{len(all_images)} | Success: {success_count} | Failed: {fail_count} | Skipped: {skip_count}")

    print("\n" + "=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Skipped (already exists): {skip_count}")
    print(f"Output directory: {OUTPUT_DIR}")

    # Save download manifest
    manifest = {
        'total': len(all_images),
        'success': success_count,
        'failed': fail_count,
        'skipped': skip_count,
        'images': all_images[:100]  # Save first 100 for reference
    }

    with open(OUTPUT_DIR / "download_manifest.json", 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
