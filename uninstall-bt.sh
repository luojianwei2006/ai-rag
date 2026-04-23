#!/bin/bash
# ============================================================
# AI 客服平台 - 卸载脚本
# 使用方式：chmod +x uninstall-bt.sh && ./uninstall-bt.sh
# ============================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}  $1"; }

APP_NAME="customer-service"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "================================================"
echo "   AI 客服平台 - 卸载脚本"
echo "================================================"
echo ""
warn "此操作将停止服务并删除 systemd 配置，数据目录不会删除"
read -p "确认卸载？(输入 yes 继续): " CONFIRM
[ "$CONFIRM" != "yes" ] && echo "已取消" && exit 0

# 停止并禁用服务
systemctl stop ${APP_NAME} 2>/dev/null && success "服务已停止"
systemctl disable ${APP_NAME} 2>/dev/null && success "服务已禁用"
rm -f /etc/systemd/system/${APP_NAME}.service
systemctl daemon-reload
success "systemd 配置已清理"

# 删除 Nginx 配置
for d in /etc/nginx/conf.d /etc/nginx/sites-available /www/server/nginx/conf/vhost; do
    if [ -f "$d/${APP_NAME}.conf" ]; then
        rm -f "$d/${APP_NAME}.conf"
        success "Nginx 配置已删除：$d/${APP_NAME}.conf"
    fi
done

# 重载 Nginx
if command -v bt &>/dev/null && [ -f "/www/server/nginx/sbin/nginx" ]; then
    /www/server/nginx/sbin/nginx -s reload 2>/dev/null
elif command -v nginx &>/dev/null; then
    nginx -s reload 2>/dev/null
fi

echo ""
echo "================================================"
echo -e "${GREEN}  ✅ 卸载完成${NC}"
echo "================================================"
echo ""
echo "  数据目录保留在："
echo "    $APP_DIR/backend/data/       (数据库)"
echo "    $APP_DIR/backend/uploads/    (上传文件)"
echo "    $APP_DIR/backend/chroma_db/  (向量数据库)"
echo ""
echo "  如需彻底删除数据，手动执行："
echo "    rm -rf $APP_DIR/backend/data $APP_DIR/backend/uploads $APP_DIR/backend/chroma_db"
echo ""
