#!/usr/bin/env python3
"""Crawl4AI batch crawler"""

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
    title = re.search(r'<title>([^<]+)</title>', html)
    if title:
        data['name'] = re.sub(r'\s*\|\s*StepperOnline\s*$', '', title.group(1))
    price = re.search(r'class="product-price"[^>]*>([^<]+)', html)
    if not price:
        price = re.search(r'\$([\d,]+\.?\d*)', html)
    if price:
        try:
            data['price'] = float(re.sub(r'[^\d.]', '', price.group(1)))
        except: pass
    sku = re.search(r'- ([A-Z0-9][A-Z0-9-]+) \|', html)
    if sku: data['sku'] = sku.group(1)
    stock = re.search(r'In Stock[:\s]*(\d+)', html, re.I)
    if stock: data['stock'] = int(stock.group(1))
    for m in re.findall(r'(\d+)\s*\+\s*\$([\d.]+)', html):
        data['volume_discounts'].append({'qty': int(m[0]), 'price': float(m[1])})
    return data if data.get('name') or data.get('price') else None

async def main():
    print('=' * 50)
    print('Crawl4AI Batch Crawler')
    print('=' * 50)
    OUTPUT = Path('d:/stepperonline_crawler_data/products_crawl4ai.json')
    with open(Path('d:/stepperonline_crawler_data/product_urls.txt'), 'r') as f:
        urls = [u.strip() for u in f if u.strip().startswith('http')]
    with open(Path('d:/stepperonline_crawler_data/crawler_state.json'), 'r') as f:
        state = json.load(f)
    crawled = state.get('crawled', [])
    remaining = [u for u in urls if u not in crawled]
    print(f'Total: {len(urls)}, Crawled: {len(crawled)}, Remaining: {len(remaining)}')
    existing = json.load(open(OUTPUT, 'r')) if OUTPUT.exists() else []
    products = existing.copy()
    print(f'Crawling {min(30, len(remaining))} products...')
    async with AsyncWebCrawler(verbose=False) as crawler:
        for i, url in enumerate(remaining[:30]):
            try:
                result = await crawler.arun(url=url)
                if result.success and result.html:
                    data = parse_html(result.html, url)
                    if data:
                        products.append(data)
                        crawled.append(url)
                        print(f'[{i+1}] OK {data.get("sku","?")[:12]} ${data.get("price",0)}')
                    else: print(f'[{i+1}] PARSE FAIL')
                else: print(f'[{i+1}] FAIL')
            except Exception as e:
                print(f'[{i+1}] ERROR: {str(e)[:40]}')
            await asyncio.sleep(0.5)
    json.dump(products, open(OUTPUT, 'w'))
    json.dump({'product_urls': urls, 'crawled': crawled}, open(Path('d:/stepperonline_crawler_data/crawler_state.json'), 'w'))
    print(f'Done! Total: {len(products)}')

if __name__ == '__main__':
    asyncio.run(main())
