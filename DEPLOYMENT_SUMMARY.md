# StepperOnline Crawler - GitHub 部署总结

## 仓库信息

- **GitHub 仓库**: https://github.com/ryan823-dev/stepmotech-crawler
- **分支**: main
- **提交**: Initial commit (affdb4a)
- **文件数**: 36 个文件

## 数据库状态

### 已上架产品统计
- **总产品数**: 533 个
- **数据库**: Supabase PostgreSQL
- **导出文件**: `products_export_latest.json` (533 个产品完整数据)

### 产品分类
- 步进电机 (stepper-motors)
- 伺服电机 (servo-motors)
- 线性执行器 (linear-actuators)
- 齿轮箱 (gearboxes)
- 驱动器 (drivers)
- 配件 (accessories)

## 核心文件说明

### 🕷️ 爬虫文件
1. **`crawl_stepper-PACHHONG.py`** ⭐ 最新版本
   - Playwright 反检测爬虫
   - 多种 User-Agent 轮换
   - 浏览器指纹模拟
   - 反自动化脚本注入

2. **`crawl_stepper.py`** - 原始智能爬虫
3. **`crawler_*.py`** - 历史版本爬虫（多种实现方式）

### 📤 上传文件
1. **`upload_local.py`** ⭐ 自动上传器
   - 无限循环监控
   - 自动重复检测
   - 批量上传到 Supabase
   - 日志记录功能

2. **`export_products.py`** - 数据导出工具
   - 导出所有已上架产品
   - JSON 格式保存

### 📊 数据文件
1. **`products_export_latest.json`** - 533 个产品完整数据
2. **`data/stepper_products.json`** - 爬取的产品数据
3. **`data/products.json`** - 已上传产品记录

### 📝 配置文件
- `README.md` - 项目说明文档
- `.gitignore` - Git 忽略配置
- `config.json` - 配置文件
- `wrangler.toml` - Cloudflare Workers 配置

## 使用方法

### 1. 克隆仓库
```bash
git clone https://github.com/ryan823-dev/stepmotech-crawler.git
cd stepmotech-crawler
```

### 2. 安装依赖
```bash
npm install  # 安装 Node.js 依赖
pip install playwright  # 安装 Python 爬虫依赖
playwright install chromium  # 安装浏览器
```

### 3. 运行爬虫
```bash
python crawl_stepper-PACHHONG.py
```

### 4. 运行上传器
```bash
python upload_local.py
```

### 5. 导出数据
```bash
python export_products.py
```

## 技术栈

- **爬虫框架**: Playwright, Crawl4AI
- **数据库**: Supabase (PostgreSQL)
- **语言**: Python 3.x, Node.js
- **部署**: Cloudflare Workers
- **版本控制**: Git + GitHub

## 注意事项

1. **反爬虫策略**
   - 使用 VPN 避免 IP 封锁
   - 请求间隔 2-5 秒
   - 随机 User-Agent 轮换
   - 浏览器指纹模拟

2. **数据安全**
   - Supabase Service Key 已提交（需保密）
   - 建议设置环境变量
   - 生产环境使用 Secrets 管理

3. **维护建议**
   - 定期检查网站反爬策略变化
   - 更新 User-Agent 列表
   - 监控上传日志
   - 备份数据库数据

## 下次更新计划

- [ ] 添加更多反检测策略
- [ ] 实现分布式爬虫
- [ ] 添加图片下载功能
- [ ] 实现 PDF 文档下载
- [ ] 添加数据验证和清洗
