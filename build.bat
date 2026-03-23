@echo off
chcp 65001 >nul
echo ========================================
echo StepperOnline 爬取工具 - 打包脚本
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo 正在安装PyInstaller...
    pip install pyinstaller -q
)

REM 创建初始配置
echo 创建配置文件...
if not exist "config.json" (
    echo {"supabase": {"url": "","anon_key": ""},"crawl": {"max_products": 500}} > config.json
)

REM 打包
echo.
echo 开始打包...
python -m PyInstaller stepmotech_crawler.spec --clean

if errorlevel 1 (
    echo.
    echo 打包失败!
    pause
    exit /b 1
)

REM 复制配置文件和数据目录
echo.
echo 复制配置文件...
if exist "config.json" (
    copy "config.json" "dist\config.json" >nul
)

if exist "data" (
    xcopy /E /I /Y "data" "dist\data" >nul
)

REM 创建数据目录
if not exist "dist\data" (
    mkdir "dist\data"
)

echo.
echo ========================================
echo 打包完成!
echo ========================================
echo.
echo 输出目录: dist\
echo 运行: dist\StepperOnline爬取工具.exe
echo.
echo 首次运行请配置Supabase连接:
echo 1. 编辑 config.json
echo 2. 填入 supabase.url 和 supabase.anon_key
echo.
pause
