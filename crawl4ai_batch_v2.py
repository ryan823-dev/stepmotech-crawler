#!/usr/bin/env python3
"""Crawl4AI批量爬取器"""
import sys, io, json, time, re, asyncio
from pathlib import Path
from datetime import datetime
from crawl4ai import AsyncWebCrawler

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

DATA_DIR = Path("d:/stepmotech_cf_worker/data")
DATA_DIR.mkdir(exist_ok=True)

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
    if "nema 8" in n: return "stepper-motors-nema-8"
    if "nema 11" in n: return "stepper-motors-nema-11"
    if "nema 14" in n: return "stepper-motors-nema-14"
    if "nema 17" in n: return "stepper-motors-nema-17"
    if "nema 23" in n: return "stepper-motors-nema-23"
    if "nema 24" in n: return "stepper-motors-nema-24"
    if "nema 34" in n: return "stepper-motors-nema-34"
    if "servo" in n: return "servo-motors"
    if "linear" in n: return "linear-actuators"
    if "gearbox" in n: return "gearboxes"
    if "driver" in n: return "drivers"
    return "accessories"

def upload(d):
    import urllib.request, urllib.error
    cfg = {"url":"https://qwcwkfavkrevxonnfkrw.supabase.co","anon_key":"sb_publishable_qqy39AdcMbtNNzhgiD404A_RrjpVI1v"}
    slug = d.get("sku", d["url"].split("/")[-1][:50])
    p = {
        "name": d.get("name", slug),
        "slug": slug,
        "sku": d.get("sku", slug),
        "price": d.get("price", 0),
        "category": cat(d),
        "specifications": d.get("specs", {}),
        "status": "active",
        "updated_at": datetime.now().isoformat()
    }
    h = {"apikey":cfg["anon_key"],"Authorization":f"Bearer {cfg['anon_key']}","Content-Type":"application/json"}
    try:
        cu = f"{cfg['url']}/rest/v1/products?slug=eq.{slug}&select=id"
        req = urllib.request.Request(cu, headers=h)
        with urllib.request.urlopen(req, timeout=10) as r:
            if json.loads(r.read()): return True
        iu = f"{cfg['url']}/rest/v1/products"
        req = urllib.request.Request(iu, data=json.dumps(p).encode(), headers=h, method="POST")
        urllib.request.urlopen(req, timeout=15)
        return True
    except: pass
    return False

async def crawl_one(url):
    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.araw(url)
            if result.success:
                return parse(result.html, url)
    except Exception as e:
        log(f"Crawl4AI error: {e}")
    return None

async def main():
    log("="*50)
    log("Crawl4AI Crawler Starting...")
    urls = get_urls()
    log(f"URLs to process: {len(urls)}")
    if not urls:
        log("No new URLs")
        return
    ok, fail = 0, 0
    for i, url in enumerate(urls):
        log(f"[{i+1}/{len(urls)}] {url[:50]}...")
        d = await crawl_one(url)
        if d and upload(d):
            ok += 1
            log(f"  OK: {d.get('sku','')[:30]}")
            pf = DATA_DIR/"products.json"
            ex = []
            if pf.exists():
                with open(pf,"r",encoding="utf-8") as f:
                    ex = json.load(f)
            ex.append({"url":url,"name":d.get("name",""),"sku":d.get("sku","")})
            with open(pf,"w",encoding="utf-8") as f:
                json.dump(ex, f, ensure_ascii=False)
        else:
            fail += 1
            log("  FAIL")
        if (i+1) % 20 == 0:
            log(f"Progress: {i+1}/{len(urls)} OK:{ok} FAIL:{fail}")
        await asyncio.sleep(2)
    log("="*50)
    log(f"DONE! OK:{ok} FAIL:{fail}")
    log("="*50)

if __name__ == "__main__":
    asyncio.run(main())
