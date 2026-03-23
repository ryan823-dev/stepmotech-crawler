#!/usr/bin/env python3
"""简化的爬取工具 - 命令行模式"""

import sys
import io
import os
import json
import time
from pathlib import Path
from datetime import datetime
import subprocess
import re
import urllib.request
import urllib.error

# UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 配置
APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = APP_DIR / "config.json"

class CrawlerTool:
    def __init__(self):
        self.load_config()
        self.stats = {"crawled": 0, "uploaded": 0, "failed": 0}

    def load_config(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "supabase": {
                    "url": "https://qwcwkfavkrevxonnfkrw.supabase.co",
                    "anon_key": "sb_publishable_qqy39AdcMbtNNzhgiD404A_RrjpVI1v"
                }
            }

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        print(line)
        log_file = DATA_DIR / "crawler.log"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line + "/n")

    def get_product_urls(self):
        urls = []
        consolidated = Path("d:/stepperonline_crawler_data/consolidated/complete_data.json")
        if consolidated.exists():
            with open(consolidated, 'r', encoding='utf-8') as f:
                products = json.load(f)
                for p in products:
                    urls.append(f"https://www.omc-stepperonline.com/{p['slug']}")
        return list(set(urls))[:500]

    def crawl_with_curl(self, url):
        try:
            cmd = ['curl', '-s', '-L', '-A',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                '-H', 'Accept: text/html', url, '--max-time', '30']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
            if result.returncode == 0 and len(result.stdout) > 1000:
                html = result.stdout
                data = {'url': url, 'name': '', 'price': 0, 'sku': '', 'specs': {}}
                title = re.search(r'<title>([^<]+)</title>', html)
                if title:
                    data['name'] = re.sub(r'/s*/|/s*StepperOnline/s*$', '', title.group(1))
                sku = re.search(r'<li>Model:/s*([^<]+)</li>', html)
                if sku:
                    data['sku'] = sku.group(1).strip()
                price = re.search(r'/$([/d,]+/.?/d*)', html)
                if price:
                    try:
                        data['price'] = float(re.sub(r'[^/d.]', '', price.group(1)))
                    except: pass
                return data if data.get('name') or data.get('sku') else None
        except: pass
        return None

    def categorize(self, data):
        name = (data.get('name', '') + data.get('sku', '')).lower()
        if 'nema 8' in name: return 'stepper-motors-nema-8'
        if 'nema 11' in name: return 'stepper-motors-nema-11'
        if 'nema 14' in name: return 'stepper-motors-nema-14'
        if 'nema 17' in name: return 'stepper-motors-nema-17'
        if 'nema 23' in name: return 'stepper-motors-nema-23'
        if 'nema 24' in name: return 'stepper-motors-nema-24'
        if 'nema 34' in name: return 'stepper-motors-nema-34'
        if 'servo' in name: return 'servo-motors'
        if 'linear' in name: return 'linear-actuators'
        if 'gearbox' in name: return 'gearboxes'
        if 'driver' in name: return 'drivers'
        return 'accessories'

    def upload_to_supabase(self, data):
        category = self.categorize(data)
        slug = data.get('sku', data['url'].split('/')[-1][:50])
        product = {
            'name': data.get('name', slug),
            'slug': slug,
            'sku': data.get('sku', slug),
            'price': data.get('price', 0),
            'category': category,
            'specifications': data.get('specs', {}),
            'status': 'active',
            'updated_at': datetime.now().isoformat()
        }
        headers = {
            'apikey': self.config['supabase']['anon_key'],
            'Authorization': f"Bearer {self.config['supabase']['anon_key']}",
            'Content-Type': 'application/json',
        }
        try:
            # 检查是否存在
            check_url = f"{self.config['supabase']['url']}/rest/v1/products?slug=eq.{slug}&select=id"
            req = urllib.request.Request(check_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if json.loads(resp.read()):
                    return True
            # 插入
            insert_url = f"{self.config['supabase']['url']}/rest/v1/products"
            req = urllib.request.Request(insert_url, data=json.dumps(product).encode(), headers=headers, method='POST')
            urllib.request.urlopen(req, timeout=15)
            return True
        except: pass
        return False

    def run(self):
        print("=" * 60)
        print("StepperOnline Crawler v2")
        print("=" * 60)
        self.log("Starting...")
        urls = self.get_product_urls()
        self.log(f"URLs to process: {len(urls)}")
        processed_file = DATA_DIR / "products.json"
        if processed_file.exists():
            with open(processed_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            processed = {p['url'] for p in existing}
            urls = [u for u in urls if u not in processed]
        self.log(f"New URLs: {len(urls)}")
        if not urls:
            self.log("No new URLs")
            return
        success, fail = 0, 0
        for i, url in enumerate(urls):
            self.log(f"[{i+1}/{len(urls)}] {url[:50]}...")
            data = self.crawl_with_curl(url)
            if data and self.upload_to_supabase(data):
                success += 1
                self.log(f"  OK: {data.get('sku','')[:30]}")
            else:
                fail += 1
                self.log(f"  FAIL")
            if (i + 1) % 20 == 0:
                self.log(f"Progress: {i+1}/{len(urls)} OK:{success} FAIL:{fail}")
            time.sleep(1.5)
        self.log("=" * 60)
        self.log(f"DONE! OK:{success} FAIL:{fail}")
        self.log("=" * 60)

if __name__ == "__main__":
    tool = CrawlerTool()
    tool.run()
