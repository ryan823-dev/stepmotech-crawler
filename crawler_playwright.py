#!/usr/bin/env python3
"""
Batch crawler for omc-stepperonline.com using Playwright
Bypasses 403 blocking by using headless browser
"""

import json
import time
import random
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

# Configuration
DATA_DIR = Path("d:/stepperonline_crawler_data")
STATE_FILE = DATA_DIR / "crawler_state.json"
OUTPUT_FILE = DATA_DIR / "products_batch.json"
BATCH_SIZE = 50  # Products per batch
REQUEST_DELAY = 3  # Seconds between requests

# User agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]

def load_urls():
    """Load product URLs from various sources"""
    # Try product_urls.txt first
    urls_file = Path("d:/stepperonline_crawler_data/product_urls.txt")
    if urls_file.exists():
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and line.startswith('http')]
        if urls:
            print(f"Loaded {len(urls)} URLs from product_urls.txt")
            return urls
    
    # Try state file
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
            urls = state.get('product_urls', [])
            if urls:
                print(f"Loaded {len(urls)} URLs from state file")
                return urls
    
    return []

def load_crawled():
    """Load list of already crawled URLs"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
            return state.get('crawled', [])
    return []

def save_products(products):
    """Save products to output file"""
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

def parse_price(price_str):
    """Extract numeric price from string"""
    if not price_str:
        return None
    match = re.search(r'[\d.]+', price_str.replace(',', ''))
    return float(match.group()) if match else None

def parse_product_from_text(text, url):
    """Parse product data from page text content"""
    data = {
        'source_url': url,
        'name': '',
        'price': None,
        'sku': '',
        'stock': None,
        'weight': None,
        'certifications': '',
        'brand': 'OMC-StepperOnline',
        'short_description': '',
        'description': '',
        'specifications': {},
        'images': [],
        'volume_discounts': [],
        'currency': 'USD'
    }

    lines = text.split('\n')
    i = 0

    try:
        # Find product name (usually after "Nema X Stepper Motor")
        for idx, line in enumerate(lines):
            line = line.strip()
            if 'Stepper Motor' in line and len(line) > 20 and len(line) < 200:
                data['name'] = line
                break

        # Parse volume discounts (pattern: "5 + $8.08")
        discount_pattern = re.compile(r'(\d+)\s*\+\s*\$([\d.]+)')
        for line in lines:
            matches = discount_pattern.findall(line)
            if matches:
                for qty, price in matches:
                    data['volume_discounts'].append({
                        'qty': int(qty),
                        'price': float(price)
                    })
                break

        # Extract key fields using regex on full text
        # SKU/Model
        sku_match = re.search(r'(?:Model|Part Number|Manufacturer Part Number)[:\s]*([A-Z0-9-]+)', text, re.I)
        if sku_match:
            data['sku'] = sku_match.group(1)

        # Price
        price_match = re.search(r'\$([\d.]+)', text)
        if price_match:
            data['price'] = float(price_match.group(1))

        # Stock
        stock_match = re.search(r'In Stock[:\s]*(\d+)', text, re.I)
        if stock_match:
            data['stock'] = int(stock_match.group(1))

        # Weight
        weight_match = re.search(r'(?:Gross Weight|Weight)[:\s]*([\d.]+)\s*(?:kg|g)', text, re.I)
        if weight_match:
            weight_val = float(weight_match.group(1))
            if weight_match.group(2) == 'g':
                weight_val = weight_val / 1000  # Convert to kg
            data['weight'] = weight_val

        # Certifications
        cert_match = re.search(r'Certificated[:\s]*([\w,\s]+?)(?=\s*(?:Click|Ships|$))', text, re.I)
        if cert_match:
            data['certifications'] = cert_match.group(1).strip()

        # Extract specifications
        # Electrical Specification section
        elec_match = re.search(r'Electrical Specification(.*?)(?:Physical Specification|$)', text, re.I | re.DOTALL)
        if elec_match:
            elec_text = elec_match.group(1)
            spec_pattern = re.compile(r'([A-Za-z\s/]+)[:\s]*([^\n]+)')
            for match in spec_pattern.findall(elec_text):
                key, value = match[0].strip(), match[1].strip()
                if key and value and len(key) < 50:
                    data['specifications'][key] = value

        # Physical Specification section
        phys_match = re.search(r'Physical Specification(.*?)(?:Connection|$)', text, re.I | re.DOTALL)
        if phys_match:
            phys_text = phys_match.group(1)
            for match in spec_pattern.findall(phys_text):
                key, value = match[0].strip(), match[1].strip()
                if key and value and len(key) < 50:
                    data['specifications'][key] = value

        # Description (after SPECIFICATIONS)
        desc_match = re.search(r'DESCRIPTION\s+(.{100,2000}?)(?:SPECIFICATIONS|DIMENSIONS|$)', text, re.DOTALL)
        if desc_match:
            data['description'] = desc_match.group(1).strip()

    except Exception as e:
        print(f"Parse error: {e}")

    return data

def crawl_product(browser, url, max_retries=3):
    """Crawl a single product page"""
    for attempt in range(max_retries):
        try:
            context = browser.contexts[0] if browser.contexts else None
            if not context:
                context = browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={'width': 1920, 'height': 1080}
                )

            page = context.new_page()

            try:
                page.goto(url, timeout=60000, wait_until='domcontentloaded')
                time.sleep(2)

                text = page.locator('body').inner_text()

                # Check for access denied
                if 'access denied' in text.lower():
                    print(f"  Blocked, attempt {attempt + 1}/{max_retries}")
                    page.close()
                    # Create new context to reset
                    if context in browser.contexts:
                        context.close()
                    context = browser.new_context(
                        user_agent=random.choice(USER_AGENTS),
                        viewport={'width': 1920, 'height': 1080}
                    )
                    time.sleep(random.uniform(2, 5))
                    continue

                # Parse product data
                data = parse_product_from_text(text, url)

                # Get images
                imgs = page.query_selector_all('img')
                for img in imgs:
                    src = img.get_attribute('src') or img.get_attribute('data-src') or ''
                    if src and ('image' in src.lower() or 'catalog' in src.lower()):
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = 'https://www.omc-stepperonline.com' + src
                        data['images'].append(src)

                # Deduplicate and limit images
                data['images'] = list(dict.fromkeys(data['images']))[:10]

                page.close()
                return data, None

            except Exception as e:
                page.close()
                print(f"  Error: {e}, attempt {attempt + 1}/{max_retries}")
                time.sleep(2)

        except Exception as e:
            print(f"  Context error: {e}")
            time.sleep(2)

    return None, "Failed after max retries"

def main():
    """Main crawling function"""
    print("=" * 60)
    print("OMC StepperOnline Batch Crawler (Playwright)")
    print("=" * 60)

    # Load URLs and crawled state
    product_urls = load_urls()
    crawled = load_crawled()

    if not product_urls:
        print("No product URLs found")
        return

    # Filter out already crawled
    remaining_urls = [url for url in product_urls if url not in crawled]
    print(f"Total URLs: {len(product_urls)}")
    print(f"Already crawled: {len(crawled)}")
    print(f"Remaining: {len(remaining_urls)}")

    # Load existing products
    existing_products = []
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            existing_products = json.load(f)
        print(f"Existing products loaded: {len(existing_products)}")

    # Start crawling
    print(f"\nStarting batch crawl of {min(BATCH_SIZE, len(remaining_urls))} products...")
    print("-" * 60)

    products = existing_products.copy()
    failed_urls = []

    with sync_playwright() as p:
        # Launch browser with anti-detection
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage']
        )

        # Create persistent context
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={'width': 1920, 'height': 1080}
        )

        # Remove webdriver detection
        context.add_init_script('''
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        ''')

        count = 0
        for url in remaining_urls[:BATCH_SIZE]:
            count += 1
            slug = url.split('/')[-1]
            print(f"[{count}/{min(BATCH_SIZE, len(remaining_urls))}] Crawling: {slug[:50]}...")

            product_data, error = crawl_product(browser, url)

            if product_data:
                products.append(product_data)
                crawled.append(url)
                print(f"  OK - {product_data.get('name', 'N/A')[:40]}")
            else:
                failed_urls.append(url)
                print(f"  FAILED - {error}")

            # Delay between requests
            if count < BATCH_SIZE:
                delay = REQUEST_DELAY + random.uniform(0, 2)
                time.sleep(delay)

        context.close()
        browser.close()

    # Save results
    save_products(products)
    print(f"\n" + "=" * 60)
    print(f"Crawl complete!")
    print(f"Products saved: {len(products)}")
    print(f"Failed: {len(failed_urls)}")
    print(f"Output: {OUTPUT_FILE}")

    # Update state
    state = {
        'product_urls': product_urls,
        'crawled': crawled
    }
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)

    print(f"State updated with {len(crawled)} crawled URLs")

if __name__ == "__main__":
    main()
