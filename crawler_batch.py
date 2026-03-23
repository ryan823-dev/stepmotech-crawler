#!/usr/bin/env python3
"""
Batch crawler using curl subprocess
"""

import json
import time
import subprocess
import re
import os
from pathlib import Path

# Configuration
DATA_DIR = Path("d:/stepperonline_crawler_data")
STATE_FILE = DATA_DIR / "crawler_state.json"
OUTPUT_FILE = DATA_DIR / "products_curl.json"
HTML_DIR = DATA_DIR / "html_cache"
BATCH_SIZE = 50
REQUEST_DELAY = 1

def curl_get(url, timeout=30):
    """Fetch URL using curl"""
    try:
        proc = subprocess.Popen(
            ['curl', '-s', '-L', '--max-time', str(timeout),
             '-H', 'User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
             '-H', 'Accept: text/html,application/xhtml+xml',
             '-H', 'Accept-Language: en-US,en;q=0.9',
             url],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        stdout, _ = proc.communicate(timeout=timeout + 5)
        return stdout.decode('utf-8', errors='ignore')
    except Exception as e:
        return None

def parse_product(html, url):
    """Parse product data from HTML"""
    data = {
        'source_url': url,
        'name': '',
        'price': None,
        'sku': '',
        'stock': None,
        'weight': None,
        'certifications': '',
        'brand': 'OMC-StepperOnline',
        'description': '',
        'specifications': {},
        'images': [],
        'volume_discounts': [],
        'currency': 'USD'
    }

    if not html or len(html) < 1000:
        return None

    # Product name from title
    title_match = re.search(r'<title>([^<]+)</title>', html)
    if title_match:
        title = title_match.group(1)
        data['name'] = re.sub(r'\s*\|\s*StepperOnline\s*$', '', title)

    # Price
    price_match = re.search(r'class="product-price"[^>]*>([^<]+)', html)
    if not price_match:
        price_match = re.search(r'<[^>]+class="[^"]*price[^"]*"[^>]*>([^<]*\$[\d.]+)', html, re.I)
    if not price_match:
        price_match = re.search(r'\$([\d.]+)', html)
    if price_match:
        price_str = re.sub(r'[^\d.]', '', price_match.group(1))
        if price_str and price_str != '.':
            try:
                data['price'] = float(price_str)
            except (ValueError, AttributeError):
                pass

    # SKU from title
    sku_match = re.search(r'-\s*([A-Z0-9][A-Z0-9-]+)\s*\|', html)
    if not sku_match:
        sku_match = re.search(r'-\s*([A-Z0-9]{4,20})\s*$', data.get('name', ''))
    if not sku_match:
        sku_match = re.search(r'([A-Z0-9]{5,15})\s*</title>', html)
    if sku_match:
        data['sku'] = sku_match.group(1)

    # In Stock
    stock_match = re.search(r'In Stock[:\s]*(\d+)', html, re.I)
    if stock_match:
        data['stock'] = int(stock_match.group(1))

    # Gross Weight
    weight_match = re.search(r'Gross Weight[:\s]*([\d.]+)\s*(kg|g)', html, re.I)
    if weight_match:
        weight_val = float(weight_match.group(1))
        if weight_match.group(2).lower() == 'g':
            weight_val = weight_val / 1000
        data['weight'] = weight_val

    # Certificated
    cert_match = re.search(r'Certificated[:\s]*([\w,\s]+?)(?=\s*(?:Click|Ships|$))', html, re.I)
    if cert_match:
        data['certifications'] = cert_match.group(1).strip()

    # Volume discounts
    disc_pattern = re.compile(r'(\d+)\s*\+\s*\$([\d.]+)')
    for match in disc_pattern.findall(html):
        data['volume_discounts'].append({'qty': int(match[0]), 'price': float(match[1])})

    # Description from meta
    desc_match = re.search(r'name="description"[^>]+content="([^"]+)"', html)
    if desc_match:
        data['description'] = desc_match.group(1)

    # Images
    img_patterns = [
        r'"image"[^:]*:\s*"([^"]+)"',
        r'data-src="(https?://[^"]*\.(?:jpg|jpeg|png|webp)[^"]*)"',
        r'src="(https?://[^"]*product[^"]*\.(?:jpg|jpeg|png|webp)[^"]*)"',
    ]
    for pattern in img_patterns:
        for match in re.finditer(pattern, html, re.I):
            img_url = match.group(1)
            if img_url and 'data:image' not in img_url and img_url not in data['images']:
                data['images'].append(img_url)

    data['images'] = list(dict.fromkeys(data['images']))[:10]

    return data if data.get('name') else None

def load_urls():
    urls_file = Path("d:/stepperonline_crawler_data/product_urls.txt")
    if urls_file.exists():
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and line.startswith('http')]
        return urls
    return []

def load_crawled():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
            return state.get('crawled', [])
    return []

def main():
    print("=" * 60)
    print("OMC StepperOnline Batch Crawler (curl)")
    print("=" * 60)

    # Ensure HTML cache directory exists
    HTML_DIR.mkdir(exist_ok=True)

    product_urls = load_urls()
    crawled = load_crawled()

    if not product_urls:
        print("No URLs found")
        return

    remaining_urls = [url for url in product_urls if url not in crawled]
    print(f"Total: {len(product_urls)}, Already crawled: {len(crawled)}, Remaining: {len(remaining_urls)}")

    # Load existing products
    existing_products = []
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            existing_products = json.load(f)
        print(f"Loaded {len(existing_products)} existing products")

    products = existing_products.copy()
    failed = []
    blocked_count = 0

    print(f"\nStarting crawl of {min(BATCH_SIZE, len(remaining_urls))} products...")

    for i, url in enumerate(remaining_urls[:BATCH_SIZE]):
        slug = url.split('/')[-1][:45]
        print(f"[{i+1}/{BATCH_SIZE}] {slug}...", end='', flush=True)

        html = curl_get(url)

        if not html or len(html) < 1000:
            print(" FAILED (no response)")
            failed.append(url)
            time.sleep(REQUEST_DELAY * 2)
            continue

        if 'access denied' in html.lower() or '403 forbidden' in html.lower():
            print(" BLOCKED")
            failed.append(url)
            blocked_count += 1
            if blocked_count >= 5:
                print("Too many blocks, stopping")
                break
            time.sleep(5)
            continue

        blocked_count = 0  # Reset on success

        # Save HTML to cache
        slug_key = slug.replace('/', '_')[:50]
        html_file = HTML_DIR / f"{slug_key}.html"
        with open(html_file, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(html)

        data = parse_product(html, url)

        if data:
            products.append(data)
            crawled.append(url)
            print(f" OK - {data.get('sku', 'N/A')} | ${data.get('price', 0)}")
        else:
            print(" PARSE FAILED")
            failed.append(url)

        time.sleep(REQUEST_DELAY)

    # Save products
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

    # Update state
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump({'product_urls': product_urls, 'crawled': crawled}, f, indent=2)

    print(f"\n" + "=" * 60)
    print(f"Crawl complete!")
    print(f"New products: {len(products) - len(existing_products)}")
    print(f"Total in file: {len(products)}")
    print(f"Failed: {len(failed)}")
    print(f"Total crawled URLs: {len(crawled)}")

if __name__ == "__main__":
    main()
