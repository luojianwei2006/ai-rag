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

- **后端**: Python 3.9+ / FastAPI / SQLAlchemy / ChromaDB
- **前端**: Vue 3 / TDesign / Vite
- **RAG**: ChromaDB 向量数据库
- **大模型**: 智谱GLM / OpenAI ChatGPT / Google Gemini / 自定义 OpenAI 兼容
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
| Python | >= 3.9 |
| Node.js | >= 16（仅本地构建前端，服务器不需要） |

> **⚠️ ChromaDB 需要 sqlite3 >= 3.35.0**，已通过 `pysqlite3-binary` 自动兼容，无需手动升级。

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

## 部署方式

| 方式 | 适用场景 |
|------|----------|
| **宝塔面板** ⭐ | 有宝塔面板的服务器（Amazon Linux 2 / CentOS） |
| **Docker** | 任意支持 Docker 的服务器 |
| **手动部署** | 裸机部署（Nginx + Uvicorn） |

---

## 宝塔面板部署（推荐）

### 环境说明

- **服务器**: Amazon Linux 2 / CentOS 7+
- **面板**: 宝塔面板（需安装 Python项目管理器）
- **前端**: 本地 `npm run build` → 上传 dist 到网站根目录
- **后端**: 宝塔 Python项目管理器 托管

### 第一步：安装宝塔 Python 项目管理器

1. 宝塔面板 → 软件商店 → 搜索「Python项目管理器」→ 安装
2. 安装后在「版本管理」中安装 Python 3.9+

### 第二步：部署后端

1. **拉取代码到服务器**
```bash
cd /www/git
git clone https://github.com/luojianwei2006/ai-rag.git
cd ai-rag
```

2. **宝塔创建项目**
   - 打开 Python项目管理器 → 添加项目
   - 填写：

| 字段 | 值 |
|------|-----|
| 项目路径 | `/www/git/ai-rag/backend` |
| Python版本 | 3.9+ |
| 框架 | `python` |
| 启动方式 | `自定义` |
| 自定义启动方式 | `<虚拟环境路径>/bin/python3.9 -m uvicorn main:app --host 0.0.0.0 --port 8000` |
| 端口 | `8000` |
| 是否安装依赖 | ✅ 勾选 |

> 虚拟环境路径在项目创建后自动生成，类似 `/www/git/ai-rag/backend/xxxx_venv/`

3. **手动安装缺失包（如有需要）**
```bash
cd /www/git/ai-rag/backend
<虚拟环境路径>/bin/pip install pysqlite3-binary
```

### 第三步：部署前端

```bash
# 在本地 Mac/PC 执行
cd customer-service-platform/frontend
npm install --legacy-peer-deps
npm run build

# 上传到服务器网站根目录
scp -r dist/* root@你的服务器IP:/www/wwwroot/kefu.zenithgames.com/
```

### 第四步：配置 Nginx（宝塔面板内）

宝塔 → 网站 → 你的站点 → 配置文件，在 `server {}` 块中添加（放在 `#SSL-END` 之后，`#ERROR-PAGE-START` 之前）：

```nginx
    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }

    # WebSocket 代理
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
    }

    # 静态文件（头像等上传资源）
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_cache_valid 200 1d;
        add_header Cache-Control "public, max-age=86400";
    }

    # 前端 SPA
    location / {
        try_files $uri $uri/ /index.html;
    }
```

保存后会自动重载 Nginx。

### 踩坑记录

| 问题 | 原因 | 解决 |
|------|------|------|
| `??=` 语法报错 | 服务器 Node.js 太老 | 本地构建 dist 上传，不在服务器跑 npm |
| Python SSL 不可用 | Python 3.14.2 缺 SSL | 用宝塔 Python 项目管理器安装的 Python 3.9 |
| `langchain-community` 装不上 | Python 版本太低 | 升级 Python ≥ 3.9 |
| 磁盘撑满 | langchain/sentence-transformers 吃空间 | 精简 requirements.txt，节省 3GB+ |
| `sqlite3 >= 3.35` 报错 | Amazon Linux 2 sqlite 3.7 太旧 | `pysqlite3-binary` 替换 |
| gunicorn 报错 `missing 'send'` | FastAPI 是 ASGI | gunicorn 配置 `worker_class = 'uvicorn.workers.UvicornWorker'` |

---

## 手动部署

### 前端

```bash
cd frontend
npm install && npm run build
cp -r dist/* /var/www/html/
```

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Nginx 配置

参考上方宝塔部署的 Nginx 配置块。

---

## 开发命令

```bash
# 本地启动
./startup.sh

# 本地构建前端
cd frontend && npm install --legacy-peer-deps && npm run build

# 一键关闭
./shutdown.sh
```

## 常用运维

