# 客服管理平台

> 基于 AI + RAG 的多商户智能客服 SaaS 平台

## 功能概览

| 角色 | 功能 |
|------|------|
| **管理员** | 登录/改密、API Key配置（GLM/OpenAI/Gemini）、SMTP邮件配置、商户管理 |
| **商户** | 注册/登录/改密、知识库上传管理、问答测试、自定义API Key、实时客服监控、历史记录查看 |
| **客户** | 专属链接聊天、AI智能问答、一键转人工客服 |

## 快速启动

```bash
cd customer-service-platform
bash start.sh
```

## 技术栈

- **后端**: Python 3.10+ / FastAPI / SQLAlchemy / ChromaDB
- **前端**: Vue 3 / TDesign / Vite
- **RAG**: ChromaDB 向量数据库 + LangChain
- **大模型**: 智谱GLM / OpenAI ChatGPT / Google Gemini
- **实时通信**: WebSocket

## 目录结构

```
customer-service-platform/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置文件
│   ├── database.py          # 数据库连接
│   ├── models/models.py     # 数据库模型
│   ├── routers/             # API 路由
│   │   ├── admin.py         # 管理员接口
│   │   ├── tenant.py        # 商户接口
│   │   ├── knowledge.py     # 知识库接口
│   │   └── chat.py          # 聊天接口（含WebSocket）
│   ├── services/
│   │   ├── rag_service.py   # RAG核心
│   │   ├── llm_service.py   # 大模型调用
│   │   └── email_service.py # 邮件服务
│   └── utils/
│       ├── doc_parser.py    # 文档解析
│       └── security.py      # 认证安全
├── frontend/
│   └── src/views/
│       ├── admin/           # 管理员页面
│       ├── tenant/          # 商户页面
│       └── chat/            # 客户聊天页面
├── Dockerfile               # Docker 镜像构建
├── docker-compose.yml       # Docker Compose 配置
├── docker-entrypoint.sh     # 容器启动脚本
├── nginx.conf               # Docker 内部 Nginx 配置
├── start.sh                 # 一键启动
└── startup.sh               # 后台启动
```

## 访问地址

| 页面 | 地址 |
|------|------|
| 管理员后台 | http://localhost:5173/admin/login |
| 商户登录 | http://localhost:5173/login |
| 商户注册 | http://localhost:5173/register |
| API 文档 | http://localhost:8000/docs |

## 默认账号

- 管理员: `admin` / `admin123`（首次启动自动创建）
- 商户：通过注册页面注册，密码发到邮箱

## 客服链接格式

```
http://localhost:5173/chat/{chat_token}
```

每个商户注册后自动生成唯一的 `chat_token`，在商户后台的左侧菜单底部可复制完整链接。

## 人工客服触发词

客户输入以下关键词会自动转接人工：
- 人工、人工客服、转人工、真人、真人客服、找人工、要人工 等

## 环境要求

| 要求 | 版本 |
|------|------|
| Python | >= 3.10 |
| Node.js | >= 16 |
| sqlite3 | >= 3.35.0（**ChromaDB 强制要求**） |

> **⚠️ sqlite3 版本问题**：ChromaDB 要求 sqlite3 >= 3.35.0，部分系统自带的 sqlite3 版本过低。
> 检查方法：`python3 -c "import sqlite3; print(sqlite3.sqlite_version)"`
> 如果版本低于 3.35.0，需要编译安装新版 sqlite3：

```bash
# CentOS / Ubuntu 通用编译安装 sqlite3 3.45.0
cd /tmp
wget https://www.sqlite.org/2024/sqlite-autoconf-3450000.tar.gz
tar xzf sqlite-autoconf-3450000.tar.gz
cd sqlite-autoconf-3450000
./configure --prefix=/usr/local/sqlite3 --enable-fts5
make -j$(nproc) && make install

# 设置环境变量
export LD_LIBRARY_PATH=/usr/local/sqlite3/lib:$LD_LIBRARY_PATH
export CFLAGS="-I/usr/local/sqlite3/include"
export LDFLAGS="-L/usr/local/sqlite3/lib"

# 持久化（重启后生效）
echo 'export LD_LIBRARY_PATH=/usr/local/sqlite3/lib:$LD_LIBRARY_PATH' >> /etc/profile.d/sqlite3.sh
echo 'export CFLAGS="-I/usr/local/sqlite3/include"' >> /etc/profile.d/sqlite3.sh
echo 'export LDFLAGS="-L/usr/local/sqlite3/lib"' >> /etc/profile.d/sqlite3.sh

# 验证
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"

# 重要：安装新版 sqlite3 后，需要重建虚拟环境
rm -rf backend/.venv
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

## 环境变量配置（可选）

在 `backend/` 目录创建 `.env` 文件：

```env
DATABASE_URL=sqlite:///./platform.db
SECRET_KEY=your-custom-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-password
FRONTEND_URL=http://localhost:5173
```

---

## 打包与部署

### 一、本地开发

```bash
cd customer-service-platform

# 一键启动（前后端开发模式）
./startup.sh

