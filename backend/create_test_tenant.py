#!/usr/bin/env python3
"""创建测试商户"""
import sys
sys.path.insert(0, '/Users/luojianwei/WorkBuddy/20260411104248/customer-service-platform/backend')

from database import SessionLocal
from models.models import Tenant
from utils.security import get_password_hash
import secrets

db = SessionLocal()
try:
    # 检查是否已存在
    existing = db.query(Tenant).filter(Tenant.id == 1).first()
    if existing:
        print(f"✅ 测试商户已存在: ID={existing.id}, email={existing.email}")
    else:
        # 创建测试商户
        tenant = Tenant(
            id=1,
            email="test@example.com",
            company_name="测试公司",
            hashed_password=get_password_hash("test123"),
            chat_token=secrets.token_hex(16),
            is_active=True,
            feishu_enabled=True,
            feishu_app_id="test_app_id",
            feishu_app_secret="test_app_secret"
        )
        db.add(tenant)
        db.commit()
        print(f"✅ 测试商户已创建: ID={tenant.id}, email={tenant.email}")
        print(f"   chat_token: {tenant.chat_token}")
finally:
    db.close()