```bash
# 宝塔 → 重启项目（图形界面操作）
# 或命令行
ps aux | grep uvicorn
kill <PID>

# 更新部署
cd frontend && npm run build && scp -r dist/* root@服务器IP:/www/wwwroot/kefu.zenithgames.com/
cd /www/git/ai-rag && git pull  # 服务器上拉取后端最新代码
```

---

## Docker 部署

项目提供完整的 Docker 支持，推荐用 `docker compose` 一键部署前后端。

### 前置准备

```bash
cd customer-service-platform

# 1. 创建后端环境变量文件（如果没有）
cp backend/.env.example backend/.env
# 编辑 backend/.env，填写必要的配置（SECRET_KEY、OPENAI_API_KEY 等）

# 2. 确认 docker-compose.yml 中的端口和路径
```

### 方式一：Docker Compose 部署（✅ 推荐）

```bash
cd customer-service-platform

# 构建并启动（首次约 10-20 分钟，需要下载依赖和 Playwright 浏览器）
docker compose up -d --build

# 查看日志
docker compose logs -f

# 查看服务状态
docker compose ps

# 停止服务
docker compose down

# 停止并删除数据卷（⚠️ 会删除数据库和上传文件）
docker compose down -v

# 重新构建（代码更新后）
docker compose down
docker compose up -d --build
```

访问地址：
- 前端：`http://localhost:80`
- 后端 API 文档：`http://localhost:8000/docs`

### 方式二：手动构建并运行

#### 后端

```bash
cd customer-service-platform/backend

# 构建后端镜像
docker build -t customer-service-backend:latest .

# 运行后端容器
docker run -d \
  --name customer-service-backend \
  --restart unless-stopped \
  -p 8000:8000 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/xhs_screenshots:/app/xhs_screenshots \
  -v $(pwd)/chroma_db:/app/chroma_db \
  -v $(pwd)/platform.db:/app/platform.db \
  --env-file .env \
  customer-service-backend:latest

# 查看日志
docker logs -f customer-service-backend
```

#### 前端

```bash
cd customer-service-platform/frontend

# 构建前端镜像
docker build -t customer-service-frontend:latest .

# 运行前端容器
docker run -d \
  --name customer-service-frontend \
  --restart unless-stopped \
  -p 80:80 \
  customer-service-frontend:latest

# 查看日志
docker logs -f customer-service-frontend
```

### 自定义配置

| 配置项 | 说明 | 修改位置 |
|--------|------|-----------|
| 后端端口 | 默认 8000 | `docker-compose.yml` 或 `docker run -p` |
| 前端端口 | 默认 80 | `docker-compose.yml` 或 `docker run -p` |
| 环境变量 | LLM 配置、密钥等 | `backend/.env` |
| Nginx 配置 | 前端路由、API 代理 | `frontend/docker/nginx.conf` |
| 健康检查 | 服务可用性检测 | `backend/Dockerfile` / `frontend/Dockerfile` |

### 常见问题

| 问题 | 解决方案 |
|------|-----------|
| Playwright 浏览器安装失败 | 检查 Dockerfile 中 `apt-get install` 的包是否完整 |
| ChromaDB 报错 sqlite3 版本低 | 使用 `python:3.11-slim` 镜像（已包含较新 sqlite3） |
| 前端访问后端 API 跨域 | 后端已配置 CORS，或配置 Nginx 反向代理 |
| 上传文件丢失 | 确保 `uploads/` 目录已挂载为数据卷 |

### 生产环境建议

```bash
# 1. 使用特定版本标签，不要用 latest
docker build -t customer-service-backend:v1.0.0 ./backend
docker build -t customer-service-frontend:v1.0.0 ./frontend

# 2. 使用外部数据库（PostgreSQL/MySQL）替代 SQLite
# 修改 backend/.env 中的 DATABASE_URL

# 3. 配置 HTTPS（在 Nginx 容器中配置 SSL 证书）
# 将证书挂载到 frontend 容器： -v ./ssl:/etc/nginx/ssl

# 4. 使用 Docker Swarm 或 Kubernetes 编排（多实例部署）
```

### Docker 部署常用命令

| 操作 | 命令 |
|------|------|
| 查看日志 | `docker compose logs -f` 或 `docker logs -f <容器名>` |
| 重启服务 | `docker compose restart` 或 `docker restart <容器名>` |
| 停止服务 | `docker compose down` 或 `docker stop <容器名>` |
| 删除容器 | `docker compose down` 或 `docker rm -f <容器名>` |
| 进入容器 | `docker exec -it <容器名> /bin/bash` |
| 查看状态 | `docker compose ps` 或 `docker ps \| grep customer-service` |

A: 使用 `docker run -p 其他端口:80` 修改映射端口。

**Q: 如何备份数据？**
A: 备份宿主机上的三个目录即可：
```bash
tar -czf backup-$(date +%Y%m%d).tar.gz data/ uploads/ chroma_db/
```

**Q: 如何迁移到另一台服务器？**
A: 打包整个项目目录（含数据）传到新服务器，重新 `docker compose up -d --build` 即可。
