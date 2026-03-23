#!/usr/bin/env python3
"""
Improved batch crawler with anti-blocking measures
"""

import json
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

# Configuration
DATA_DIR = Path("d:/stepperonline_crawler_data")
STATE_FILE = DATA_DIR / "crawler_state.json"
OUTPUT_FILE = DATA_DIR / "products_batch.json"
BATCH_SIZE = 10
INITIAL_DELAY = 15  # Longer initial delay to reset IP ban
REQUEST_DELAY = 12  # Delay between requests

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]

def load_urls():
    urls_file = Path("d:/stepperonline_crawler_data/product_urls.txt")
    if urls_file.exists():
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and line.startswith('http')]
        if urls:
            print(f"Loaded {len(urls)} URLs")
            return urls
    return []

def load_crawled():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
            return state.get('crawled', [])
    return []

def parse_product(text, url):
    import re
    
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

    for line in text.split('\n'):
        line = line.strip()
        if 'Stepper Motor' in line and 20 < len(line) < 200:
            data['name'] = line
            break

    sku_match = re.search(r'Model[:\s]*([A-Z0-9-]+)', text)
    if sku_match:
        data['sku'] = sku_match.group(1)

    price_match = re.search(r'\$([\d.]+)', text)
    if price_match:
        data['price'] = float(price_match.group(1))

    stock_match = re.search(r'In Stock[:\s]*(\d+)', text)
    if stock_match:
        data['stock'] = int(stock_match.group(1))

    weight_match = re.search(r'Gross Weight[:\s]*([\d.]+)\s*kg', text)
    if weight_match:
        data['weight'] = float(weight_match.group(1))

    cert_match = re.search(r'Certificated[:\s]*([\w,\s]+?)(?=\s*(?:Click|Ships|$))', text)
    if cert_match:
        data['certifications'] = cert_match.group(1).strip()

    disc_pattern = re.compile(r'(\d+)\s*\+\s*\$([\d.]+)')
    for match in disc_pattern.findall(text):
        data['volume_discounts'].append({'qty': int(match[0]), 'price': float(match[1])})

    desc_match = re.search(r'DESCRIPTION\s+(.{100,1500}?)(?:SPECIFICATIONS|DIMENSIONS)', text, re.DOTALL)
    if desc_match:
        data['description'] = desc_match.group(1).strip()

    return data

def main():
    print("=" * 60)
    print("OMC StepperOnline Batch Crawler (Anti-Block)")
    print("=" * 60)

    product_urls = load_urls()
    crawled = load_crawled()

    if not product_urls:
        print("No URLs found")
        return

    remaining_urls = [url for url in product_urls if url not in crawled]
    print(f"Total: {len(product_urls)}, Already crawled: {len(crawled)}, Remaining: {len(remaining_urls)}")

    if not remaining_urls:
        print("All URLs already crawled!")
        return

    print(f"\nStarting crawl of {min(BATCH_SIZE, len(remaining_urls))} products...")
    print(f"Initial delay: {INITIAL_DELAY}s to reset any IP blocks...")

    # Initial delay before starting
    time.sleep(INITIAL_DELAY)

    # Load existing products first
    existing_products = []
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            existing_products = json.load(f)
        print(f"Loaded {len(existing_products)} existing products")

    products = []
    failed = []
    consecutive_blocks = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage']
        )

        for i, url in enumerate(remaining_urls[:BATCH_SIZE]):
            slug = url.split('/')[-1][:50]
            
            # If we get 3 consecutive blocks, take a longer break
            if consecutive_blocks >= 3:
                print(f"\n!!! Too many blocks, taking 60s break...")
                time.sleep(60)
                consecutive_blocks = 0
            
            print(f"[{i+1}/{BATCH_SIZE}] {slug}...", end='', flush=True)

            try:
                # Create new context for each request to avoid state tracking
                context = browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={'width': 1920, 'height': 1080}
                )
                context.add_init_script('''
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                ''')
                
                page = context.new_page()
                
                # Navigate with longer wait
                page.goto(url, timeout=60000, wait_until='domcontentloaded')
                time.sleep(3)  # Wait for any JavaScript

                text = page.locator('body').inner_text()

                if 'access denied' in text.lower():
                    print(" BLOCKED")
                    failed.append(url)
                    consecutive_blocks += 1
                    context.close()
                    # Exponential backoff
                    sleep_time = 10 * consecutive_blocks
                    print(f"    Waiting {sleep_time}s before next request...")
                    time.sleep(sleep_time)
                    continue

                # Success
                consecutive_blocks = 0
                data = parse_product(text, url)
                products.append(data)
                crawled.append(url)
                print(f" OK - {data.get('sku', 'N/A')} | Stock: {data.get('stock', 'N/A')}")
                
                page.close()
                context.close()

            except Exception as e:
                print(f" ERROR - {str(e)[:50]}")
                failed.append(url)
                consecutive_blocks += 1

            # Delay between requests
            if i < BATCH_SIZE - 1:
                delay = REQUEST_DELAY + random.uniform(0, 5)
                print(f"    Delay: {delay:.1f}s...")
                time.sleep(delay)

        browser.close()

    # Save products
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

    # Update state
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump({'product_urls': product_urls, 'crawled': crawled}, f, indent=2)

    print(f"\n" + "=" * 60)
    print(f"Crawl complete!")
    print(f"Products: {len(products)}")
    print(f"Failed: {len(failed)}")
    print(f"Total crawled: {len(crawled)}")

if __name__ == "__main__":
    main()
