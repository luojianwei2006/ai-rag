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
        # Ubuntu / Debian — 使用 deadsnakes PPA 安装 Python 3.11
        apt-get update -y
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update -y
        apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip
        PYTHON_CMD="python3.11"
    elif command -v yum &>/dev/null || command -v dnf &>/dev/null; then
        # CentOS / RHEL / Fedora
        PKG_MGR=$(command -v dnf 2>/dev/null || echo "yum")

        # 尝试安装高版本 Python
        if $PKG_MGR install -y python3.11 python3.11-pip python3.11-devel 2>/dev/null; then
            PYTHON_CMD="python3.11"
        elif $PKG_MGR install -y python3.10 python3.10-pip python3.10-devel 2>/dev/null; then
            PYTHON_CMD="python3.10"
        elif $PKG_MGR install -y python39 python39-pip python39-devel 2>/dev/null; then
            PYTHON_CMD="python3.9"
        else
            # 使用 IUS 源
            $PKG_MGR install -y epel-release 2>/dev/null || true
            curl -s https://setup.ius.io/ | bash 2>/dev/null || true
            $PKG_MGR install -y python311 python311-pip python311-devel 2>/dev/null || \
            $PKG_MGR install -y python39 python39-pip python39-devel 2>/dev/null || true
            # 检查安装结果
            for c in python3.11 python3.10 python3.9; do
                if command -v "$c" &>/dev/null; then
                    V=$($c -c "import sys; print(sys.version_info[:2])" 2>/dev/null)
                    if [ "$(echo $V | cut -d, -f2)" -ge 9 ] 2>/dev/null; then
                        PYTHON_CMD="$c"
                        break
                    fi
                fi
            done
        fi
    fi

    if [ -z "$PYTHON_CMD" ] || ! command -v "$PYTHON_CMD" &>/dev/null; then
        error "自动安装 Python 3.9+ 失败。

  Ubuntu/Debian 请执行：
    apt install software-properties-common
    add-apt-repository ppa:deadsnakes/ppa
    apt install python3.11 python3.11-venv python3.11-pip

  CentOS 7 请执行：
    yum install epel-release
    yum install https://repo.ius.io/ius-release-el7.rpm
    yum install python311 python311-pip python311-devel

  CentOS 8/Rocky/Alma 请执行：
    dnf install python3.11 python3.11-pip python3.11-devel

  安装完成后重新运行: ./install-bt.sh"
    fi

    VER=$("$PYTHON_CMD" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null)
    success "Python $VER 安装完成 ($PYTHON_CMD)"
fi

# ==================== 第 2 步：检测 Node.js ====================
echo ""
echo "[2/7] 检测 Node.js 环境..."

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
echo "[3/7] 安装 Python 依赖..."

cd "$BACKEND_DIR"

# 创建虚拟环境（如果已存在，检查 Python 版本是否匹配）
NEED_RECREATE=false
if [ -d ".venv" ]; then
    VENV_PYTHON_VER=$(.venv/bin/python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null || echo "0.0")
    VENV_MAJOR=$(echo "$VENV_PYTHON_VER" | cut -d. -f1)
    VENV_MINOR=$(echo "$VENV_PYTHON_VER" | cut -d. -f2)
    if [ "$VENV_MAJOR" -lt 3 ] || ([ "$VENV_MAJOR" -eq 3 ] && [ "$VENV_MINOR" -lt 9 ]); then
        warn "旧虚拟环境 Python $VENV_PYTHON_VER 版本过低，重新创建..."
        rm -rf .venv
        NEED_RECREATE=true
    else
        info "虚拟环境已存在（Python $VENV_PYTHON_VER）"
    fi
fi
if [ ! -d ".venv" ]; then
    info "创建 Python 虚拟环境..."
    $PYTHON_CMD -m venv .venv
    NEED_RECREATE=true
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

# 强制清除所有 pip 镜像配置（宝塔可能自动配置了残缺镜像源）
rm -f /root/.config/pip/pip.conf
rm -f /etc/pip.conf
pip config unset global.index-url 2>/dev/null || true
pip config unset global.trusted-host 2>/dev/null || true
pip config unset global.timeout 2>/dev/null || true

info "pip 配置已清理，当前配置：$(pip config list 2>/dev/null || echo '无自定义配置，使用默认')"

