#!/usr/bin/env python3
"""
Batch crawler using Crawl4AI - bypasses WAF and anti-bot protection
"""

import sys
import io
import json
import time
import re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from crawl4ai import AsyncWebCrawler
import asyncio

# Configuration
DATA_DIR = Path("d:/stepperonline_crawler_data")
STATE_FILE = DATA_DIR / "crawler_state.json"
OUTPUT_FILE = DATA_DIR / "products_crawl4ai.json"
BATCH_SIZE = 50
CONCURRENCY = 3

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

def parse_product(markdown, url):
    """Parse product data from crawl4ai markdown"""
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

    if not markdown or len(markdown) < 100:
        return None

    lines = markdown.split('\n')

    # Find product name (usually in title or first heading)
    for line in lines[:20]:
        line = line.strip()
        if line and len(line) > 20 and len(line) < 200:
            if any(kw in line.lower() for kw in ['stepper', 'motor', 'servo', 'gearbox', 'linear', 'driver', 'kit']):
                data['name'] = line
                break

    # Extract SKU
    sku_match = re.search(r'-\s*([A-Z0-9][A-Z0-9-]{4,20})\s*(?:\||$)', markdown)
    if sku_match:
        data['sku'] = sku_match.group(1)

    # Extract price
    price_match = re.search(r'\$([\d,]+\.?\d*)', markdown)
    if price_match:
        price_str = price_match.group(1).replace(',', '')
        try:
            data['price'] = float(price_str)
        except:
            pass

    # Extract stock
    stock_match = re.search(r'In Stock[:\s]*(\d+)', markdown, re.I)
    if stock_match:
        data['stock'] = int(stock_match.group(1))

    # Extract weight
    weight_match = re.search(r'(?:Gross )?Weight[:\s]*([\d.]+)\s*(kg|g)', markdown, re.I)
    if weight_match:
        weight_val = float(weight_match.group(1))
        if weight_match.group(2).lower() == 'g':
            weight_val = weight_val / 1000
        data['weight'] = weight_val

    # Volume discounts
    disc_pattern = re.compile(r'(\d+)\s*\+\s*\$([\d.]+)')
    for match in disc_pattern.findall(markdown):
        data['volume_discounts'].append({'qty': int(match[0]), 'price': float(match[1])})

    # Extract specifications section
    spec_section = re.search(r'(?:Specification|Parameter|Spec)(?:s)?[\s:]*\n(.*?)(?:\n\n|\nDescription|\nRelated|\nFeatured)', markdown, re.DOTALL | re.I)
    if spec_section:
        spec_text = spec_section.group(1)
        for line in spec_text.split('\n'):
            match = re.match(r'^\s*([A-Za-z\s/]+)[:\s]+([^\n]+)', line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                if key and value and len(key) < 50:
                    data['specifications'][key] = value

    # Extract description
    desc_match = re.search(r'Description\s*\n(.*?)(?:\n\n|\nSpecification|\nParameter)', markdown, re.DOTALL | re.I)
    if desc_match:
        data['description'] = desc_match.group(1).strip()[:2000]

    # Extract images from markdown links
    img_pattern = re.search(r'!\[.*?\]\((https?://[^)]+\.(?:jpg|jpeg|png|webp)[^)]*)\)', markdown)
    if img_pattern:
        data['images'].append(img_pattern.group(1))

    return data if data.get('name') or data.get('price') else None

async def crawl_batch(urls, crawler):
    """Crawl a batch of URLs concurrently"""
    results = []

    for url in urls:
        try:
            result = await crawler.arun(url=url)
            if result.success and result.markdown:
                data = parse_product(result.markdown, url)
                if data:
                    results.append(data)
                    print(f"OK - {data.get('sku', 'N/A')[:20]} | ${data.get('price', 0)}")
                else:
                    print(f"PARSE FAIL - {url[-50:]}")
            else:
                print(f"FAIL - {url[-50:]}")
        except Exception as e:
            print(f"ERROR - {str(e)[:50]}")
        finally:
            await asyncio.sleep(1)  # Rate limiting

    return results

async def main():
    print("=" * 60)
    print("OMC StepperOnline Crawler (Crawl4AI)")
    print("=" * 60)

    product_urls = load_urls()
    crawled = load_crawled()

    if not product_urls:
        print("No URLs found")
        return

    remaining_urls = [url for url in product_urls if url not in crawled]
    print(f"Total: {len(product_urls)}, Crawled: {len(crawled)}, Remaining: {len(remaining_urls)}")

    # Load existing products
    existing_products = []
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            existing_products = json.load(f)
        print(f"Loaded {len(existing_products)} existing products")

    products = existing_products.copy()
    total_to_crawl = min(BATCH_SIZE, len(remaining_urls))

    print(f"\nCrawling {total_to_crawl} products with Crawl4AI...")

    async with AsyncWebCrawler(verbose=False) as crawler:
        for i in range(0, total_to_crawl, CONCURRENCY):
            batch = remaining_urls[i:i+CONCURRENCY]
            print(f"\n--- Batch {i//CONCURRENCY + 1} ---")

            results = await crawl_batch(batch, crawler)
            products.extend(results)
            crawled.extend([r['source_url'] for r in results])

            await asyncio.sleep(2)  # Pause between batches

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
    print(f"Total crawled URLs: {len(crawled)}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
