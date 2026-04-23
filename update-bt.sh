#!/bin/bash
# ============================================================
# AI 客服平台 - 更新脚本
# 用于从 GitHub 拉取最新代码后重新部署
# 使用方式：chmod +x update-bt.sh && ./update-bt.sh
# ============================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}  $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

APP_NAME="customer-service"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"

echo ""
echo "================================================"
echo "   AI 客服平台 - 更新脚本"
echo "================================================"
echo ""

# 拉取最新代码
if [ -d "$APP_DIR/.git" ]; then
    info "拉取最新代码..."
    cd "$APP_DIR"
    git pull origin main
    success "代码已更新"
else
    warn "未检测到 Git 仓库，跳过代码拉取，直接重新部署"
fi

# 更新 Python 依赖
info "更新 Python 依赖..."
cd "$BACKEND_DIR"
source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q --timeout 120
deactivate
success "Python 依赖已更新"

# 重新构建前端
info "重新构建前端..."
cd "$FRONTEND_DIR"
npm install --registry=https://registry.npmmirror.com -q
npm run build
success "前端已重新打包"

# 重启后端服务
info "重启后端服务..."
systemctl restart ${APP_NAME}
sleep 3

if systemctl is-active --quiet ${APP_NAME}; then
    success "后端服务重启成功"
else
    error "后端服务重启失败，请查看日志：journalctl -u $APP_NAME -n 30"
fi

# 重载 Nginx
if command -v bt &>/dev/null && [ -f "/www/server/nginx/sbin/nginx" ]; then
    /www/server/nginx/sbin/nginx -s reload 2>/dev/null && success "宝塔 Nginx 已重载"
elif command -v nginx &>/dev/null; then
    nginx -s reload 2>/dev/null && success "Nginx 已重载"
fi

echo ""
echo "================================================"
echo -e "${GREEN}  ✅ 更新完成！${NC}"
echo "================================================"
echo ""
