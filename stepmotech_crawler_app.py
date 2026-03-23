#!/usr/bin/env python3
"""
StepperOnline数据爬取与上架工具
Stepmotech自动化工作流
"""

import sys
import io
import os
import json
import re
import time
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, unquote
import subprocess
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import threading
import asyncio

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 尝试导入tkinter（用于GUI）
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False
    print("Warning: tkinter not available, running in headless mode")

# 配置路径
APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
CONFIG_FILE = APP_DIR / "config.json"
LOG_FILE = APP_DIR / "stepmotech_crawler.log"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)

@dataclass
class Product:
    """产品数据模型"""
    slug: str
    name: str
    sku: str
    price: float
    category: str
    subcategory: str
    specifications: Dict[str, str]
    images: List[str]
    pdfs: List[str]
    description: str
    stock: int
    certifications: str
    weight: str
    brand: str = "OMC-StepperOnline"
    source_url: str = ""
    status: str = "pending"  # pending, crawled, processed, uploaded

@dataclass
class CrawlProgress:
    """爬取进度"""
    total_urls: int = 0
    crawled: int = 0
    processed: int = 0
    uploaded: int = 0
    failed: int = 0
    start_time: datetime = None
    current_url: str = ""

class Config:
    """配置管理"""
    def __init__(self):
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            self.data = self._default_config()
            self.save()

    def _default_config(self):
        return {
            "supabase": {
                "url": "https://qwcwkfavkrevxonnfkrw.supabase.co",
                "anon_key": "sb_publishable_qqy39AdcMbtNNzhgiD404A_RrjpVI1x",
                "service_key": ""
            },
            "crawl": {
                "max_products": 500,
                "delay": 1.0,
                "retry": 3,
                "batch_size": 50
            },
            "source": {
                "base_url": "https://www.omc-stepperonline.com",
                "categories": [
                    "stepper-motors",
                    "servo-motors",
                    "linear-actuators",
                    "gearboxes",
                    "drivers",
                    "accessories"
                ]
            },
            "output": {
                "save_images": True,
                "save_pdfs": True,
                "images_dir": str(DATA_DIR / "images"),
                "pdfs_dir": str(DATA_DIR / "pdfs")
            }
        }

    def save(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        keys = key.split('.')
        val = self.data
        for k in keys:
            val = val.get(k, default)
        return val

    def set(self, key, value):
        keys = key.split('.')
        d = self.data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value

class Logger:
    """日志管理"""
    def __init__(self, log_file=None):
        self.log_file = log_file or LOG_FILE
        self.handlers = []

        # 设置根日志
        self.logger = logging.getLogger('stepmotech')
        self.logger.setLevel(logging.DEBUG)

        # 文件处理器
        fh = logging.FileHandler(self.log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        # 控制台处理器
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def debug(self, msg):
        self.logger.debug(msg)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def callback(self, msg):
        """GUI回调"""
        pass

logger = Logger()

class SupabaseUploader:
    """Supabase数据上传"""
    def __init__(self, config: Config):
        self.config = config
        self.url = config.get('supabase.url')
        self.anon_key = config.get('supabase.anon_key')
        self.service_key = config.get('supabase.service_key')

    def upload_product(self, product: Product) -> bool:
        """上传单个产品"""
        try:
            # 构建产品数据
            product_data = {
                'name': product.name,
                'slug': product.slug,
                'sku': product.sku,
                'price': product.price,
                'category': product.category,
                'subcategory': product.subcategory,
                'specifications': product.specifications,
                'description': product.description,
                'stock': product.stock,
                'certifications': product.certifications,
                'weight': product.weight,
                'brand': product.brand,
                'images': product.images[:5],  # 限制图片数量
                'status': 'active',
                'updated_at': datetime.now().isoformat()
            }

            # 使用supabase CLI或直接HTTP请求
            # 这里使用简化的直接请求方式
            headers = {
                'apikey': self.anon_key,
                'Authorization': f'Bearer {self.anon_key}',
                'Content-Type': 'application/json',
                'Prefer': 'return=representation'
            }

            import urllib.request
            import urllib.error

            # 检查是否已存在
            check_url = f"{self.url}/rest/v1/products?slug=eq.{product.slug}&select=id"
            req = urllib.request.Request(check_url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    existing = json.loads(resp.read())
                    if existing:
                        # 更新
                        update_url = f"{self.url}/rest/v1/products?slug=eq.{product.slug}"
                        req = urllib.request.Request(
                            update_url,
                            data=json.dumps(product_data).encode(),
                            headers={**headers, 'Prefer': 'return=minimal', 'X-HTTP-Method': 'PATCH'},
                            method='PATCH'
                        )
                        urllib.request.urlopen(req, timeout=10)
                        logger.info(f"Updated product: {product.slug}")
                        return True
            except Exception as e:
                pass

            # 插入新产品
            insert_url = f"{self.url}/rest/v1/products"
            req = urllib.request.Request(
                insert_url,
                data=json.dumps(product_data).encode(),
                headers={**headers, 'Prefer': 'return=representation'},
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                logger.info(f"Uploaded: {product.slug}")
                return True

        except Exception as e:
            logger.error(f"Upload failed for {product.slug}: {e}")
            return False

class Crawl4AIClient:
    """Crawl4AI爬取客户端"""
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.get('source.base_url')

    async def crawl_product(self, url: str) -> Optional[Dict]:
        """爬取单个产品页面"""
        try:
            # 使用crawl4ai
            from crawl4ai import AsyncWebCrawler

            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.araw(url)

                if result.success:
                    return self._parse_html(result.html, url)
                else:
                    logger.warning(f"Crawl failed: {url}")
                    return None

        except ImportError:
            # 备用：使用curl
            return await self._crawl_with_curl(url)
        except Exception as e:
            logger.error(f"Crawl error for {url}: {e}")
            return None

    async def _crawl_with_curl(self, url: str) -> Optional[Dict]:
        """使用curl备用爬取"""
        try:
            headers = [
                'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language: en-US,en;q=0.9',
            ]

            cmd = ['curl', '-s', '-L', '-A', headers[0], '-H', headers[1], url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout:
                return self._parse_html(result.stdout, url)

        except Exception as e:
            logger.error(f"Curl crawl failed: {e}")

        return None

    def _parse_html(self, html: str, url: str) -> Dict:
        """解析HTML提取产品数据"""
        data = {
            'source_url': url,
            'name': '',
            'price': 0,
            'sku': '',
            'stock': 0,
            'weight': '',
            'certifications': '',
            'description': '',
            'specifications': {},
            'images': [],
            'pdfs': []
        }

        # 提取标题
        title = re.search(r'<title>([^<]+)</title>', html)
        if title:
            data['name'] = re.sub(r'\s*\|\s*StepperOnline\s*$', '', title.group(1))

        # 提取SKU
        sku_match = re.search(r'<li>Model:\s*([^<]+)</li>', html)
        if sku_match:
            data['sku'] = sku_match.group(1).strip()

        # 提取价格
        price_match = re.search(r'class="product-price"[^>]*>([^<]+)', html)
        if not price_match:
            price_match = re.search(r'\$([\d,]+\.?\d*)', html)

        if price_match:
            try:
                data['price'] = float(re.sub(r'[^\d.]', '', price_match.group(1)))
            except:
                pass

        # 提取规格
        lis = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)
        skip_keys = ['About Us', 'Contact', 'FAQ', 'Shipping', 'Returns']
        for li in lis:
            clean = re.sub(r'<[^>]+>', '', li).strip()
            if ':' in clean and 3 < len(clean) < 150:
                parts = clean.split(':', 1)
                key = parts[0].strip()
                val = parts[1].strip()
                if key and val and key not in skip_keys:
                    data['specifications'][key] = val

        # 提取图片
        for pattern in [r'data-image="([^"]+)"', r'<img[^>]+src="([^"]+catalog[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"']:
            for m in re.findall(pattern, html, re.IGNORECASE):
                if 'logo' not in m.lower() and 'menu' not in m.lower():
                    if m.startswith('/'):
                        m = self.base_url + m
                    if m not in data['images']:
                        data['images'].append(m)

        # 提取PDF
        for m in re.findall(r'href="([^"]+\.pdf[^"]*)"', html, re.IGNORECASE):
            if m.startswith('/'):
                m = self.base_url + m
            data['pdfs'].append(m)

        # 提取库存
        stock_match = re.search(r'<li>In Stock:\s*(\d+)</li>', html)
        if stock_match:
            data['stock'] = int(stock_match.group(1))

        # 提取认证
        cert_match = re.search(r'<li>Certificated:\s*([^<]+)</li>', html)
        if cert_match:
            data['certifications'] = cert_match.group(1)

        # 提取重量
        weight_match = re.search(r'<li>Gross Weight:\s*([^<]+)</li>', html)
        if weight_match:
            data['weight'] = weight_match.group(1)

        return data

    def get_product_urls(self) -> List[str]:
        """获取所有产品URL"""
        urls = []

        # 从已保存的数据中获取URL
        products_file = DATA_DIR / "products.json"
        if products_file.exists():
            with open(products_file, 'r', encoding='utf-8') as f:
                products = json.load(f)
                for p in products:
                    if 'source_url' in p:
                        urls.append(p['source_url'])

        # 如果没有，从sitemap获取
        if not urls:
            sitemap_url = f"{self.base_url}/sitemap.xml"
            try:
                result = subprocess.run(['curl', '-s', sitemap_url], capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    urls = re.findall(r'<loc>([^<]+/product/[^<]+)</loc>', result.stdout)
                    logger.info(f"Found {len(urls)} product URLs from sitemap")
            except:
                pass

        return urls

class DataProcessor:
    """数据处理器"""
    def __init__(self, config: Config):
        self.config = config

    def categorize(self, product_data: Dict) -> tuple:
        """分类产品"""
        slug = product_data.get('source_url', '').lower()
        name = product_data.get('name', '').lower()
        specs = product_data.get('specifications', {})
        frame_size = specs.get('Frame Size', '').lower()

        category = 'accessories'
        subcategory = 'other'

        # NEMA步进电机
        if 'nema 8' in slug or '8mm' in frame_size:
            category = 'stepper-motors'
            subcategory = 'nema-8'
        elif 'nema 11' in slug or '11mm' in frame_size:
            category = 'stepper-motors'
            subcategory = 'nema-11'
        elif 'nema 14' in slug or '14mm' in frame_size:
            category = 'stepper-motors'
            subcategory = 'nema-14'
        elif 'nema 17' in slug or '17mm' in frame_size or '42' in frame_size:
            category = 'stepper-motors'
            subcategory = 'nema-17'
        elif 'nema 23' in slug or '23mm' in frame_size or '57' in frame_size:
            category = 'stepper-motors'
            subcategory = 'nema-23'
        elif 'nema 24' in slug or '24mm' in frame_size:
            category = 'stepper-motors'
            subcategory = 'nema-24'
        elif 'nema 34' in slug or '34mm' in frame_size or '86' in frame_size:
            category = 'stepper-motors'
            subcategory = 'nema-34'

        # 伺服电机
        elif 'servo' in slug or 'a6' in slug:
            category = 'servo-motors'
            subcategory = 'ac-servo-kits'

        # 线性执行器
        elif 'linear' in slug or 'actuator' in slug or 'ball screw' in slug:
            category = 'linear-actuators'
            subcategory = 'ball-screw' if 'ball' in slug else 'linear'

        # 减速箱
        elif 'gearbox' in slug or 'planetary' in slug or 'gear ratio' in slug:
            category = 'gearboxes'
            subcategory = 'planetary'

        # 驱动器
        elif 'driver' in slug or 'dm' in slug or 'drive' in slug:
            category = 'drivers'
            subcategory = 'stepper-drivers'

        # 配件
        elif 'cable' in slug or 'coupling' in slug or 'bracket' in slug:
            category = 'accessories'
            subcategory = 'cables' if 'cable' in slug else 'mounts'

        return category, subcategory

    def generate_slug(self, name: str, sku: str) -> str:
        """生成URL友好的slug"""
        # 使用SKU或名称生成slug
        base = sku or name
        slug = base.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = re.sub(r'^-+|-+$', '', slug)
        return slug[:100]

    def process(self, crawled_data: Dict) -> Optional[Product]:
        """处理爬取的数据"""
        if not crawled_data.get('name') and not crawled_data.get('sku'):
            return None

        category, subcategory = self.categorize(crawled_data)
        slug = crawled_data.get('sku', '') or self.generate_slug(
            crawled_data.get('name', ''),
            crawled_data.get('sku', '')
        )

        return Product(
            slug=slug,
            name=crawled_data.get('name', slug),
            sku=crawled_data.get('sku', slug),
            price=crawled_data.get('price', 0),
            category=category,
            subcategory=subcategory,
            specifications=crawled_data.get('specifications', {}),
            images=crawled_data.get('images', []),
            pdfs=crawled_data.get('pdfs', []),
            description=crawled_data.get('description', ''),
            stock=crawled_data.get('stock', 0),
            certifications=crawled_data.get('certifications', ''),
            weight=crawled_data.get('weight', ''),
            source_url=crawled_data.get('source_url', '')
        )

class Workflow:
    """自动化工作流"""
    def __init__(self, config: Config, progress_callback=None):
        self.config = config
        self.crawler = Crawl4AIClient(config)
        self.processor = DataProcessor(config)
        self.uploader = SupabaseUploader(config)
        self.progress = CrawlProgress()
        self.progress_callback = progress_callback
        self.running = False
        self.paused = False

    def log(self, msg):
        """记录日志"""
        logger.info(msg)
        if self.progress_callback:
            self.progress_callback(msg)

    def save_state(self):
        """保存工作状态"""
        state = {
            'progress': asdict(self.progress),
            'timestamp': datetime.now().isoformat()
        }
        with open(DATA_DIR / "workflow_state.json", 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

        # 保存已处理的产品
        products_file = DATA_DIR / "products.json"
        if products_file.exists():
            with open(products_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        else:
            existing = []

        with open(products_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2)

    async def run(self):
        """运行工作流"""
        self.running = True
        self.progress.start_time = datetime.now()

        self.log("=" * 60)
        self.log("StepperOnline 数据爬取与上架工作流")
        self.log("=" * 60)

        # 1. 获取产品URL
        self.log("\n[1/5] 获取产品URL列表...")
        urls = self.crawler.get_product_urls()

        if not urls:
            self.log("未找到产品URL，尝试从类别页面获取...")
            # 备用：使用已知的URL列表
            urls = self._get_default_urls()

        self.progress.total_urls = len(urls)
        self.log(f"找到 {len(urls)} 个产品URL")

        # 加载已处理的产品
        processed_urls = set()
        products_file = DATA_DIR / "products.json"
        if products_file.exists():
            with open(products_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                processed_urls = {p.get('source_url') for p in existing if p.get('source_url')}

        # 过滤未处理的URL
        urls = [u for u in urls if u not in processed_urls]
        self.log(f"待处理: {len(urls)} 个产品")

        # 2. 爬取数据
        self.log("\n[2/5] 开始爬取数据...")
        crawled_data = []

        for i, url in enumerate(urls):
            if not self.running:
                break

            while self.paused:
                await asyncio.sleep(1)

            self.progress.current_url = url
            self.log(f"[{i+1}/{len(urls)}] 爬取: {url[:60]}...")

            data = await self.crawler.crawl_product(url)
            if data:
                crawled_data.append(data)
                self.progress.crawled += 1
            else:
                self.progress.failed += 1

            # 每10个保存一次状态
            if (i + 1) % 10 == 0:
                self.save_state()

        self.log(f"爬取完成: {self.progress.crawled} 成功, {self.progress.failed} 失败")

        # 3. 处理数据
        self.log("\n[3/5] 处理数据...")
        products = []

        for data in crawled_data:
            product = self.processor.process(data)
            if product:
                products.append(product)
                self.progress.processed += 1

        self.log(f"处理完成: {len(products)} 个有效产品")

        # 4. 上架
        self.log("\n[4/5] 上架到Supabase...")

        for i, product in enumerate(products):
            if not self.running:
                break

            self.log(f"[{i+1}/{len(products)}] 上架: {product.sku}")

            if self.uploader.upload_product(product):
                self.progress.uploaded += 1
            else:
                self.log(f"  上架失败: {product.sku}")

        self.log(f"上架完成: {self.progress.uploaded} 成功")

        # 5. 下载资源
        self.log("\n[5/5] 下载资源文件...")

        if self.config.get('output.save_images'):
            self._download_images(products)

        if self.config.get('output.save_pdfs'):
            self._download_pdfs(products)

        # 保存最终状态
        self.save_state()

        self.log("\n" + "=" * 60)
        self.log("工作流执行完成!")
        self.log("=" * 60)
        self.log(f"总产品: {self.progress.total_urls}")
        self.log(f"爬取成功: {self.progress.crawled}")
        self.log(f"处理成功: {self.progress.processed}")
        self.log(f"上架成功: {self.progress.uploaded}")
        self.log(f"失败: {self.progress.failed}")

        self.running = False

    def _download_images(self, products):
        """下载产品图片"""
        images_dir = Path(self.config.get('output.images_dir'))
        images_dir.mkdir(exist_ok=True)

        downloaded = 0
        for product in products:
            product_dir = images_dir / product.slug
            product_dir.mkdir(exist_ok=True)

            for img_url in product.images[:5]:
                filename = unquote(urlparse(img_url).path.split('/')[-1])
                if not filename or '.' not in filename:
                    filename = f"{hashlib.md5(img_url.encode()).hexdigest()[:8]}.jpg"

                output_path = product_dir / filename
                if not output_path.exists():
                    try:
                        subprocess.run([
                            'curl', '-s', '-L', '-o', str(output_path),
                            '-H', 'User-Agent: Mozilla/5.0',
                            '-H', f'Referer: {self.config.get("source.base_url")}/',
                            img_url
                        ], timeout=30)
                        downloaded += 1
                    except:
                        pass

        self.log(f"下载图片: {downloaded} 张")

    def _download_pdfs(self, products):
        """下载PDF文档"""
        pdfs_dir = Path(self.config.get('output.pdfs_dir'))
        pdfs_dir.mkdir(exist_ok=True)

        downloaded = 0
        for product in products:
            for pdf_url in product.pdfs:
                url = pdf_url.replace('&amp;', '&')
                filename = url.split('/')[-1].split('&')[0]
                if not filename.endswith('.pdf'):
                    filename = f"{product.sku}.pdf"

                output_path = pdfs_dir / filename
                if not output_path.exists():
                    try:
                        subprocess.run([
                            'curl', '-s', '-L', '-o', str(output_path),
                            '-H', 'User-Agent: Mozilla/5.0',
                            '-H', f'Referer: {self.config.get("source.base_url")}/',
                            url
                        ], timeout=60)
                        if output_path.exists() and output_path.stat().st_size > 1000:
                            downloaded += 1
                    except:
                        pass

        self.log(f"下载PDF: {downloaded} 份")

    def _get_default_urls(self) -> List[str]:
        """获取默认URL列表（从已保存数据）"""
        urls = []

        # 从consolidated目录读取
        consolidated = Path("d:/stepperonline_crawler_data/consolidated/complete_data.json")
        if consolidated.exists():
            with open(consolidated, 'r', encoding='utf-8') as f:
                products = json.load(f)
                for p in products:
                    urls.append(f"https://www.omc-stepperonline.com/{p['slug']}")

        return urls[:self.config.get('crawl.max_products', 500)]

    def stop(self):
        """停止工作流"""
        self.running = False
        self.log("正在停止...")

    def pause(self):
        """暂停工作流"""
        self.paused = not self.paused
        return self.paused

def main():
    """主函数"""
    config = Config()

    if HAS_TKINTER:
        # GUI模式
        class App:
            def __init__(self, root):
                self.root = root
                self.root.title("StepperOnline 数据爬取工具 v1.0")
                self.root.geometry("800x600")

                self.workflow = None
                self.thread = None

                self._create_widgets()

            def _create_widgets(self):
                # 标题
                title = tk.Label(self.root, text="StepperOnline 数据爬取与上架", font=("Arial", 16))
                title.pack(pady=10)

                # 状态显示
                self.status_label = tk.Label(self.root, text="状态: 等待开始", fg="blue")
                self.status_label.pack()

                # 进度条
                self.progress = ttk.Progressbar(self.root, length=600, mode='determinate')
                self.progress.pack(pady=10)

                # 日志窗口
                self.log_text = scrolledtext.ScrolledText(self.root, height=25, width=95)
                self.log_text.pack(pady=10)

                # 按钮
                btn_frame = tk.Frame(self.root)
                btn_frame.pack(pady=10)

                self.start_btn = tk.Button(btn_frame, text="开始运行", command=self.start, width=15, bg="green", fg="white")
                self.start_btn.pack(side=tk.LEFT, padx=5)

                self.pause_btn = tk.Button(btn_frame, text="暂停/继续", command=self.pause, width=15, state=tk.DISABLED)
                self.pause_btn.pack(side=tk.LEFT, padx=5)

                self.stop_btn = tk.Button(btn_frame, text="停止", command=self.stop, width=15, state=tk.DISABLED, bg="red", fg="white")
                self.stop_btn.pack(side=tk.LEFT, padx=5)

            def log(self, msg):
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)

            def start(self):
                if self.workflow and self.workflow.running:
                    return

                self.log("=" * 60)
                self.log("启动工作流...")
                self.log("=" * 60)

                self.workflow = Workflow(config, progress_callback=self.log)
                self.start_btn.config(state=tk.DISABLED)
                self.pause_btn.config(state=tk.NORMAL)
                self.stop_btn.config(state=tk.NORMAL)
                self.status_label.config(text="状态: 运行中", fg="green")

                def run_async():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.workflow.run())
                    self.root.after(0, self.on_complete)

                self.thread = threading.Thread(target=run_async)
                self.thread.start()

            def pause(self):
                if self.workflow:
                    paused = self.workflow.pause()
                    self.status_label.config(
                        text=f"状态: {'已暂停' if paused else '运行中'}",
                        fg="orange" if paused else "green"
                    )

            def stop(self):
                if self.workflow:
                    self.workflow.stop()
                self.status_label.config(text="状态: 已停止", fg="red")

            def on_complete(self):
                self.start_btn.config(state=tk.NORMAL)
                self.pause_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.DISABLED)
                self.status_label.config(text="状态: 完成", fg="blue")
                self.log("\n" + "=" * 60)
                self.log("工作流执行完成！")
                self.log("=" * 60)

        root = tk.Tk()
        app = App(root)
        root.mainloop()
    else:
        # 命令行模式
        print("运行命令行模式...")
        workflow = Workflow(config)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(workflow.run())

if __name__ == "__main__":
    main()
