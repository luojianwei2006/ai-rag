"""迁移脚本：给 tenants 表添加 chat_language 列"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "platform.db")

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"数据库文件不存在: {DB_PATH}")
        print("请先启动后端服务以自动创建数据库和表。")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查 chat_language 列是否已存在
    cursor.execute("PRAGMA table_info(tenants)")
    columns = [row[1] for row in cursor.fetchall()]

    if "chat_language" in columns:
        print("chat_language 列已存在，无需迁移。")
        conn.close()
        return

    # 添加列，默认值为 'zh'
    cursor.execute("ALTER TABLE tenants ADD COLUMN chat_language VARCHAR(10) DEFAULT 'zh'")
    conn.commit()
    print("迁移完成：tenants 表已添加 chat_language 列（默认值 'zh'）")

    # 验证
    cursor.execute("PRAGMA table_info(tenants)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"当前 tenants 表字段: {columns}")

    conn.close()

if __name__ == "__main__":
    migrate()
