# ==================== 阶段 1：构建前端 ====================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps

COPY frontend/ ./
RUN npm run build


# ==================== 阶段 2：运行环境 ====================
FROM python:3.11-slim

LABEL maintainer="luojianwei2006"
LABEL description="Customer Service Platform - All-in-One (Frontend + Backend)"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖（nginx + Playwright 浏览器依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    wget \
    gnupg \
    # Playwright 依赖
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    # 清理
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd -m -u 1000 -s /bin/bash appuser

WORKDIR /app

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 浏览器
RUN playwright install chromium && \
    playwright install-deps chromium

# 复制后端代码
COPY backend/ .

# 复制前端构建产物到 nginx 静态目录
RUN mkdir -p /var/www/html
COPY --from=frontend-builder /app/frontend/dist /var/www/html

# 创建必要目录
RUN mkdir -p /app/uploads /app/xhs_screenshots /app/chroma_db /app/logs /run/nginx \
    && chown -R appuser:appuser /app/uploads /app/xhs_screenshots /app/chroma_db /app/logs /run/nginx \
    && chown -R appuser:appuser /var/www/html

# 写入 nginx 配置
RUN echo 'server {\n\
    listen 80;\n\
    server_name localhost;\n\
    root /var/www/html;\n\
    index index.html;\n\
    client_max_body_size 100m;\n\
    gzip on;\n\
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
    location /api/ {\n\
        proxy_pass http://127.0.0.1:8000;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n\
        proxy_connect_timeout 60s;\n\
        proxy_read_timeout 300s;\n\
    }\n\
    location /ws/ {\n\
        proxy_pass http://127.0.0.1:8000;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header Upgrade $http_upgrade;\n\
        proxy_set_header Connection "upgrade";\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
        proxy_read_timeout 3600s;\n\
    }\n\
}' > /etc/nginx/sites-enabled/default

# 确保 nginx 日志目录可写
RUN chown -R appuser:appuser /var/log/nginx /var/lib/nginx

# 切换非 root 用户
USER appuser

EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:80/api/health || exit 1

# 启动脚本
COPY --chown=appuser:appuser docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

CMD ["/docker-entrypoint.sh"]
