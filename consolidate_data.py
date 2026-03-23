#!/usr/bin/env python3
"""Extract and consolidate all useful data from stepperonline"""

import sys
import io
import json
import re
import os
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = Path("d:/stepperonline_crawler_data")
OUTPUT_DIR = DATA_DIR / "consolidated"
OUTPUT_DIR.mkdir(exist_ok=True)

def load_all_products():
    """Load all product data from various sources"""
    products = {}

    # Source 1: products_crawl4ai_valid.json
    f = DATA_DIR / "products_crawl4ai_valid.json"
    if f.exists():
        with open(f, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
            for p in data:
                key = p.get('sku') or p.get('source_url', '')
                if key:
                    products[key] = p
        print(f"Loaded {len(data)} products from crawl4ai")

    # Source 2: product_*.json files
    for f in DATA_DIR.glob("product_*.json"):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                key = data.get('sku') or data.get('source_url', '')
                if key and key not in products:
                    products[key] = data
        except:
            pass
    print(f"Total unique products: {len(products)}")

    return list(products.values())

def extract_categories(products):
    """Extract category structure from product data"""
    categories = defaultdict(list)

    for p in products:
        name = p.get('name', '').lower()

        if 'nema' in name or 'stepper motor' in name or 'bipolar' in name:
            cat = 'stepper-motors'
            # Further categorize by size
            if 'nema 8' in name: subcat = 'nema-8'
            elif 'nema 11' in name: subcat = 'nema-11'
            elif 'nema 14' in name: subcat = 'nema-14'
            elif 'nema 17' in name: subcat = 'nema-17'
            elif 'nema 23' in name: subcat = 'nema-23'
            elif 'nema 24' in name: subcat = 'nema-24'
            elif 'nema 34' in name: subcat = 'nema-34'
            else: subcat = 'other'
        elif 'servo' in name or 'a6' in name:
            cat = 'servo-motors'
            subcat = 'servo-kits'
        elif any(k in name for k in ['linear', 'actuator', 'ball screw', 'acme', 'captive', 'external', 'lead screw']):
            cat = 'linear-actuators'
            if 'ball screw' in name: subcat = 'ball-screw'
            elif 'acme' in name: subcat = 'acme'
            elif 'captive' in name: subcat = 'captive'
            elif 'external' in name: subcat = 'external'
            else: subcat = 'linear-other'
        elif any(k in name for k in ['gearbox', 'planetary', 'reducer', 'g ratio']):
            cat = 'gearboxes'
            subcat = 'planetary'
        elif any(k in name for k in ['driver', 'dm5', 'dm8', 'stepper drive']):
            cat = 'drivers'
            subcat = 'stepper-drivers'
        elif any(k in name for k in ['cable', 'wire', 'connector', 'bracket', 'mount', 'coupling', 'vibration', 'kit']):
            cat = 'accessories'
            subcat = 'other-accessories'
        else:
            cat = 'accessories'
            subcat = 'other'

        categories[cat].append({
            'sku': p.get('sku', ''),
            'name': p.get('name', ''),
            'price': p.get('price'),
            'subcategory': subcat
        })

    return dict(categories)

def extract_specifications(products):
    """Extract all unique specifications"""
    all_specs = set()

    for p in products:
        specs = p.get('specifications', {})
        if isinstance(specs, dict):
            all_specs.update(specs.keys())

    return sorted(list(all_specs))

def extract_images(products):
    """Extract all unique image URLs"""
    images = set()

    for p in products:
        for img in p.get('images', []):
            if img and isinstance(img, str):
                images.add(img)

        # Also extract from source URL
        url = p.get('source_url', '')
        if url:
            # Extract potential image patterns
            matches = re.findall(r'https?://[^\s"]+\.(?:jpg|jpeg|png|webp)', url)
            for m in matches:
                images.add(m)

    return sorted(list(images))

def extract_pdfs(products):
    """Extract PDF/datasheet URLs"""
    pdfs = []

    for p in products:
        url = p.get('source_url', '')
        sku = p.get('sku', '')

        # Common PDF patterns
        if sku:
            pdf_urls = [
                f"https://www.omc-stepperonline.com/download/datasheet/{sku}.pdf",
                f"https://www.omc-stepperonline.com/datasheet/{sku}.pdf",
                f"https://www.omc-stepperonline.com/image/data/{sku}.pdf",
            ]
            for pdf_url in pdf_urls:
                pdfs.append({
                    'sku': sku,
                    'name': p.get('name', ''),
                    'pdf_url': pdf_url
                })

    return pdfs

def extract_multi_language_urls(products):
    """Extract multi-language URLs"""
    base_url = "https://www.omc-stepperonline.com"
    lang_prefixes = ['en', 'es', 'pt', 'ru', 'fr', 'vi', 'th', 'id', 'pl', 'de', 'it', 'nl']

    urls_by_lang = defaultdict(list)

    for p in products:
        source_url = p.get('source_url', '')
        if source_url:
            # Extract slug from URL
            slug_match = re.search(r'com/([^/]+)$', source_url)
            if slug_match:
                slug = slug_match.group(1)
                for lang in lang_prefixes:
                    # Some URLs already have lang prefix
                    if f'/{lang}/' in source_url:
                        urls_by_lang[lang].append(source_url)
                    else:
                        # Generate localized URL
                        localized_url = f"{base_url}/{lang}/{slug}"
                        urls_by_lang[lang].append(localized_url)

    return dict(urls_by_lang)

def generate_seo_content(products):
    """Generate SEO-friendly content structure"""
    seo_data = {
        'meta_descriptions': [],
        'keywords': set(),
        'title_patterns': []
    }

    for p in products:
        name = p.get('name', '')
        sku = p.get('sku', '')
        desc = p.get('description', '')

        if name:
            seo_data['title_patterns'].append({
                'pattern': name,
                'sku': sku,
                'suggested_title': f"{name} - {sku} | StepperOnline"
            })

        if desc:
            seo_data['meta_descriptions'].append({
                'sku': sku,
                'description': desc[:160]  # SEO meta description length
            })

        # Extract keywords
        if name:
            words = re.findall(r'\b[A-Za-z]{4,}\b', name)
            seo_data['keywords'].update(words)

    seo_data['keywords'] = sorted(list(seo_data['keywords']))
    return seo_data

def main():
    print("=" * 60)
    print("Consolidate All StepperOnline Data")
    print("=" * 60)

    # Load all products
    print("\n1. Loading all product data...")
    products = load_all_products()
    print(f"   Total products: {len(products)}")

    # Extract categories
    print("\n2. Extracting category structure...")
    categories = extract_categories(products)
    print(f"   Categories found: {len(categories)}")
    for cat, prods in categories.items():
        print(f"   - {cat}: {len(prods)} products")

    # Save categories
    with open(OUTPUT_DIR / "categories.json", 'w', encoding='utf-8') as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)
    print(f"   Saved to: categories.json")

    # Extract specifications
    print("\n3. Extracting specifications...")
    specs = extract_specifications(products)
    print(f"   Unique specifications: {len(specs)}")
    with open(OUTPUT_DIR / "specifications.json", 'w', encoding='utf-8') as f:
        json.dump(specs, f, indent=2)
    print(f"   Saved to: specifications.json")

    # Extract images
    print("\n4. Extracting image URLs...")
    images = extract_images(products)
    print(f"   Unique images: {len(images)}")
    with open(OUTPUT_DIR / "image_urls.json", 'w', encoding='utf-8') as f:
        json.dump(images, f, indent=2)
    print(f"   Saved to: image_urls.json")

    # Extract PDFs
    print("\n5. Extracting PDF/datasheet URLs...")
    pdfs = extract_pdfs(products)
    print(f"   Potential PDFs: {len(pdfs)}")
    with open(OUTPUT_DIR / "pdf_urls.json", 'w', encoding='utf-8') as f:
        json.dump(pdfs, f, indent=2, ensure_ascii=False)
    print(f"   Saved to: pdf_urls.json")

    # Extract multi-language URLs
    print("\n6. Extracting multi-language URLs...")
    lang_urls = extract_multi_language_urls(products)
    print(f"   Languages: {list(lang_urls.keys())}")
    for lang, urls in lang_urls.items():
        print(f"   - {lang}: {len(urls)} URLs")

    # Save consolidated products
    print("\n7. Saving consolidated products...")
    with open(OUTPUT_DIR / "all_products_consolidated.json", 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print(f"   Saved {len(products)} products")

    # Generate SEO content
    print("\n8. Generating SEO content...")
    seo = generate_seo_content(products)
    with open(OUTPUT_DIR / "seo_content.json", 'w', encoding='utf-8') as f:
        json.dump(seo, f, indent=2, ensure_ascii=False)
    print(f"   Keywords: {len(seo['keywords'])}")
    print(f"   Title patterns: {len(seo['title_patterns'])}")

    # Summary report
    print("\n" + "=" * 60)
    print("CONSOLIDATION COMPLETE")
    print("=" * 60)
    print(f"Output directory: {OUTPUT_DIR}")
    print("\nFiles created:")
    print("  - categories.json")
    print("  - specifications.json")
    print("  - image_urls.json")
    print("  - pdf_urls.json")
    print("  - all_products_consolidated.json")
    print("  - seo_content.json")

if __name__ == "__main__":
    main()
