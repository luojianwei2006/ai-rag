# 第一阶段：构建前端
FROM node:20-alpine AS builder

LABEL maintainer="luojianwei2006"
LABEL description="Customer Service Platform Frontend Builder"

# 设置工作目录
WORKDIR /app

# 复制 package.json 和 package-lock.json
COPY package*.json ./

# 安装依赖
RUN npm install --legacy-peer-deps

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# 第二阶段：运行前端（Nginx）
FROM nginx:alpine

LABEL maintainer="luojianwei2006"
LABEL description="Customer Service Platform Frontend - Nginx"

# 复制自定义 Nginx 配置
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# 从构建阶段复制静态文件
COPY --from=builder /app/dist /usr/share/nginx/html

# 创建非 root 用户
RUN adduser -D -u 1000 appuser && \
    chown -R appuser:appuser /usr/share/nginx/html && \
    chown -R appuser:appuser /var/log/nginx && \
    chown -R appuser:appuser /var/lib/nginx && \
    chmod -R 755 /usr/share/nginx/html

# 切换非 root 用户
USER appuser

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:80 || exit 1

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]
