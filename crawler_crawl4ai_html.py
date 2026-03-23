#!/usr/bin/env python3
"""Crawl4AI batch crawler with HTML parsing"""

import sys
import io
import json
import re
from pathlib import Path
from crawl4ai import AsyncWebCrawler
import asyncio

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def parse_html(html, url):
    data = {
        'source_url': url, 'name': '', 'price': None, 'sku': '',
        'stock': None, 'weight': None, 'certifications': '',
        'brand': 'OMC-StepperOnline', 'description': '',
        'specifications': {}, 'images': [], 'volume_discounts': [], 'currency': 'USD'
    }

    if not html or len(html) < 1000:
        return None

    # Title
    title_match = re.search(r'<title>([^<]+)</title>', html)
    if title_match:
        title = title_match.group(1)
        data['name'] = re.sub(r'\s*\|\s*StepperOnline\s*$', '', title)

    # Price
    price_match = re.search(r'class="product-price"[^>]*>([^<]+)', html)
    if not price_match:
        price_match = re.search(r'\$([\d,]+\.?\d*)', html)
    if price_match:
        price_str = re.sub(r'[^\d.]', '', price_match.group(1))
        if price_str:
            try:
                data['price'] = float(price_str)
            except:
                pass

    # SKU
    sku_match = re.search(r'-\s*([A-Z0-9][A-Z0-9-]+)\s*\|', html)
    if not sku_match:
        sku_match = re.search(r'([A-Z0-9]{4,15})\s*</title>', html)
    if sku_match:
        data['sku'] = sku_match.group(1)

    # Stock
    stock_match = re.search(r'In Stock[:\s]*(\d+)', html, re.I)
    if stock_match:
        data['stock'] = int(stock_match.group(1))

    # Volume discounts
    for m in re.findall(r'(\d+)\s*\+\s*\$([\d.]+)', html):
        data['volume_discounts'].append({'qty': int(m[0]), 'price': float(m[1])})

    # Weight
    weight_match = re.search(r'(?:Gross )?Weight[:\s]*([\d.]+)\s*(kg|g)', html, re.I)
    if weight_match:
        val = float(weight_match.group(1))
        if weight_match.group(2).lower() == 'g':
            val = val / 1000
        data['weight'] = val

    # Description from meta
    desc_match = re.search(r'name="description"[^>]+content="([^"]+)"', html)
    if desc_match:
        data['description'] = desc_match.group(1)

    return data if data.get('name') or data.get('price') else None

async def main():
    print('=' * 60)
    print('Crawl4AI Batch Crawler (HTML)')
    print('=' * 60)

    OUTPUT_FILE = Path('d:/stepperonline_crawler_data/products_crawl4ai.json')
    urls_file = Path('d:/stepperonline_crawler_data/product_urls.txt')
    state_file = Path('d:/stepperonline_crawler_data/crawler_state.json')

    with open(urls_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip().startswith('http')]

    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    crawled = state.get('crawled', [])

    remaining = [u for u in urls if u not in crawled]
    print(f'Total: {len(urls)}, Crawled: {len(crawled)}, Remaining: {len(remaining)}')

    existing = []
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        print(f'Loaded: {len(existing)} existing')

    products = existing.copy()
    BATCH_SIZE = 50

    print(f'\nCrawling {min(BATCH_SIZE, len(remaining))} products...')

    async with AsyncWebCrawler(verbose=False) as crawler:
        for i, url in enumerate(remaining[:BATCH_SIZE]):
            try:
                result = await crawler.arun(url=url)
                if result.success and result.html:
                    data = parse_html(result.html, url)
                    if data:
                        products.append(data)
                        crawled.append(url)
                        print(f'[{i+1}] OK - {data.get("sku", "N/A")[:15]} | ${data.get("price", 0)}')
                    else:
                        print(f'[{i+1}] PARSE FAIL')
                else:
                    print(f'[{i+1}] FAIL')
            except Exception as e:
                print(f'[{i+1}] ERROR: {str(e)[:50]}')
            await asyncio.sleep(0.5)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump({'product_urls': urls, 'crawled': crawled}, f, indent=2)

    print(f'\n' + '=' * 60)
    print(f'Done! New: {len(products) - len(existing)}, Total: {len(products)}')
    print('=' * 60)

if __name__ == '__main__':
    asyncio.run(main())
