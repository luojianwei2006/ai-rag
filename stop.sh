#!/bin/bash
# 停止生产服务
pkill -f "uvicorn main:app" && echo "✅ 服务已停止" || echo "⚠️ 未找到运行中的服务"
