#!/usr/bin/env python3
"""
Fast crawler using requests with mobile User-Agent
"""

import json
import time
import requests
import re
from pathlib import Path

# Configuration
DATA_DIR = Path("d:/stepperonline_crawler_data")
STATE_FILE = DATA_DIR / "crawler_state.json"
OUTPUT_FILE = DATA_DIR / "products_curl.json"
BATCH_SIZE = 30
REQUEST_DELAY = 2

# Mobile User-Agent that bypasses WAF
MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'

def fetch_url(url, timeout=30):
    """Fetch URL using requests with mobile UA"""
    try:
        headers = {
            'User-Agent': MOBILE_UA,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            response.encoding = 'utf-8'
            return response.text
        return None
    except Exception as e:
        print(f"Request error: {e}")
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
        price_match = re.search(r'"price"\s*:\s*"?([\d.]+)', html)
    if price_match:
        price_str = re.sub(r'[^\d.]', '', price_match.group(1))
        if price_str:
            data['price'] = float(price_str)

    # SKU from meta keywords
    sku_match = re.search(r'"keywords"[^>]+content="[^"]*,\s*([A-Z0-9][A-Z0-9-]+)', html, re.I)
    if sku_match:
        data['sku'] = sku_match.group(1)

    # In Stock
    stock_match = re.search(r'In Stock\s*(\d+)', html, re.I)
    if stock_match:
        data['stock'] = int(stock_match.group(1))

    # Gross Weight
    weight_match = re.search(r'Gross Weight[:\s]*([\d.]+)\s*(?:kg|g)', html, re.I)
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
        r'src="(https?://[^"]*product[^"]*\.(?:jpg|jpeg|png|webp))"',
        r'data-src="(https?://[^"]*\.(?:jpg|jpeg|png|webp))"',
    ]
    for pattern in img_patterns:
        for match in re.finditer(pattern, html, re.I):
            img_url = match.group(1)
            if img_url and 'data:image' not in img_url:
                if img_url not in data['images']:
                    data['images'].append(img_url)

    data['images'] = data['images'][:10]

    return data if data.get('name') or data.get('price') else None

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
    print("OMC StepperOnline Fast Crawler (requests)")
    print("=" * 60)

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

    print(f"\nStarting fast crawl of {min(BATCH_SIZE, len(remaining_urls))} products...")

    for i, url in enumerate(remaining_urls[:BATCH_SIZE]):
        slug = url.split('/')[-1][:50]
        print(f"[{i+1}/{BATCH_SIZE}] {slug}...", end='', flush=True)

        html = fetch_url(url)

        if not html:
            print(" FAILED (no response)")
            failed.append(url)
            time.sleep(REQUEST_DELAY)
            continue

        if 'access denied' in html.lower() or '403 forbidden' in html.lower():
            print(" BLOCKED")
            failed.append(url)
            time.sleep(5)
            continue

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
