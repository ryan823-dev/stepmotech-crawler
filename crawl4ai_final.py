#!/usr/bin/env python3
"""Crawl4AI爬取上架 v7 - 最终版"""
import sys, io, json, asyncio
from pathlib import Path
from datetime import datetime
from crawl4ai import AsyncWebCrawler
import re, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = Path("d:/stepmotech_cf_worker/data")
DATA_DIR.mkdir(exist_ok=True)

SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF3Y3drZmF2a3Jldnhvbm5ma3J3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDE0OTAxNSwiZXhwIjoyMDg5NzI1MDE1fQ.m95EuxyrAf2ujV7_R3x2ryvZ0ZnCfZhxA9Z4Qbs51kU"
URL = "https://qwcwkfavkrevxonnfkrw.supabase.co"

CAT_IDS = {
    "stepper-motors":"4287020d-976c-4b3e-9387-9a7b6e63827b",
    "servo-motors":"4192975d-229e-4ff2-9bc9-dbd96e8d3f30",
    "linear-actuators":"7b150daf-0c65-4e10-a7b6-0dfdfca43470",
    "gearboxes":"6f73517e-4b4c-43b3-9675-b719d3989f92",
    "drivers":"93a18c2a-8a5b-4b2f-a8fc-f3f8e08791af",
    "accessories":"77158756-ee6e-4df0-9c23-5f67a8261b35"
}

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(DATA_DIR/"crawler.log","a",encoding="utf-8") as f:
        f.write(line+"/n")

def get_urls():
    urls = []
    src = Path("d:/stepperonline_crawler_data/consolidated/complete_data.json")
    if src.exists():
        with open(src,"r",encoding="utf-8") as f:
            for p in json.load(f):
                urls.append(f"https://www.omc-stepperonline.com/{p['slug']}")
    done = set()
    pf = DATA_DIR/"products.json"
    if pf.exists():
        with open(pf,"r",encoding="utf-8") as f:
            for p in json.load(f):
                done.add(p.get("url",""))
    return [u for u in urls if u not in done]

def parse(html, url):
    d = {"url":url,"name":"","price":0,"sku":"","specs":{}}
    m = re.search(r"<title>([^<]+)</title>", html)
    if m: d["name"] = re.sub(r"/s*/|/s*StepperOnline/s*$","",m.group(1))
    m = re.search(r"<li>Model:/s*([^<]+)</li>", html)
    if m: d["sku"] = m.group(1).strip()
    m = re.search(r"/$([/d,]+/.?/d*)", html)
    if m:
        try: d["price"] = float(re.sub(r"[^/d.]","",m.group(1)))
        except: pass
    for li in re.findall(r"<li[^>]*>(.*?)</li>", html, re.DOTALL):
        c = re.sub(r"<[^>]+>","",li).strip()
        if ":" in c and 3 < len(c) < 150:
            k,v = c.split(":",1)
            k,v = k.strip(), v.strip()
            if k and v and k not in ["About Us","Contact","FAQ"]:
                d["specs"][k] = v
    return d if d.get("name") or d.get("sku") else None

def cat(d):
    n = (d.get("name","") + d.get("sku","")).lower()
    if "nema" in n: return "stepper-motors"
    if "servo" in n: return "servo-motors"
    if "linear" in n or "actuator" in n: return "linear-actuators"
    if "gearbox" in n: return "gearboxes"
    if "driver" in n: return "drivers"
    return "accessories"

def upload(d):
    slug = d.get("sku", d["url"].split("/")[-1][:50])[:100]
    cat_id = CAT_IDS.get(cat(d), CAT_IDS["accessories"])
    p = {
        "slug": slug,
        "sku": d.get("sku", slug),
        "price": d.get("price", 0),
        "categoryId": cat_id,
        "specifications": d.get("specs", {}),
        "active": True,
        "stock": 100,
        "stockStatus": "IN_STOCK",
        "currency": "USD"
    }
    h = {"apikey":SERVICE_KEY,"Authorization":f"Bearer {SERVICE_KEY}","Content-Type":"application/json"}
    try:
        cu = f"{URL}/rest/v1/products?slug=eq.{slug}&select=id"
        req = urllib.request.Request(cu, headers=h)
        with urllib.request.urlopen(req, timeout=10) as r:
            if json.loads(r.read()): return True
        iu = f"{URL}/rest/v1/products"
        req = urllib.request.Request(iu, data=json.dumps(p).encode(), headers=h, method="POST")
        urllib.request.urlopen(req, timeout=15)
        return True
    except: return False

async def main():
    log("="*50)
    log("Crawl4AI v7 STARTING...")
    urls = get_urls()
    log(f"URLs: {len(urls)}")
    if not urls:
        log("No new URLs - Done!")
        return
    
    ok, fail = 0, 0
    async with AsyncWebCrawler(verbose=False) as crawler:
        for i, url in enumerate(urls):
            log(f"[{i+1}/{len(urls)}] {url[:50]}...")
            try:
                result = await crawler.arun(url=url)
                if result.success:
                    d = parse(result.html, url)
                    if d and upload(d):
                        ok += 1
                        log(f"  OK: {d.get('sku','')[:30]}")
                        pf = DATA_DIR/"products.json"
                        ex = []
                        if pf.exists():
                            with open(pf,"r",encoding="utf-8") as f:
                                ex = json.load(f)
                        ex.append({"url":url,"sku":d.get("sku","")})
                        with open(pf,"w",encoding="utf-8") as f:
                            json.dump(ex, f, ensure_ascii=False)
                    else:
                        fail += 1
                        log("  FAIL upload")
                else:
                    fail += 1
            except Exception as e:
                fail += 1
                log(f"  ERROR")
            
            if (i+1) % 10 == 0:
                log(f"Progress: {i+1}/{len(urls)} OK:{ok} FAIL:{fail}")
            await asyncio.sleep(2)
    
    log(f"DONE! OK:{ok} FAIL:{fail}")

if __name__ == "__main__":
    asyncio.run(main())
