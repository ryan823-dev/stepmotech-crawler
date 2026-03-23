# StepperOnline Crawler & Uploader

智能爬虫和自动上架工具 - 从 omc-stepperonline.com 爬取产品数据并自动上传到 Supabase 数据库

## 功能特性

- **智能反爬虫绕过**: 使用 Playwright 和多种反检测技术
- **批量数据上传**: 支持批量上传产品到 Supabase
- **重复检测**: 自动跳过已存在的产品
- **无限循环运行**: 后台持续监控新数据
- **数据导出**: 导出所有已上架产品到 JSON

## 核心文件

### 爬虫文件
- `crawl_stepper.py` - 最新智能爬虫（Playwright 反检测）
- `upload_local.py` - 本地数据上传器（无限循环）
- `export_products.py` - 产品数据导出工具

### 数据文件
- `data/products.json` - 已上传产品记录
- `data/crawler.log` - 爬虫日志
- `products_export_*.json` - 导出的产品数据

## 使用方法

### 1. 上传本地数据
```bash
python upload_local.py
```

### 2. 运行智能爬虫
```bash
python crawl_stepper.py
```

### 3. 导出产品数据
```bash
python export_products.py
```

## 数据库统计

- 总产品数：533+
- 分类：步进电机、伺服电机、线性执行器、齿轮箱、驱动器、配件
- 数据库：Supabase PostgreSQL

## 技术栈

- Python 3.x
- Playwright (浏览器自动化)
- Supabase (数据库)
- JSON (数据存储)

## 注意事项

- 需要稳定的网络连接
- 首次运行可能需要安装 Playwright 浏览器
- 建议使用 VPN 避免 IP 封锁
