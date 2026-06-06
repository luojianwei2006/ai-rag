# 替换系统 sqlite3 为新版本（Amazon Linux 2 兼容）
import sys
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from database import engine, Base
from models.models import Admin, SystemConfig
from utils.security import get_password_hash
from config import settings
from database import SessionLocal

# 导入路由
from routers import admin, tenant, knowledge, chat, feishu, wecom, points, xhs, embed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库"""
    # 创建表
    Base.metadata.create_all(bind=engine)

    # 创建上传目录
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "xhs_materials"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "avatars"), exist_ok=True)

    # 初始化管理员账户
    db = SessionLocal()
    try:
        existing_admin = db.query(Admin).first()
        if not existing_admin:
            admin_user = Admin(
                username=settings.ADMIN_USERNAME,
                hashed_password=get_password_hash(settings.ADMIN_PASSWORD)
            )
            db.add(admin_user)
            db.commit()
            print(f"✅ 管理员账户已创建: {settings.ADMIN_USERNAME} / {settings.ADMIN_PASSWORD}")
        else:
            print(f"✅ 管理员账户已存在: {existing_admin.username}")
    finally:
        db.close()

    yield
    print("👋 服务关闭")


app = FastAPI(
    title="客服管理平台 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(admin.router)
app.include_router(tenant.router)
app.include_router(knowledge.router)
app.include_router(chat.router)
app.include_router(feishu.router)
app.include_router(wecom.router)
app.include_router(points.router)
app.include_router(xhs.router)
app.include_router(embed.router)

# 健康检查（放在 mount 前确保不被前端 SPA 拦截）
@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok"}

# 静态文件服务（头像等上传文件）
app.mount("/static", StaticFiles(directory=settings.UPLOAD_DIR), name="static")

# 前端静态文件（生产模式：直接由后端服务 Vue 打包产物）
frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    print(f"✅ 前端已挂载: {frontend_dist}")

    # SPA fallback：非 API 路径返回 index.html，让 Vue Router 处理前端路由
    index_html = os.path.join(frontend_dist, "index.html")
    @app.middleware("http")
    async def spa_fallback(request: Request, call_next):
        response = await call_next(request)
        if response.status_code == 404 and not request.url.path.startswith("/api") and not request.url.path.startswith("/ws"):
            if os.path.isfile(index_html):
                return FileResponse(index_html)
        return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