# 安装依赖
info "安装 Python 依赖包（首次约 5-15 分钟）..."

if pip install -r requirements.txt --timeout 180; then
    success "Python 依赖安装完成（官方 PyPI）"
else
    warn "官方 PyPI 安装失败，可能是网络问题"
    echo ""
    echo "======================================================"
    warn "服务器无法访问 PyPI 官方源，请选择以下方法之一："
    echo ""
    echo "  方法1 - 如果服务器有代理，设置后重试："
    echo "    export http_proxy=http://代理地址:端口"
    echo "    export https_proxy=http://代理地址:端口"
    echo "    ./install-bt.sh"
    echo ""
    echo "  方法2 - 分步手动安装（先装大包再装剩余）："
    echo "    cd backend && source .venv/bin/activate"
    echo "    pip install langchain-community langchain langchain-openai langchain-google-genai"
    echo "    pip install chromadb sentence-transformers"
    echo "    pip install -r requirements.txt"
    echo ""
    echo "  方法3 - 检查服务器是否能访问外网："
    echo "    curl -I https://pypi.org/simple/"
    echo ""
    echo "======================================================"
    exit 1
fi

deactivate

# ==================== 第 4 步：构建前端 ====================
echo ""
echo "[4/7] 构建前端..."

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
echo "[5/7] 配置环境变量..."

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
echo "[6/7] 安装系统服务..."

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

# ==================== 配置 Nginx + 注册到宝塔面板 ====================
echo ""
echo "[7/7] 配置 Nginx 站点..."

BT_VHOST_DIR="/www/server/nginx/conf/vhost"
BT_NGINX_BIN="/www/server/nginx/sbin/nginx"
BT_PANEL_DB="/www/server/panel/data/db/site.db"
BT_SITE_ID=""

