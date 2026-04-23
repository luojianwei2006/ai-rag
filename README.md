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
├── install-bt.sh            # 宝塔原生一键安装（推荐）
├── update-bt.sh             # 宝塔原生一键更新
├── uninstall-bt.sh          # 宝塔原生卸载
├── bt-nginx.conf            # Nginx 配置（安装时自动生成）
├── Dockerfile               # Docker 镜像构建
├── docker-compose.yml       # Docker Compose 配置
├── docker-entrypoint.sh     # 容器启动脚本
├── deploy-bt.sh             # 宝塔 Docker 一键部署
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
# 拷贝打包产物到 Nginx 目录
cp -r dist /var/www/customer-service
```

#### 3. 启动后端

```bash
cd customer-service-platform/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 生产启动
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

# 重启后端
kill $(pgrep -f "uvicorn.*main:app") && cd backend && nohup uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &

# 更新部署（拉取最新代码后）
cd frontend && npm run build && cp -r dist/* /var/www/customer-service/
```

---

## 宝塔原生部署（推荐，无需 Docker）

> 直接在宝塔面板上安装运行，性能更好、更省资源，适合绝大多数 VPS。

### 前提条件

| 要求 | 说明 |
|------|------|
| 操作系统 | CentOS 7+ / Ubuntu 18+ / Debian 10+ |
| 宝塔面板 | 已安装宝塔面板（[安装教程](https://www.bt.cn/new/download.html)） |
| Python | 3.9+（脚本自动安装） |
| Node.js | 16+（脚本自动安装） |
| Nginx | 宝塔面板已安装 Nginx（软件商店 → Nginx） |
| 内存 | 建议 2GB 以上（AI 模型需要） |

### 一键安装

#### 第 1 步：上传项目到服务器

**方式 A：从 GitHub 拉取（推荐）**
```bash
cd /www/wwwroot
git clone https://github.com/luojianwei2006/ai-rag.git customer-service
cd customer-service
```

**方式 B：宝塔面板上传**
1. 宝塔 → **文件** → 进入 `/www/wwwroot/`
2. 上传 `customer-service.zip` → 解压

#### 第 2 步：一键安装

```bash
cd /www/wwwroot/customer-service
chmod +x install-bt.sh
./install-bt.sh
```

安装过程中会提示填写：
- 管理员账号和密码
- 访问域名或 IP（用于生成客服链接）

**首次安装约需 5-15 分钟**（下载 Python 依赖 + 前端构建）。

#### 第 3 步：验证访问

安装完成后，浏览器打开：

```
http://服务器IP:8001
```

- 管理员后台：`http://服务器IP:8001/admin/login`
- 默认账号：安装时设置的账号密码
- **⚠️ 请登录后立即修改密码！**

#### 第 4 步：配置域名（可选）

1. **域名解析**：添加 A 记录指向服务器 IP
2. **在宝塔面板添加域名**：
   - 网站 → 点击「customer-service」→ 域名管理 → 添加域名
   - 添加后 Nginx 配置的 `server_name` 行会自动更新
3. **如需修改 Nginx 配置**：点击站点 → 配置文件
   - 安装时已自动生成配置，通常无需手动修改
   - 配置中已预留 `#SSL-START` / `#SSL-END` 标记，申请 SSL 证书时宝塔会自动填充
4. **申请 SSL**（推荐）：站点 → SSL → Let's Encrypt → 申请 → 开启强制 HTTPS

> **💡 提示**：安装脚本会自动使用服务器 IP 作为默认 `server_name`，在宝塔面板添加域名时会自动追加到 `server_name` 行中，无需手动修改配置文件。

---

### 宝塔原生部署常用命令

| 操作 | 命令 |
|------|------|
| 查看服务状态 | `systemctl status customer-service` |
| 重启后端 | `systemctl restart customer-service` |
| 停止后端 | `systemctl stop customer-service` |
| 查看日志 | `tail -f /www/wwwroot/customer-service/backend/server.log` |
| 更新部署 | `./update-bt.sh` |
| 卸载服务 | `./uninstall-bt.sh` |

---

### 脚本说明

| 脚本 | 说明 |
|------|------|
| `install-bt.sh` | **一键安装**：检测环境、安装依赖、构建前端、配置 systemd、配置 Nginx |
| `update-bt.sh` | **一键更新**：拉取新代码、更新依赖、重新构建、重启服务 |
| `uninstall-bt.sh` | **卸载服务**：停止服务、删除 systemd 和 Nginx 配置（数据目录保留） |
| `bt-nginx.conf` | **Nginx 配置**：安装时自动生成，可直接用于宝塔站点配置 |

---

## Docker 部署（宝塔一键部署）

### 方式一：宝塔面板从零部署（推荐，最详细）

> 适合零基础用户，从一台空服务器到上线只需 6 步。

#### 第 1 步：安装宝塔面板

```bash
# CentOS / RHEL
yum install -y wget && wget -O install.sh https://download.bt.cn/install/install_6.0.sh && sh install.sh ed8484bec

# Ubuntu / Debian
wget -O install.sh https://download.bt.cn/install/install-ubuntu_6.0.sh && bash install.sh ed8484bec
```

安装完成后，记录宝塔面板的访问地址、账号、密码。

#### 第 2 步：宝塔面板安装 Docker

1. 浏览器打开宝塔面板地址
2. 登录后进入 **软件商店**
3. 搜索 **Docker** → 安装 **Docker管理器**
4. 等待安装完成（约 1-3 分钟）

#### 第 3 步：上传项目文件

**方式 A：宝塔面板上传**
1. 宝塔面板 → **文件** → 进入 `/www/wwwroot/`
2. 点击 **上传** → 选择 `customer-service-platform.zip`（先在本地把项目打包为 zip）
3. 上传完成后右键 → **解压**

**方式 B：命令行上传（推荐）**
```bash
# 本地终端执行（把项目上传到服务器）
scp -r customer-service-platform/ root@你的服务器IP:/www/wwwroot/
```

**方式 C：从 GitHub 拉取（如果代码已推送到 GitHub）**
```bash
cd /www/wwwroot
git clone https://github.com/luojianwei2006/ai-rag.git customer-service-platform
```

#### 第 4 步：一键部署

```bash
cd /www/wwwroot/customer-service-platform
chmod +x deploy-bt.sh
./deploy-bt.sh
```

脚本会自动完成：
- 检查 Docker 环境
- 停止旧容器（如果存在）
- 构建镜像（首次约 5-15 分钟，需下载依赖 + 下载 AI 模型）
- 启动容器
- 验证服务

看到 `部署完成！` 即表示成功。

#### 第 5 步：验证访问

浏览器打开 `http://你的服务器IP:8001`

- 管理员后台：`http://你的服务器IP:8001/admin/login`
- 默认账号：`admin` / `admin123`
- **请登录后立即修改密码！**

#### 第 6 步：配置域名（可选）

如果需要用域名访问（如 `cs.yourdomain.com`）：

1. **域名解析**：在域名服务商添加 A 记录指向服务器 IP
2. **宝塔添加站点**：
   - 宝塔 → **网站** → **添加站点**
   - 域名填写：`cs.yourdomain.com`
   - 其他保持默认 → 提交
3. **配置反向代理**：
   - 点击站点名 → **反向代理** → **添加反向代理**
   - 代理名称：`customer-service`
   - 目标 URL：`http://127.0.0.1:8001`
   - 发送域名：`$host`
   - 提交
4. **申请 SSL（可选）**：
   - 点击站点名 → **SSL** → **Let's Encrypt**
   - 勾选域名 → 申请 → 开启强制 HTTPS

配置完成后通过 `https://cs.yourdomain.com` 访问。

---

### 方式二：Docker Compose 部署

适合有 Docker 经验的用户：

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

---

### 方式三：手动 Docker 部署

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

---

### Docker 部署常用命令

| 操作 | 命令 |
|------|------|
| 查看日志 | `docker logs -f customer-service` |
| 重启服务 | `docker restart customer-service` |
| 停止服务 | `docker stop customer-service` |
| 删除容器 | `docker rm -f customer-service` |
| 更新部署 | `./deploy-bt.sh`（重新构建+启动） |
| 进入容器 | `docker exec -it customer-service bash` |
| 查看状态 | `docker ps \| grep customer-service` |

---

### Docker 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SECRET_KEY` | JWT 密钥（务必修改！） | 随机生成 |
| `ADMIN_USERNAME` | 管理员账号 | admin |
| `ADMIN_PASSWORD` | 管理员密码（务必修改！） | admin123 |
| `FRONTEND_URL` | 前端地址（客服链接用） | 空 |

---

### 数据持久化

Docker 部署会自动将以下目录挂载到宿主机，**重装/更新容器不会丢失数据**：

| 容器路径 | 宿主机路径 | 说明 |
|----------|-----------|------|
| `/app/data` | `./data` | 数据库文件 |
| `/app/uploads` | `./uploads` | 用户上传的知识库文件 |
| `/app/chroma_db` | `./chroma_db` | 向量数据库 |

---

### 常见问题

**Q: 首次构建很慢？**
A: 需要下载 Python 依赖和 AI 模型（sentence-transformers），国内服务器建议配置 Docker 镜像加速：

```bash
# 配置 Docker 镜像加速
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
A: 修改 `deploy-bt.sh` 中的 `PORT=8001` 为其他端口，或使用 `docker run -p 其他端口:80`。

**Q: 如何备份数据？**
A: 备份宿主机上的三个目录即可：
```bash
tar -czf backup-$(date +%Y%m%d).tar.gz data/ uploads/ chroma_db/
```

**Q: 如何迁移到另一台服务器？**
A: 打包整个项目目录（含数据）传到新服务器，执行 `./deploy-bt.sh` 即可。
