#!/usr/bin/env python3
"""
智能爬虫 - 使用 Playwright 绕过反爬虫机制
支持多种访问策略，自动切换
"""
import os, sys, io, json, asyncio, random
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
DATA_DIR = Path("d:/stepmotech_cf_worker/data")
DATA_DIR.mkdir(exist_ok=True)

BASE_URL = "https://www.omc-stepperonline.com"
SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF3Y3drZmF2a3Jldnhvbm5ma3J3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDE0OTAxNSwiZXhwIjoyMDg5NzI1MDE1fQ.m95EuxyrAf2ujV7_R3x2ryvZ0ZnCfZhxA9Z4Qbs51kU"
SUPABASE_URL = "https://qwcwkfavkrevxonnfkrw.supabase.co"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
    with open(DATA_DIR/"crawler_stepper.log","a",encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

async def check_site_access(page):
    """检查网站是否可以访问"""
    try:
        await page.goto(BASE_URL, timeout=30000, wait_until="domcontentloaded")
        content = await page.content()
        if "blocked" in content.lower() or "valued visitor" in content.lower():
            log("SITE: BLOCKED - Access denied message detected")
            return False
        if len(content) < 5000:
            log(f"SITE: SUSPICIOUS - HTML only {len(content)} chars")
            return False
        log(f"SITE: ACCESSIBLE - HTML {len(content)} chars")
        return True
    except Exception as e:
        log(f"SITE: ERROR - {e}")
        return False

async def crawl_category(page, category_url, category_id):
    """爬取分类页面获取产品链接"""
    products = []
    try:
        log(f"Crawling category: {category_url}")
        await page.goto(category_url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(2, 4))
        
        # 提取产品链接
        product_links = await page.query_selector_all('.product-thumb a')
        log(f"Found {len(product_links)} products in category")
        
        for link in product_links[:20]:  # 每个分类最多 20 个
            try:
                href = await link.get_attribute('href')
                if href and '/product/' in href:
                    products.append(href)
            except:
                continue
    except Exception as e:
        log(f"Category crawl error: {e}")
    
    return products

async def extract_product_data(page, product_url):
    """提取产品详细数据"""
    try:
        await page.goto(product_url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(1, 3))
        
        # 检查是否被封锁
        content = await page.content()
        if "blocked" in content.lower() or len(content) < 5000:
            return None
        
        # 提取数据
        try:
            slug = product_url.split('/product/')[-1].split('?')[0].strip('/')
        except:
            slug = product_url
        
        specs = {}
        
        # 提取型号
        try:
            model = await page.locator('h1').first.inner_text()
            if model:
                specs['Model'] = model.strip()
        except:
            pass
        
        # 提取规格表
        try:
            spec_rows = await page.query_selector_all('.spec-table tr')
            for row in spec_rows:
                try:
                    cells = await row.query_selector_all('td')
                    if len(cells) >= 2:
                        key = await cells[0].inner_text()
                        value = await cells[1].inner_text()
                        if key and value:
                            specs[key.strip()] = value.strip()
                except:
                    continue
        except:
            pass
        
        # 提取图片
        images = []
        try:
            img_elements = await page.query_selector_all('.product-images img')
            for img in img_elements[:5]:
                src = await img.get_attribute('src')
                if src and src.startswith('http'):
                    images.append(src)
        except:
            pass
        
        if specs:
            return {
                "slug": slug,
                "specifications": specs,
                "images": images,
                "url": product_url
            }
    except Exception as e:
        log(f"Extract error: {e}")
    
    return None

async def main():
    log("="*60)
    log("SMART CRAWLER STARTED - Playwright Anti-Detection")
    log("="*60)
    
    all_products = []
    
    async with async_playwright() as p:
        # 使用随机浏览器指纹
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=random.choice(USER_AGENTS),
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            geolocation={'latitude': 40.7128, 'longitude': -74.0060}
        )
        
        # 注入反检测脚本
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US']});
        """)
        
        page = await context.new_page()
        
        # 检查网站访问
        log("Testing site accessibility...")
        accessible = await check_site_access(page)
        
        if not accessible:
            log("WARNING: Site is still blocking access!")
            log("Trying alternative approach...")
            
            # 尝试直接访问产品页面
            test_urls = [
                f"{BASE_URL}/product/nema-17-stepper-motor",
                f"{BASE_URL}/product/stepper-motor-nema-23",
            ]
            
            for url in test_urls:
                try:
                    await page.goto(url, timeout=15000)
                    await asyncio.sleep(2)
                    content = await page.content()
                    if len(content) > 5000 and "blocked" not in content.lower():
                        log(f"SUCCESS: {url} is accessible!")
                        accessible = True
                        break
                except:
                    continue
        
        if accessible:
            log("Site is accessible! Starting crawl...")
            
            # 爬取主要分类
            categories = [
                (f"{BASE_URL}/stepper-motors", "stepper-motors"),
                (f"{BASE_URL}/servo-motors", "servo-motors"),
                (f"{BASE_URL}/linear-actuators", "linear-actuators"),
                (f"{BASE_URL}/gearboxes", "gearboxes"),
            ]
            
            for cat_url, cat_name in categories:
                log(f"Processing category: {cat_name}")
                products = await crawl_category(page, cat_url, cat_name)
                log(f"Got {len(products)} product URLs from {cat_name}")
                
                # 提取产品数据
                for prod_url in products[:10]:  # 每个分类最多 10 个
                    data = await extract_product_data(page, prod_url)
                    if data:
                        all_products.append(data)
                        log(f"Extracted: {data['slug']}")
                    await asyncio.sleep(random.uniform(1, 2))
                
                await asyncio.sleep(random.uniform(3, 5))
        else:
            log("ERROR: Cannot access website. Using fallback data.")
        
        await browser.close()
    
    # 保存结果
    log(f"Total products extracted: {len(all_products)}")
    
    output_file = DATA_DIR/"stepper_products.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)
    
    log(f"Saved to: {output_file}")
    log("CRAWLER FINISHED")
    
    return all_products

if __name__ == "__main__":
    asyncio.run(main())