# 判断是否是宝塔环境
if [ -d "$BT_VHOST_DIR" ] && [ -f "$BT_NGINX_BIN" ]; then
    info "检测到宝塔面板环境"

    # 复制配置到宝塔 vhost 目录
    DEST_CONF="$BT_VHOST_DIR/${APP_NAME}.conf"
    cp "$NGINX_CONF_PATH" "$DEST_CONF"
    success "Nginx 配置已写入：$DEST_CONF"

    # 注册站点到宝塔面板数据库（让宝塔网站列表可见）
    if [ -f "$BT_PANEL_DB" ] && command -v sqlite3 &>/dev/null; then
        info "注册站点到宝塔面板..."

        # 获取服务器 IP 作为默认域名
        SERVER_IP=$(curl -s --connect-timeout 3 ifconfig.me 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
        SITE_DOMAIN="${SERVER_IP}:${PORT_FRONTEND}"
        SITE_PATH="$FRONTEND_DIR/dist"
        CREATE_TIME=$(date +%Y-%m-%d" "%H:%M:%S)

        # 检查是否已存在
        EXIST_ID=$(sqlite3 "$BT_PANEL_DB" "SELECT id FROM sites WHERE name='${APP_NAME}';" 2>/dev/null)

        if [ -n "$EXIST_ID" ]; then
            # 更新现有记录
            sqlite3 "$BT_PANEL_DB" "UPDATE sites SET path='${SITE_PATH}', ps='AI客服平台', edate=$(date +%s) WHERE id=${EXIST_ID};" 2>/dev/null
            BT_SITE_ID="$EXIST_ID"
            success "站点已更新（ID: $EXIST_ID）"
        else
            # 获取当前最大 ID
            MAX_ID=$(sqlite3 "$BT_PANEL_DB" "SELECT MAX(id) FROM sites;" 2>/dev/null || echo "0")
            NEW_ID=$((MAX_ID + 1))

            # 获取当前时间戳
            NOW_TS=$(date +%s)

            # 插入新站点记录
            sqlite3 "$BT_PANEL_DB" << EOSQL 2>/dev/null
INSERT INTO sites (id, name, path, status, ps, addtime, edate) VALUES (${NEW_ID}, '${APP_NAME}', '${SITE_PATH}', 1, 'AI客服平台', ${NOW_TS}, ${NOW_TS});
EOSQL

            if [ $? -eq 0 ]; then
                BT_SITE_ID="$NEW_ID"
                success "站点已注册到宝塔面板（ID: $NEW_ID）"
            else
                warn "数据库写入失败，站点不会出现在宝塔列表中（但服务仍可正常访问）"
            fi
        fi

        # 写入站点域名记录
        if [ -n "$BT_SITE_ID" ]; then
            sqlite3 "$BT_PANEL_DB" "DELETE FROM domain WHERE pid=${BT_SITE_ID};" 2>/dev/null
            sqlite3 "$BT_PANEL_DB" "INSERT INTO domain (pid, name, port) VALUES (${BT_SITE_ID}, '${SERVER_IP}', '${PORT_FRONTEND}');" 2>/dev/null
        fi

    elif [ -f "$BT_PANEL_DB" ] && ! command -v sqlite3 &>/dev/null; then
        warn "缺少 sqlite3 命令，无法注册到宝塔面板"
        info "安装 sqlite3 后可手动执行注册："
        info "  yum install sqlite / apt install sqlite3"
    fi

    # 测试并重载 Nginx
    if $BT_NGINX_BIN -t 2>/dev/null; then
        $BT_NGINX_BIN -s reload
        success "宝塔 Nginx 已重载"
    else
        warn "Nginx 配置测试失败，请手动检查：$DEST_CONF"
    fi

    echo ""
    echo "================================================"
    echo -e "${GREEN}  ✅ 安装完成！${NC}"
    echo "================================================"
    echo ""
    echo "  🌐 访问地址：http://${SERVER_IP:-服务器IP}:${PORT_FRONTEND}"
    echo "  🔧 管理后台：http://${SERVER_IP:-服务器IP}:${PORT_FRONTEND}/admin/login"
    echo "  👤 账号：$ADMIN_USER  密码：$ADMIN_PASS"
    echo ""
    if [ -n "$BT_SITE_ID" ]; then
        echo "  📋 宝塔面板查看："
        echo "     左侧菜单 → 网站 → 列表中可看到「${APP_NAME}」"
    else
        echo "  📋 宝塔面板："
        echo "     站点未注册到面板列表，但服务正常运行"
        echo "     Nginx 配置文件：$DEST_CONF"
    fi
    echo ""
    echo "  ⚙️  后端服务管理："
    echo "     查看日志：tail -f $APP_DIR/backend/server.log"
    echo "     重启服务：systemctl restart $APP_NAME"
    echo "     停止服务：systemctl stop $APP_NAME"
    echo "     查看状态：systemctl status $APP_NAME"
    echo ""
    echo "  ⚠️  请登录后台后立即修改管理员密码！"
    echo ""
    echo "  💡 绑定域名：网站 → 点击站点名 → 域名管理 → 添加域名"
    echo "================================================"

else
    # 非宝塔环境
    NGINX_AVAILABLE_DIR=""
    for d in /etc/nginx/conf.d /etc/nginx/sites-available; do
        if [ -d "$d" ]; then
            NGINX_AVAILABLE_DIR="$d"
            break
        fi
    done

    if [ -n "$NGINX_AVAILABLE_DIR" ]; then
        cp "$NGINX_CONF_PATH" "$NGINX_AVAILABLE_DIR/${APP_NAME}.conf"
        nginx -t 2>/dev/null && nginx -s reload
        success "Nginx 配置已写入并重载"
    else
        warn "未找到 Nginx，请手动安装并配置"
        warn "Nginx 配置文件：$NGINX_CONF_PATH"
    fi

    echo ""
    echo "================================================"
    echo -e "${GREEN}  ✅ 安装完成！${NC}"
    echo "================================================"
    echo ""
    echo "  🌐 访问地址：http://服务器IP:$PORT_FRONTEND"
    echo "  🔧 管理后台：http://服务器IP:$PORT_FRONTEND/admin/login"
    echo "  👤 账号：$ADMIN_USER  密码：$ADMIN_PASS"
    echo ""
    echo "  ⚙️  常用命令："
    echo "     查看日志：tail -f $APP_DIR/backend/server.log"
    echo "     重启服务：systemctl restart $APP_NAME"
    echo "     停止服务：systemctl stop $APP_NAME"
    echo "     查看状态：systemctl status $APP_NAME"
    echo ""
    echo "  ⚠️  请登录后台后立即修改管理员密码！"
    echo "================================================"
fi
