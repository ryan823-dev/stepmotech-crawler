#!/usr/bin/env python3
"""Download product PDFs/datasheets"""

import sys
import io
import json
import re
from pathlib import Path
import subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = Path("d:/stepperonline_crawler_data")
OUTPUT_DIR = Path("d:/stepperonline_crawler_pdfs")
OUTPUT_DIR.mkdir(exist_ok=True)

def fix_pdf_url(url):
    """Fix malformed PDF URLs"""
    # Fix common URL encoding issues
    url = url.replace('&amp;', '&')
    url = url.replace('=product', '?route=product')
    url = url.replace('=product', '?route=product')

    # Ensure proper base URL
    if not url.startswith('http'):
        if url.startswith('/'):
            url = 'https://www.omc-stepperonline.com' + url
        else:
            url = 'https://www.omc-stepperonline.com/' + url

    return url

def download_pdf(url, output_path):
    """Download PDF using curl"""
    headers = [
        'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer: https://www.omc-stepperonline.com/',
        'Accept: application/pdf,*/*',
    ]

    cmd = ['curl', '-s', '-L', '-o', str(output_path), '-w', '%{http_code}']
    for h in headers:
        cmd.extend(['-H', h])
    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.stdout.strip()
    except:
        return '000'

def main():
    print("=" * 60)
    print("Download Product PDFs/Datasheets")
    print("=" * 60)

    # Load PDF list
    with open(DATA_DIR / "consolidated/pdf_list.json", 'r', encoding='utf-8') as f:
        pdfs = json.load(f)

    print(f"\nTotal PDFs to download: {len(pdfs)}")

    # Download
    success = 0
    failed = 0
    skipped = 0

    print("\nDownloading...")

    for i, pdf in enumerate(pdfs):
        slug = pdf['slug']
        url = fix_pdf_url(pdf['url'])

        # Extract filename from URL
        filename = url.split('/')[-1].split('?')[0]
        if not filename.endswith('.pdf'):
            filename = f"{slug}.pdf"

        output_path = OUTPUT_DIR / filename

        # Skip if exists
        if output_path.exists() and output_path.stat().st_size > 1000:
            skipped += 1
            continue

        http_code = download_pdf(url, output_path)

        if output_path.exists() and output_path.stat().st_size > 1000:
            # Verify it's actually a PDF
            with open(output_path, 'rb') as f:
                header = f.read(5)
            if header.startswith(b'%PDF'):
                success += 1
            else:
                failed += 1
                output_path.unlink()  # Remove invalid file
        else:
            failed += 1

        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(pdfs)} | Success: {success} | Failed: {failed} | Skipped: {skipped}")

    print("\n" + "=" * 60)
    print(f"COMPLETE: {success} success, {failed} failed, {skipped} skipped")
    print(f"Output: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
