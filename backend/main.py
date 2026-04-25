import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from models.models import Admin, SystemConfig
from utils.security import get_password_hash
from config import settings
from database import SessionLocal

# 导入路由
from routers import admin, tenant, knowledge, chat, feishu, wecom, points, xhs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库"""
    # 创建表
    Base.metadata.create_all(bind=engine)

    # 创建上传目录
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "xhs_materials"), exist_ok=True)

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


@app.get("/")
async def root():
    return {"message": "客服管理平台 API 运行正常", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
