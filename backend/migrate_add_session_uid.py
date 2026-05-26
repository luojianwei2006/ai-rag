#!/usr/bin/env python3
"""迁移脚本：为 chat_sessions 表添加 uid 字段"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "platform.db")


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查列是否已存在
    cursor.execute("PRAGMA table_info(chat_sessions)")
    columns = [row[1] for row in cursor.fetchall()]

    if "uid" not in columns:
        cursor.execute("ALTER TABLE chat_sessions ADD COLUMN uid VARCHAR(100)")
        conn.commit()
        print("✅ 已添加 uid 字段到 chat_sessions 表")
    else:
        print("ℹ️  uid 字段已存在，跳过")

    conn.close()


if __name__ == "__main__":
    migrate()
