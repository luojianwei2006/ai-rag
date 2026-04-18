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
└── start.sh                 # 一键启动
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
