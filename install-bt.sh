#!/bin/bash
# ============================================================
# AI 客服平台 - 宝塔面板一键安装脚本（无需 Docker）
# 适用系统：CentOS 7+  / Ubuntu 18+ / Debian 10+
# 使用方式：chmod +x install-bt.sh && ./install-bt.sh
# ============================================================

set -e

# ==================== 颜色输出 ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}  $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ==================== 配置（可按需修改）====================
APP_NAME="customer-service"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"    # 脚本所在目录即项目根目录
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
PORT_BACKEND=8000                            # 后端 uvicorn 端口
PORT_FRONTEND=8001                           # Nginx 对外端口
PYTHON_MIN="3.9"

# ==================== 读取用户配置 ====================
echo ""
echo "================================================"
echo "   AI 客服平台 - 宝塔一键安装脚本"
echo "================================================"
echo ""

read -p "请输入管理员账号 [默认 admin]: " INPUT_ADMIN_USER
ADMIN_USER=${INPUT_ADMIN_USER:-admin}

read -s -p "请输入管理员密码 [默认 admin123]: " INPUT_ADMIN_PASS
echo ""
ADMIN_PASS=${INPUT_ADMIN_PASS:-admin123}

read -p "请输入访问域名或IP（用于生成前端链接，如 http://your-domain.com）[默认 http://localhost:$PORT_FRONTEND]: " INPUT_FRONTEND_URL
FRONTEND_URL=${INPUT_FRONTEND_URL:-"http://localhost:$PORT_FRONTEND"}

echo ""
info "项目目录：$APP_DIR"
info "后端端口：$PORT_BACKEND"
info "前端端口：$PORT_FRONTEND"
info "管理员账号：$ADMIN_USER"
info "前端地址：$FRONTEND_URL"
echo ""
read -p "确认以上配置？回车继续，Ctrl+C 取消..." _

# ==================== 第 1 步：检测 Python ====================
echo ""
echo "[1/6] 检测 Python 环境..."

PYTHON_CMD=""
for cmd in python3.11 python3.10 python3.9 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null)
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
            PYTHON_CMD="$cmd"
            success "找到 Python $VER ($cmd)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    warn "未找到 Python 3.9+，尝试自动安装..."
    if command -v apt-get &>/dev/null; then
        apt-get update -y && apt-get install -y python3 python3-pip python3-venv
        PYTHON_CMD="python3"
    elif command -v yum &>/dev/null; then
        yum install -y python3 python3-pip
        PYTHON_CMD="python3"
    else
        error "无法自动安装 Python，请手动安装 Python 3.9+ 后重试"
    fi
fi

# ==================== 第 2 步：检测 Node.js ====================
echo ""
echo "[2/6] 检测 Node.js 环境..."

NODE_CMD=""
NPM_CMD=""

if command -v node &>/dev/null; then
    NODE_VER=$(node --version 2>/dev/null)
    NODE_MAJOR=$(echo "$NODE_VER" | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 16 ]; then
        NODE_CMD="node"
        NPM_CMD="npm"
        success "找到 Node.js $NODE_VER"
    else
        warn "Node.js 版本过低（$NODE_VER），需要 v16+，尝试升级..."
    fi
fi

if [ -z "$NODE_CMD" ]; then
    warn "未找到合适的 Node.js，尝试自动安装 Node.js 20..."
    if command -v apt-get &>/dev/null; then
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs
    elif command -v yum &>/dev/null; then
        curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
        yum install -y nodejs
    else
        error "无法自动安装 Node.js，请手动安装 Node.js 16+ 后重试"
    fi
    NODE_CMD="node"
    NPM_CMD="npm"
    success "Node.js 安装完成：$(node --version)"
fi

# ==================== 第 3 步：安装 Python 依赖 ====================
echo ""
echo "[3/6] 安装 Python 依赖..."

cd "$BACKEND_DIR"

# 创建虚拟环境
if [ ! -d ".venv" ]; then
    info "创建 Python 虚拟环境..."
    $PYTHON_CMD -m venv .venv
fi

# 激活虚拟环境
source .venv/bin/activate
success "虚拟环境已激活"

# 升级 pip
pip install --upgrade pip -q

# 安装依赖（先用官方源，失败再切换国内镜像）
info "安装 Python 依赖包（首次约 5-15 分钟）..."

# 先清除 pip 缓存，避免旧缓存干扰
pip cache purge -q 2>/dev/null || true

# 取消可能存在的全局镜像配置干扰
pip config unset global.index-url 2>/dev/null || true

MIRRORS=(
    ""                                              # 官方 PyPI（默认，不指定镜像）
    "-i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com"
    "-i https://pypi.mirrors.ustc.edu.cn/simple --trusted-host pypi.mirrors.ustc.edu.cn"
    "-i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn"
)
MIRROR_NAMES=("官方 PyPI" "阿里云" "中科大" "清华")

INSTALLED=false
for i in "${!MIRRORS[@]}"; do
    info "尝试 ${MIRROR_NAMES[$i]} ..."
    CMD="pip install -r requirements.txt --timeout 180 ${MIRRORS[$i]}"
    if eval $CMD; then
        success "Python 依赖安装完成（${MIRROR_NAMES[$i]}）"
        INSTALLED=true
        break
    else
        warn "${MIRROR_NAMES[$i]} 失败，切换下一个..."
    fi
done

if [ "$INSTALLED" = false ]; then
    error "所有源均失败，请检查网络连通性后重试，或手动执行：pip install -r requirements.txt"
fi

deactivate

# ==================== 第 4 步：构建前端 ====================
echo ""
echo "[4/6] 构建前端..."

