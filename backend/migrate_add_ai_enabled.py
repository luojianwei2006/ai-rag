"""
迁移脚本：为 tenants 表新增 ai_enabled 字段
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "platform.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查列是否已存在
    cursor.execute("PRAGMA table_info(tenants)")
    columns = [row[1] for row in cursor.fetchall()]

    if "ai_enabled" not in columns:
        cursor.execute("ALTER TABLE tenants ADD COLUMN ai_enabled BOOLEAN DEFAULT 1")
        conn.commit()
        print("✅ 已添加 ai_enabled 字段")
    else:
        print("ℹ️  ai_enabled 字段已存在，跳过")

    conn.close()

if __name__ == "__main__":
    migrate()
