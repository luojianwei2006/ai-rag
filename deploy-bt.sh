#!/bin/bash
# ========================================
#  客服管理平台 - 宝塔一键部署脚本
# ========================================
#
# 使用方法：
#   1. 上传整个项目到服务器（如 /www/wwwroot/customer-service）
#   2. chmod +x deploy-bt.sh
#   3. ./deploy-bt.sh
#
# 注意事项：
#   - 需要 Docker 和 Docker Compose
#   - 宝塔面板 → 软件商店 → 安装 Docker 管理器
#   - 默认访问端口 8001，可在下方修改
# ========================================

set -e

# ---- 可修改配置 ----
PORT=8001                          # 外部访问端口
CONTAINER_NAME="customer-service"  # 容器名称
IMAGE_NAME="customer-service-img"  # 镜像名称
# --------------------

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "   客服管理平台 - Docker 部署"
echo "=========================================="
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. 检查 Docker
echo -e "${YELLOW}[1/5] 检查 Docker 环境...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker 未安装！${NC}"
    echo "请在宝塔面板 → 软件商店 → 安装 Docker 管理器"
    exit 1
fi
echo -e "${GREEN} Docker 已安装: $(docker --version)${NC}"

# 检查 Docker Compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif docker-compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}Docker Compose 未安装！${NC}"
    exit 1
fi
echo -e "${GREEN} Docker Compose 已安装${NC}"

# 2. 停止旧容器（如果存在）
echo ""
echo -e "${YELLOW}[2/5] 检查旧容器...${NC}"
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "  停止并移除旧容器..."
    docker rm -f ${CONTAINER_NAME} 2>/dev/null || true
    echo -e "${GREEN} 旧容器已移除${NC}"
else
    echo -e "${GREEN} 无旧容器${NC}"
fi

# 3. 构建镜像
echo ""
echo -e "${YELLOW}[3/5] 构建 Docker 镜像...${NC}"
echo "  （首次构建需要下载依赖，约 5-15 分钟）"
docker build -t ${IMAGE_NAME} .
echo -e "${GREEN} 镜像构建完成${NC}"

# 4. 启动容器
echo ""
echo -e "${YELLOW}[4/5] 启动服务...${NC}"
docker run -d \
    --name ${CONTAINER_NAME} \
    --restart always \
    -p ${PORT}:80 \
    -v ${SCRIPT_DIR}/data:/app/data \
    -v ${SCRIPT_DIR}/uploads:/app/uploads \
    -v ${SCRIPT_DIR}/chroma_db:/app/chroma_db \
    -e SECRET_KEY="$(openssl rand -hex 32 2>/dev/null || echo change-me-$(date +%s))" \
    -e ADMIN_USERNAME="admin" \
    -e ADMIN_PASSWORD="admin123" \
    ${IMAGE_NAME}

echo -e "${GREEN} 容器已启动${NC}"

# 5. 验证
echo ""
echo -e "${YELLOW}[5/5] 验证服务...${NC}"
sleep 5

if docker exec ${CONTAINER_NAME} curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN} 后端服务正常${NC}"
else
    echo -e "${YELLOW} 后端正在初始化（可能需要下载 AI 模型），请稍候...${NC}"
    sleep 15
    if docker exec ${CONTAINER_NAME} curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN} 后端服务正常${NC}"
    else
        echo -e "${YELLOW} 后端仍在启动中，可通过 docker logs ${CONTAINER_NAME} 查看进度${NC}"
    fi
fi

# 完成
echo ""
echo "=========================================="
echo -e "${GREEN} 部署完成！${NC}"
echo ""
echo "  访问地址："
echo "    http://你的服务器IP:${PORT}"
echo ""
echo "  默认账号："
echo "    管理员: admin / admin123"
echo ""
echo "  常用命令："
echo "    查看日志: docker logs -f ${CONTAINER_NAME}"
echo "    重启服务: docker restart ${CONTAINER_NAME}"
echo "    停止服务: docker stop ${CONTAINER_NAME}"
echo "    更新部署: ./deploy-bt.sh"
echo ""
echo "  重要提醒："
echo "    首次访问请立即修改管理员密码！"
echo "    如使用宝塔 Nginx 反代，请配置域名指向 localhost:${PORT}"
echo "=========================================="
