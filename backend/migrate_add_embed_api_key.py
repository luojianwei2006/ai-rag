"""
迁移脚本：为 tenants 表新增 embed_api_key 字段
"""
import sys
import os

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from database import engine
from models.models import Tenant
from sqlalchemy.orm import sessionmaker

def run_migration():
    """执行迁移"""
    # 检查字段是否已存在
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(tenants)"))
        columns = [row[1] for row in result.fetchall()]

        if "embed_api_key" in columns:
            print("✅ embed_api_key 字段已存在，跳过迁移")
            return

        # 添加字段（不带 UNIQUE 约束，SQLite 不支持）
        conn.execute(text("ALTER TABLE tenants ADD COLUMN embed_api_key VARCHAR(64)"))
        conn.commit()
        print("✅ 已添加 embed_api_key 字段到 tenants 表")

        # 创建唯一索引
        try:
            conn.execute(text("CREATE UNIQUE INDEX ix_tenants_embed_api_key ON tenants(embed_api_key)"))
            conn.commit()
            print("✅ 已创建 embed_api_key 唯一索引")
        except Exception as e:
            print(f"⚠️  创建唯一索引失败（可忽略）: {e}")
            conn.rollback()

    # 为现有商户生成 embed_api_key
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        import secrets
        tenants = db.query(Tenant).all()
        for t in tenants:
            if not t.embed_api_key:
                t.embed_api_key = secrets.token_urlsafe(32)
        db.commit()
        print(f"✅ 已为 {len(tenants)} 个商户生成 embed_api_key")
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
