#!/usr/bin/env python3
"""
导出数据库中的所有产品到 JSON 文件
"""
import json
import urllib.request
from datetime import datetime

SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF3Y3drZmF2a3Jldnhvbm5ma3J3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDE0OTAxNSwiZXhwIjoyMDg5NzI1MDE1fQ.m95EuxyrAf2ujV7_R3x2ryvZ0ZnCfZhxA9Z4Qbs51kU"
URL = "https://qwcwkfavkrevxonnfkrw.supabase.co"

def export_all_products():
    """导出所有产品到 JSON 文件"""
    products = []
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}"
    }
    
    print(f"Exporting products from database...")
    
    # 分页获取所有产品
    for offset in range(0, 10000, 1000):
        url = f"{URL}/rest/v1/products?select=*&limit=1000&offset={offset}"
        req = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read())
                if not data:
                    break
                products.extend(data)
                print(f"Fetched {len(data)} products (Total: {len(products)})")
                if len(data) < 1000:
                    break
        except Exception as e:
            print(f"Error fetching offset {offset}: {e}")
            break
    
    # 保存到文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"products_export_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*50}")
    print(f"EXPORT COMPLETE")
    print(f"{'='*50}")
    print(f"Total products: {len(products)}")
    print(f"Saved to: {output_file}")
    
    return output_file

if __name__ == "__main__":
    export_all_products()
