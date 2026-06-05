#!/bin/bash
# 后端部署脚本 - 在服务器上运行
# 用法: sudo ./deploy-backend.sh
# 前提: 项目已上传到 /opt/customer-service-platform

set -e

PROJECT_DIR="/opt/customer-service-platform/backend"
SERVICE_NAME="customer-service-backend"
USER_NAME="${SUDO_USER:-ec2-user}"

echo "🐍 检查 Python 版本..."
python3 --version

echo "📦 安装 Python 依赖..."
cd "$PROJECT_DIR"

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "   创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境并安装依赖
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "📝 配置 systemd 服务..."
cat > /tmp/$SERVICE_NAME.service <<EOF
[Unit]
Description=Customer Service Platform Backend
After=network.target

[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo cp /tmp/$SERVICE_NAME.service /etc/systemd/system/$SERVICE_NAME.service
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "✅ 后端部署完成！"
echo "   查看状态: sudo systemctl status $SERVICE_NAME"
echo "   查看日志: sudo journalctl -u $SERVICE_NAME -f"
