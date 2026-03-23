"""
Proxy-based Product Crawler for omc-stepperonline.com
Uses rotating proxies to bypass IP blocks
"""

import json
import time
import random
import requests
from urllib.parse import urlparse
import os

# Configuration
DATA_DIR = 'd:/stepperonline_crawler_data/products_full'
PROGRESS_FILE = 'd:/stepperonline_crawler_data/crawl_progress.json'
STATE_FILE = 'd:/stepperonline_crawler_data/crawler_state.json'

# Target
TARGET_HOST = 'www.omc-stepperonline.com'

# User agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36',
]

# Free proxy sources
PROXY_SOURCES = [
    'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
    'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt',
    'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt',
]

def load_state():
    """Load crawler state"""
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {'discovered_products': []}

def get_products():
    """Get list of products to crawl"""
    state = load_state()
    return state.get('discovered_products', [])

def load_progress():
    """Load crawl progress"""
    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {'completed': 0, 'success': 0, 'failed': 0}

def save_progress(progress):
    """Save crawl progress"""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2)

def fetch_proxies():
    """Fetch fresh proxy list"""
    proxies = []
    for source in PROXY_SOURCES:
        try:
            resp = requests.get(source, timeout=10)
            if resp.status_code == 200:
                for line in resp.text.split('\n'):
                    line = line.strip()
                    if ':' in line:
                        proxies.append(f'http://{line}')
        except:
            pass
    return proxies

def test_proxy(proxy):
    """Test if proxy works"""
    try:
        resp = requests.get(
            'http://httpbin.org/ip',
            proxies={'http': proxy, 'https': proxy},
            timeout=5
        )
        return resp.status_code == 200
    except:
        return False

def crawl_product(url, proxy=None):
    """Crawl a single product"""
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    proxies = {'http': proxy, 'https': proxy} if proxy else None

    try:
        resp = requests.get(url, headers=headers, proxies=proxies, timeout=30)

        if resp.status_code == 403:
            return None, '403 Forbidden'

        if resp.status_code != 200:
            return None, f'HTTP {resp.status_code}'

        return parse_product_html(resp.text, url), None

    except Exception as e:
        return None, str(e)

def parse_product_html(html, url):
    """Parse product data from HTML"""
    data = {
        'url': url,
        'name': '',
        'sku': '',
        'price': '',
        'description': '',
        'specifications': {},
        'images': [],
        'downloads': []
    }

    import re

    # Extract title
    match = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
    if match:
        data['name'] = clean_text(match.group(1))

    # Extract SKU
    match = re.search(r'SKU[:\s]*([A-Z0-9-]+)', html, re.I)
    if match:
        data['sku'] = match.group(1)

    # Extract price
    match = re.search(r'\$[\d,]+\.?\d*', html)
    if match:
        data['price'] = match.group(0)

    # Extract description
    match = re.search(r'description[\s\S]{0,500}?<p>([\s\S]*?)</p>', html, re.I)
    if match:
        data['description'] = clean_text(match.group(1))

    # Extract images
    img_pattern = r'https://www\.omc-stepperonline\.com/image/cache/[^\s"\'<>]+(?:-500x500|-250x250)[^\s"\'<>]*'
    for match in re.finditer(img_pattern, html):
        img_url = match.group(0)
        if '/23menu/' not in img_url and 'logo-' not in img_url:
            if img_url not in data['images']:
                data['images'].append(img_url)

    # Extract specifications
    spec_pattern = r'<td[^>]*>\s*([^<]+)\s*</td>\s*<td[^>]*>\s*([^<]+)\s*</td>'
    for match in re.finditer(spec_pattern, html):
        key = clean_text(match.group(1))
        value = clean_text(match.group(2))
        if key and value and len(key) < 100 and len(value) < 500:
            data['specifications'][key] = value

    return data

def clean_text(text):
    """Clean HTML from text"""
    import re
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def main():
    print('=' * 50)
    print('Proxy-based Product Crawler')
    print('=' * 50)

    # Ensure output directory
    os.makedirs(DATA_DIR, exist_ok=True)

    # Get products
    products = get_products()
    print(f'Total products to crawl: {len(products)}')

    # Get progress
    progress = load_progress()
    start_idx = progress.get('completed', 0)
    success_count = progress.get('success', 0)
    fail_count = progress.get('failed', 0)

    # Get existing files
    existing = set()
    for f in os.listdir(DATA_DIR):
        if f.endswith('.json'):
            slug = f.replace('.json', '')
            existing.add(slug)

    # Filter products to crawl
    to_crawl = []
    for url in products[start_idx:]:
        slug = urlparse(url).path.split('/')[-1]
        if slug not in existing:
            to_crawl.append((url, slug))

    print(f'Already done: {start_idx}')
    print(f'Already crawled: {len(existing)}')
    print(f'Reamining: {len(to_crawl)}')

    if not to_crawl:
        print('All products already crawled!')
        return

    # Fetch proxies
    print('\nFetching proxy list...')
    proxies = fetch_proxies()
    print(f'Found {len(proxies)} proxies')

    if not proxies:
        print('No proxies available!')
        return

    # Test first 10 proxies
    working_proxies = []
    for p in proxies[:10]:
        print(f'Testing {p}...', end=' ')
        if test_proxy(p):
            print('OK')
            working_proxies.append(p)
        else:
            print('FAIL')

    if not working_proxies:
        print('No working proxies!')
        return

    print(f'\nWorking proxies: {len(working_proxies)}')

    # Crawl
    delay = 3  # seconds between requests

    for i, (url, slug) in enumerate(to_crawl):
        proxy = random.choice(working_proxies)
        print(f'[{start_idx + i + 1}/{len(to_crawl)}] {slug[:40]}... ', end='')

        data, error = crawl_product(url, proxy)

        if data and data.get('specifications'):
            out_path = os.path.join(DATA_DIR, f'{slug}.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f'OK ({len(data["specifications"])} specs)')
            success_count += 1
        else:
            print(f'FAIL: {error}')
            fail_count += 1

        progress['completed'] = start_idx + i + 1
        progress['success'] = success_count
        progress['failed'] = fail_count
        save_progress(progress)

        # Delay
        time.sleep(delay)

        # Refresh proxies periodically
        if (i + 1) % 20 == 0:
            print('\nRefreshing proxies...')
            proxies = fetch_proxies()
            working_proxies = []
            for p in proxies[:10]:
                if test_proxy(p):
                    working_proxies.append(p)
            print(f'Working: {len(working_proxies)}')

    print('\n' + '=' * 50)
    print('Crawl Complete!')
    print(f'Success: {success_count}')
    print(f'Failed: {fail_count}')
    print('=' * 50)

if __name__ == '__main__':
    main()
