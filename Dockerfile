# ==================== 构建阶段：前端 ====================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ==================== 运行阶段 ====================
FROM python:3.10-slim

WORKDIR /app

# 安装 nginx + 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 后端代码
COPY backend/ .

# 前端打包产物
COPY --from=frontend-builder /app/frontend/dist /app/static

# 创建必要目录
RUN mkdir -p /app/uploads /app/chroma_db /app/data /run/nginx

# Nginx 配置
RUN cat > /etc/nginx/sites-available/default << 'EOF'
server {
    listen 80;
    server_name _;

    root /app/static;
    index index.html;

    client_max_body_size 100m;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }
}
EOF

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    UPLOAD_DIR=/app/uploads \
    CHROMA_PERSIST_DIR=/app/chroma_db \
    SECRET_KEY=change-me-in-production \
    ADMIN_USERNAME=admin \
    ADMIN_PASSWORD=admin123

# 数据持久化
VOLUME ["/app/data", "/app/uploads", "/app/chroma_db"]

EXPOSE 80

# 启动脚本
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

CMD ["/docker-entrypoint.sh"]
