#!/bin/bash
# 前端部署脚本 - 在本地运行
# 用法: ./deploy-frontend.sh <服务器IP> [用户名] [远程目录]
# 示例: ./deploy-frontend.sh 3.15.217.0 ec2-user /var/www/html/customer-service

set -e

SERVER_IP="${1}"
SERVER_USER="${2:-ec2-user}"
REMOTE_PATH="${3:-/var/www/html/customer-service}"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "$SERVER_IP" ]; then
    echo "❌ 请提供服务器IP地址"
    echo "用法: $0 <服务器IP> [用户名] [远程目录]"
    exit 1
fi

echo "📦 开始构建前端..."
cd "$LOCAL_DIR/frontend"
npm install --legacy-peer-deps 2>/dev/null || npm install
npm run build

echo "📤 上传到服务器 $SERVER_IP..."
ssh "$SERVER_USER@$SERVER_IP" "sudo mkdir -p $REMOTE_PATH && sudo chown -R $SERVER_USER:$SERVER_USER $REMOTE_PATH"
scp -r dist/* "$SERVER_USER@$SERVER_IP:$REMOTE_PATH/"

echo "✅ 前端部署完成！"
echo "   服务器路径: $REMOTE_PATH"
echo "   请确保 nginx 已配置并指向此目录"
