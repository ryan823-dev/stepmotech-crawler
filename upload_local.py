#!/usr/bin/env python3
import os, sys, io, json, asyncio
from pathlib import Path
from datetime import datetime
import urllib.request, urllib.error

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
DATA_DIR = Path("d:/stepmotech_cf_worker/data")
DATA_DIR.mkdir(exist_ok=True)

SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF3Y3drZmF2a3Jldnhvbm5ma3J3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDE0OTAxNSwiZXhwIjoyMDg5NzI1MDE1fQ.m95EuxyrAf2ujV7_R3x2ryvZ0ZnCfZhxA9Z4Qbs51kU"
URL = "https://qwcwkfavkrevxonnfkrw.supabase.co"

CAT_IDS = {"stepper-motors":"4287020d-976c-4b3e-9387-9a7b6e63827b","servo-motors":"4192975d-229e-4ff2-9bc9-dbd96e8d3f30","linear-actuators":"7b150daf-0c65-4e10-a7b6-0dfdfca43470","gearboxes":"6f73517e-4b4c-43b3-9675-b719d3989f92","drivers":"93a18c2a-8a5b-4b2f-a8fc-f3f8e08791af","accessories":"77158756-ee6e-4df0-9c23-5f67a8261b35"}

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
    with open(DATA_DIR/"crawler.log","a",encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def get_db_skus():
    skus = set()
    h = {"apikey":SERVICE_KEY,"Authorization":f"Bearer {SERVICE_KEY}"}
    try:
        for offset in range(0, 10000, 1000):
            cu = f"{URL}/rest/v1/products?select=sku&limit=1000&offset={offset}"
            req = urllib.request.Request(cu, headers=h)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
                if not data: break
                for p in data: skus.add(p.get('sku',''))
                if len(data) < 1000: break
    except Exception as e:
        log(f"Error: {e}")
    return skus

def get_local_done():
    pf = DATA_DIR/"products.json"
    if pf.exists():
        with open(pf,"r",encoding="utf-8") as f:
            return set(p.get("sku","") for p in json.load(f))
    return set()

def get_local_products():
    products = []
    src = Path("d:/stepperonline_crawler_data/consolidated/complete_data.json")
    if src.exists():
        with open(src, "r", encoding="utf-8") as f:
            for p in json.load(f):
                slug = p.get("slug", "")
                specs = p.get("specifications", {})
                sku = specs.get("Model", slug) or slug
                products.append({"slug": slug, "sku": sku, "specs": specs})
    return products

def get_cat(sku, specs):
    text = (sku + " " + str(specs)).lower()
    if "nema" in text: return CAT_IDS["stepper-motors"]
    if "servo" in text: return CAT_IDS["servo-motors"]
    if "linear" in text or "actuator" in text: return CAT_IDS["linear-actuators"]
    if "gearbox" in text or "gear" in text: return CAT_IDS["gearboxes"]
    if "driver" in text: return CAT_IDS["drivers"]
    return CAT_IDS["accessories"]

def upload(p):
    sku, slug = p["sku"], p.get("slug", p["sku"])
    data = {"slug": slug, "sku": sku, "price": 0, "categoryId": get_cat(sku, p.get("specs", {})), "specifications": p.get("specs", {}), "active": True, "stock": 100, "stockStatus": "IN_STOCK", "currency": "USD"}
    h = {"apikey":SERVICE_KEY,"Authorization":f"Bearer {SERVICE_KEY}","Content-Type":"application/json"}
    try:
        req = urllib.request.Request(f"{URL}/rest/v1/products?sku=eq.{sku}&select=id", headers=h)
        with urllib.request.urlopen(req, timeout=10) as r:
            if json.loads(r.read()): return "dup"
        req = urllib.request.Request(f"{URL}/rest/v1/products", data=json.dumps(data).encode(), headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return "ok" if r.status in (200,201) else "fail"
    except urllib.error.HTTPError as e:
        return "dup" if e.code == 409 else "err"
    except: return "err"

def save(sku, slug):
    pf = DATA_DIR/"products.json"
    ex = []
    if pf.exists():
        with open(pf,"r",encoding="utf-8") as f: ex = json.load(f)
    ex.append({"sku":sku,"slug":slug})
    with open(pf,"w",encoding="utf-8") as f: json.dump(ex, f)

async def main():
    log("="*50)
    log("UPLOADER STARTED")
    log("="*50)
    ok = dup = fail = 0
    while True:
        log("Checking DB...")
        db = get_db_skus()
        log(f"DB: {len(db)} products")
        prods = get_local_products()
        log(f"Local: {len(prods)} products")
        done = get_local_done()
        new = [p for p in prods if p["sku"] not in db | done]
        if not new:
            log("All done! Waiting...")
            await asyncio.sleep(60)
            continue
        log(f"New: {len(new)}")
        for i, p in enumerate(new):
            log(f"[{i+1}/{len(new)}] {p['sku'][:35]}...")
            r = upload(p)
            if r == "ok":
                ok += 1
                save(p["sku"], p.get("slug", p["sku"]))
            elif r == "dup": dup += 1
            else: fail += 1
            if (i+1) % 20 == 0:
                log(f"OK:{ok} Dup:{dup} Fail:{fail}")
            await asyncio.sleep(0.3)
        log(f"Batch: OK:{ok} Dup:{dup} Fail:{fail}")
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
