from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """运行数据库迁移，确保新增列存在"""
    from sqlalchemy import text, inspect
    insp = inspect(engine)
    cols = [c["name"] for c in insp.get_columns("tenants")]
    if "dingtalk_webhook" not in cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE tenants ADD COLUMN dingtalk_webhook VARCHAR(500)"))
            conn.commit()
        print("✅ 数据库迁移: 已添加 tenants.dingtalk_webhook 列")
    if "dingtalk_secret" not in cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE tenants ADD COLUMN dingtalk_secret VARCHAR(200)"))
            conn.commit()
        print("✅ 数据库迁移: 已添加 tenants.dingtalk_secret 列")
