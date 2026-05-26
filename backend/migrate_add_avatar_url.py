#!/usr/bin/env python3
"""迁移脚本：为 tenants 表添加 avatar_url 字段"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "platform.db")


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查列是否已存在
    cursor.execute("PRAGMA table_info(tenants)")
    columns = [row[1] for row in cursor.fetchall()]

    if "avatar_url" not in columns:
        cursor.execute("ALTER TABLE tenants ADD COLUMN avatar_url VARCHAR(500)")
        conn.commit()
        print("✅ 已添加 avatar_url 字段到 tenants 表")
    else:
        print("ℹ️  avatar_url 字段已存在，跳过")

    conn.close()


if __name__ == "__main__":
    migrate()