# 关闭所有服务
./shutdown.sh
```

### 二、前端打包

```bash
cd frontend
npm install
npm run build
# 打包产物输出到 frontend/dist/
```

### 三、生产部署（Nginx + Uvicorn）

#### 1. 打包前端

```bash
cd customer-service-platform/frontend
npm install
npm run build
```

#### 2. 部署前端静态文件

```bash
cp -r dist /var/www/customer-service
```

#### 3. 启动后端

```bash
cd customer-service-platform/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 生产启动（使用 systemd 推荐见下方）
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```

#### 4. Nginx 配置

在 `/etc/nginx/conf.d/customer-service.conf` 中添加：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为实际域名或服务器 IP

    root /var/www/customer-service;
    index index.html;

    client_max_body_size 100m;

    # 前端路由（SPA）
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 反向代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 60s;
        proxy_read_timeout 300s;
    }

    # WebSocket 代理（客服聊天）
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
    }

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1024;

    # 上传文件直接访问
    location /uploads {
        alias /var/www/customer-service-backend/uploads;
        expires 7d;
    }

    access_log /var/log/nginx/customer-service.log;
    error_log /var/log/nginx/customer-service.error.log;
}
```

#### 5. 重载 Nginx

```bash
nginx -t          # 检查配置
nginx -s reload   # 重载配置
```

#### 6. 配置 systemd 服务（推荐）

```bash
cat > /etc/systemd/system/customer-service.service << 'EOF'
[Unit]
Description=AI Customer Service Platform Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/customer-service-platform/backend
Environment="PATH=/path/to/customer-service-platform/backend/.venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/path/to/customer-service-platform/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=append:/path/to/customer-service-platform/backend/server.log
StandardError=append:/path/to/customer-service-platform/backend/server.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable customer-service
systemctl start customer-service
```

> 将 `/path/to/customer-service-platform` 替换为实际路径。

### 四、部署验证

| 检查项 | 命令 / 地址 |
|--------|------------|
| 后端服务 | `curl http://localhost:8000/docs` |
| 前端页面 | 浏览器访问 `http://your-domain.com` |
| API 文档 | `http://your-domain.com/api/docs` |
| WebSocket | 客户聊天页面连接测试 |

### 五、常用运维命令

```bash
# 查看后端日志
tail -f backend/server.log

# systemctl 管理
systemctl status customer-service
systemctl restart customer-service
systemctl stop customer-service

# 手动管理（无 systemd）
kill $(pgrep -f "uvicorn.*main:app") && cd backend && nohup uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &

# 更新部署（拉取最新代码后）
cd frontend && npm run build && cp -r dist/* /var/www/customer-service/
```

---

## Docker 部署

### 方式一：Docker Compose 部署（推荐）

```bash
cd customer-service-platform

# 构建并启动（首次约 5-15 分钟）
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止服务
docker compose down

# 更新部署（拉取新代码后）
docker compose down
docker compose up -d --build
```

自定义配置：编辑 `docker-compose.yml`，修改端口、环境变量等。

### 方式二：手动 Docker 部署

```bash
cd customer-service-platform

# 1. 构建镜像（首次约 5-15 分钟）
docker build -t customer-service-img .

# 2. 启动容器
docker run -d \
    --name customer-service \
    --restart always \
    -p 8001:80 \
    -v $(pwd)/data:/app/data \
    -v $(pwd)/uploads:/app/uploads \
    -v $(pwd)/chroma_db:/app/chroma_db \
    -e SECRET_KEY="你的自定义密钥" \
    -e ADMIN_USERNAME="admin" \
    -e ADMIN_PASSWORD="admin123" \
    customer-service-img

# 3. 查看日志
docker logs -f customer-service
```

### Docker 部署常用命令

| 操作 | 命令 |
|------|------|
| 查看日志 | `docker logs -f customer-service` |
| 重启服务 | `docker restart customer-service` |
| 停止服务 | `docker stop customer-service` |
| 删除容器 | `docker rm -f customer-service` |
| 进入容器 | `docker exec -it customer-service bash` |
| 查看状态 | `docker ps \| grep customer-service` |

### Docker 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SECRET_KEY` | JWT 密钥（务必修改！） | 随机生成 |
| `ADMIN_USERNAME` | 管理员账号 | admin |
| `ADMIN_PASSWORD` | 管理员密码（务必修改！） | admin123 |
| `FRONTEND_URL` | 前端地址（客服链接用） | 空 |

### 数据持久化

Docker 部署会自动将以下目录挂载到宿主机，**重装/更新容器不会丢失数据**：

| 容器路径 | 宿主机路径 | 说明 |
|----------|-----------|------|
| `/app/data` | `./data` | 数据库文件 |
| `/app/uploads` | `./uploads` | 用户上传的知识库文件 |
| `/app/chroma_db` | `./chroma_db` | 向量数据库 |

### 常见问题

**Q: 首次构建很慢？**
A: 需要下载 Python 依赖和 AI 模型（sentence-transformers），国内服务器建议配置 Docker 镜像加速：

```bash
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'EOF'
{
    "registry-mirrors": [
        "https://mirror.ccs.tencentyun.com",
        "https://docker.mirrors.ustc.edu.cn"
    ]
}
EOF
systemctl restart docker
```

**Q: 端口 8001 被占用？**
A: 使用 `docker run -p 其他端口:80` 修改映射端口。

**Q: 如何备份数据？**
A: 备份宿主机上的三个目录即可：
```bash
tar -czf backup-$(date +%Y%m%d).tar.gz data/ uploads/ chroma_db/
```

**Q: 如何迁移到另一台服务器？**
A: 打包整个项目目录（含数据）传到新服务器，重新 `docker compose up -d --build` 即可。