cd "$FRONTEND_DIR"

info "安装前端依赖..."
# 多镜像源回退
npm install --registry=https://registry.npmmirror.com 2>/dev/null || \
npm install --registry=https://registry.npm.taobao.org 2>/dev/null || \
npm install

info "打包前端..."
npm run build
success "前端打包完成 → $FRONTEND_DIR/dist"

# ==================== 第 5 步：配置环境变量 ====================
echo ""
echo "[5/6] 配置环境变量..."

cd "$BACKEND_DIR"

cat > .env << EOF
DATABASE_URL=sqlite:///./data/platform.db
SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || $PYTHON_CMD -c "import secrets; print(secrets.token_hex(32))")
ADMIN_USERNAME=$ADMIN_USER
ADMIN_PASSWORD=$ADMIN_PASS
FRONTEND_URL=$FRONTEND_URL
UPLOAD_DIR=$BACKEND_DIR/uploads
CHROMA_PERSIST_DIR=$BACKEND_DIR/chroma_db
EOF

# 创建必要目录
mkdir -p "$BACKEND_DIR/uploads" "$BACKEND_DIR/chroma_db" "$BACKEND_DIR/data"
success "环境变量已写入 backend/.env"

# ==================== 第 6 步：安装系统服务 ====================
echo ""
echo "[6/6] 安装系统服务（systemd）..."

VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"
VENV_UVICORN="$BACKEND_DIR/.venv/bin/uvicorn"

# 写入 systemd service 文件
cat > /etc/systemd/system/${APP_NAME}.service << EOF
[Unit]
Description=AI Customer Service Platform Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$BACKEND_DIR/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$VENV_UVICORN main:app --host 127.0.0.1 --port $PORT_BACKEND --workers 2
Restart=always
RestartSec=5
StandardOutput=append:$APP_DIR/backend/server.log
StandardError=append:$APP_DIR/backend/server.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${APP_NAME}
systemctl restart ${APP_NAME}

# 检查服务状态
sleep 3
if systemctl is-active --quiet ${APP_NAME}; then
    success "后端服务启动成功（端口 $PORT_BACKEND）"
else
    warn "后端服务启动异常，查看日志："
    journalctl -u ${APP_NAME} -n 20 --no-pager
fi

# ==================== 生成 Nginx 配置 ====================
echo ""
info "生成 Nginx 配置文件..."

NGINX_CONF_PATH="$APP_DIR/bt-nginx.conf"
cat > "$NGINX_CONF_PATH" << EOF
# ============================================================
# AI 客服平台 Nginx 配置
# 生成时间：$(date)
# 使用方法：复制此配置到宝塔面板站点配置中
# ============================================================

server {
    listen $PORT_FRONTEND;
    server_name _;

    # 前端静态文件
    root $FRONTEND_DIR/dist;
    index index.html;

    client_max_body_size 100m;

    # SPA 路由支持
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # 后端 API 反向代理
    location /api {
        proxy_pass http://127.0.0.1:$PORT_BACKEND;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_connect_timeout 60s;
        proxy_read_timeout 300s;
    }

    # WebSocket 代理（客服聊天）
    location /ws {
        proxy_pass http://127.0.0.1:$PORT_BACKEND;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 3600s;
    }

    # 上传文件直接访问
    location /uploads {
        alias $BACKEND_DIR/uploads;
        expires 7d;
    }

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1024;
}
EOF

success "Nginx 配置已生成：$NGINX_CONF_PATH"

# ==================== 尝试自动配置 Nginx ====================
NGINX_AVAILABLE_DIR=""
for d in /etc/nginx/conf.d /etc/nginx/sites-available /www/server/nginx/conf/vhost; do
    if [ -d "$d" ]; then
        NGINX_AVAILABLE_DIR="$d"
        break
    fi
done

if [ -n "$NGINX_AVAILABLE_DIR" ]; then
    DEST_CONF="$NGINX_AVAILABLE_DIR/${APP_NAME}.conf"
    cp "$NGINX_CONF_PATH" "$DEST_CONF"
    success "Nginx 配置已复制到：$DEST_CONF"

    # 检测宝塔 nginx 还是系统 nginx
    if command -v bt &>/dev/null && [ -f "/www/server/nginx/sbin/nginx" ]; then
        /www/server/nginx/sbin/nginx -t 2>/dev/null && /www/server/nginx/sbin/nginx -s reload
        success "宝塔 Nginx 已重载"
    elif command -v nginx &>/dev/null; then
        nginx -t 2>/dev/null && nginx -s reload
        success "Nginx 已重载"
    fi
else
    warn "未找到 Nginx 配置目录，请手动配置 Nginx"
    warn "Nginx 配置文件已保存在：$NGINX_CONF_PATH"
fi

# ==================== 完成 ====================
echo ""
echo "================================================"
echo -e "${GREEN}  ✅ 安装完成！${NC}"
echo "================================================"
echo ""
echo "  访问地址：http://服务器IP:$PORT_FRONTEND"
echo "  管理员后台：http://服务器IP:$PORT_FRONTEND/admin/login"
echo "  账号：$ADMIN_USER  密码：$ADMIN_PASS"
echo ""
echo "  常用命令："
echo "    查看后端日志：tail -f $APP_DIR/backend/server.log"
echo "    重启后端：   systemctl restart $APP_NAME"
echo "    停止后端：   systemctl stop $APP_NAME"
echo "    查看状态：   systemctl status $APP_NAME"
echo ""
echo "  ⚠️  请登录后台后立即修改管理员密码！"
echo "================================================"
