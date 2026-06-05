# -*- coding: utf-8 -*-
# 入口文件：供 PyInstaller 打包用
# 用法：pyinstaller customer_service.spec

import sys
import os

# 让 PyInstaller 能找到模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from main import app

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Customer Service API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind")
    parser.add_argument("--workers", default=1, type=int, help="Number of workers")
    args = parser.parse_args()

    print(f"🚀 Starting Customer Service API on {args.host}:{args.port}")
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level="info"
    )
