#!/usr/bin/env python3
"""Extract complete product data from HTML cache"""

import sys
import io
import json
import re
import os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = Path("d:/stepperonline_crawler_data")
HTML_CACHE = DATA_DIR / "html_cache"
OUTPUT_DIR = DATA_DIR / "consolidated"
OUTPUT_DIR.mkdir(exist_ok=True)

def extract_from_html(html_path):
    """Extract complete data from HTML file"""
    try:
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
    except:
        return None

    data = {
        'images': [],
        'specifications': {},
        'pdfs': [],
        'description': '',
        'volume_discounts': []
    }

    # Extract product images from gallery
    # Pattern 1: data-image attribute
    img_patterns = [
        r'data-image="([^"]+)"',
        r'<img[^>]+src="([^"]+catalog[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
        r'"large":"([^"]+)"',
        r'"thumb":"([^"]+)"',
    ]

    for pattern in img_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            if isinstance(m, tuple):
                m = m[0]
            if 'logo' not in m.lower() and 'menu' not in m.lower():
                # Convert relative to absolute
                if m.startswith('//'):
                    m = 'https:' + m
                elif m.startswith('/'):
                    m = 'https://www.omc-stepperonline.com' + m
                if m not in data['images']:
                    data['images'].append(m)

    # Extract specifications table
    spec_patterns = [
        r'<td[^>]*class="[^"]*spec-[^"]*"[^>]*>([^<]+)</td>',
        r'<th[^>]*>([^<]+)</th>\s*<td[^>]*>([^<]+)</td>',
        r'<td[^>]*>\s*<strong>([^<]+)</strong>\s*</td>\s*<td[^>]*>([^<]+)</td>',
    ]

    spec_text = re.search(r'<table[^>]*class="[^"]*spec[^"]*"[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
    if spec_text:
        table = spec_text.group(1)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL)
        for row in rows:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
            if len(cells) >= 2:
                key = re.sub(r'<[^>]+>', '', cells[0]).strip()
                val = re.sub(r'<[^>]+>', '', cells[1]).strip()
                if key and val:
                    data['specifications'][key] = val

    # Extract PDF/datasheet URLs
    pdf_patterns = [
        r'href="([^"]+\.pdf[^"]*)"',
        r'"pdf":"([^"]+)"',
    ]
    for pattern in pdf_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            if m.startswith('/'):
                m = 'https://www.omc-stepperonline.com' + m
            if m not in data['pdfs']:
                data['pdfs'].append(m)

    # Extract description
    desc_pattern = r'<div[^>]*id="tab-description"[^>]*>(.*?)</div>'
    desc_match = re.search(desc_pattern, html, re.DOTALL | re.IGNORECASE)
    if desc_match:
        desc_html = desc_match.group(1)
        # Clean HTML tags
        desc = re.sub(r'<[^>]+>', ' ', desc_html)
        desc = re.sub(r'\s+', ' ', desc).strip()
        data['description'] = desc[:2000]  # Limit length

    # Extract volume discounts
    vol_pattern = r'<tr[^>]*class="[^"]*price-quantity[^"]*"[^>]*>(.*?)</tr>'
    vol_matches = re.findall(vol_pattern, html, re.DOTALL | re.IGNORECASE)
    for vol_row in vol_matches:
        qty = re.search(r'(\d+)', vol_row)
        price = re.search(r'\$?([\d,]+\.?\d*)', vol_row)
        if qty and price:
            data['volume_discounts'].append({
                'min_quantity': int(qty.group(1)),
                'price': float(re.sub(r'[^\d.]', '', price.group(1)))
            })

    return data

def process_html_cache():
    """Process all HTML files in cache"""
    results = []

    html_files = list(HTML_CACHE.glob("*.html"))
    print(f"Processing {len(html_files)} HTML files...")

    for i, html_file in enumerate(html_files):
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{len(html_files)}")

        extracted = extract_from_html(html_file)
        if extracted:
            slug = html_file.stem
            results.append({
                'slug': slug,
                'file': str(html_file.name),
                **extracted
            })

    return results

def main():
    print("=" * 60)
    print("Extract Complete Data from HTML Cache")
    print("=" * 60)

    # Process HTML cache
    print("\n1. Processing HTML cache...")
    extracted = process_html_cache()
    print(f"\n   Extracted data from {len(extracted)} products")

    # Summary
    total_images = sum(len(r['images']) for r in extracted)
    total_specs = sum(len(r['specifications']) for r in extracted)
    total_pdfs = sum(len(r['pdfs']) for r in extracted)

    print(f"\n2. Summary:")
    print(f"   - Total products: {len(extracted)}")
    print(f"   - Total image URLs: {total_images}")
    print(f"   - Total specifications: {total_specs}")
    print(f"   - Total PDF URLs: {total_pdfs}")

    # Show sample
    if extracted:
        sample = extracted[0]
        print(f"\n3. Sample data (first product):")
        print(f"   Slug: {sample['slug']}")
        print(f"   Images: {len(sample['images'])}")
        print(f"   Specs: {len(sample['specifications'])}")
        print(f"   PDFs: {len(sample['pdfs'])}")

        if sample['specifications']:
            print(f"   Sample specs: {dict(list(sample['specifications'].items())[:3])}")

    # Save
    output_file = OUTPUT_DIR / "html_extracted_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)
    print(f"\n4. Saved to: {output_file}")

    # Save image URLs separately
    all_images = []
    for r in extracted:
        for img in r['images']:
            all_images.append({
                'slug': r['slug'],
                'url': img
            })

    img_file = OUTPUT_DIR / "product_images.json"
    with open(img_file, 'w', encoding='utf-8') as f:
        json.dump(all_images, f, indent=2, ensure_ascii=False)
    print(f"   Saved {len(all_images)} image URLs to: product_images.json")

    # Save PDF URLs separately
    all_pdfs = []
    for r in extracted:
        for pdf in r['pdfs']:
            all_pdfs.append({
                'slug': r['slug'],
                'url': pdf
            })

    pdf_file = OUTPUT_DIR / "product_pdfs.json"
    with open(pdf_file, 'w', encoding='utf-8') as f:
        json.dump(all_pdfs, f, indent=2, ensure_ascii=False)
    print(f"   Saved {len(all_pdfs)} PDF URLs to: product_pdfs.json")

if __name__ == "__main__":
    main()
