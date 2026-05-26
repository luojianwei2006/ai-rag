#!/bin/bash
# 后台启动生产服务
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

nohup "$ROOT/prod.sh" > "$ROOT/app.log" 2>&1 &

echo "✅ 服务已在后台启动"
echo "   日志: $ROOT/app.log"
echo "   查看: tail -f $ROOT/app.log"
echo "   停止: kill \$(pgrep -f 'uvicorn main:app')"
