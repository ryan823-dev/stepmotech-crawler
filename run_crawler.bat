@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d d:\stepmotech_cf_worker
python crawl_forever.py
