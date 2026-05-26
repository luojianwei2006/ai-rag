"""
SQLite → MySQL 数据迁移脚本
使用前请先安装依赖：pip install pymysql sqlalchemy

使用方法：
1. 确保 MySQL 已启动，并已创建数据库 customer_service
2. 修改下方 SQLITE_PATH 和 MYSQL_URL
3. 运行：python migrate_sqlite_to_mysql.py
"""

import os
import sys

# ============ 配置区 ============
SQLITE_PATH = os.path.join(os.path.dirname(__file__), "platform.db")
MYSQL_URL = "mysql+pymysql://cs_user:cs_pass123@localhost:3306/customer_service"
# ====================================


def main():
    try:
        from sqlalchemy import create_engine, MetaData, Table, inspect
        from sqlalchemy.orm import sessionmaker
    except ImportError:
        print("❌ 缺少依赖，请先运行：pip install pymysql sqlalchemy")
        sys.exit(1)

    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLite 数据库不存在：{SQLITE_PATH}")
        sys.exit(1)

    print(f"📂 SQLite 源：{SQLITE_PATH}")
    print(f"🗄️  MySQL 目标：{MYSQL_URL}")

    # 连接 SQLite
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_PATH}")
    sqlite_meta = MetaData()
    sqlite_meta.reflect(bind=sqlite_engine)

    # 连接 MySQL
    print("🔗 连接 MySQL...")
    mysql_engine = create_engine(MYSQL_URL)
    mysql_meta = MetaData()
    mysql_meta.reflect(bind=mysql_engine)

    # 获取所有表
    tables = list(sqlite_meta.tables.keys())
    print(f"📊 发现 {len(tables)} 张表：{tables}")

    mysql_session = sessionmaker(bind=mysql_engine)()

    # 按外键依赖顺序迁移（简单处理：先迁移无外键的表）
    # 这里直接按 SQLite 中的顺序迁移
    for table_name in tables:
        print(f"\n🔄 迁移表：{table_name}")
        sqlite_table = sqlite_meta.tables[table_name]

        # 检查 MySQL 中是否已存在该表
        if table_name not in mysql_meta.tables:
            print(f"   ⚠️  MySQL 中不存在表 {table_name}，请先运行：python -c 'from database import Base, engine; Base.metadata.create_all(bind=engine)'")
            continue

        mysql_table = mysql_meta.tables[table_name]

        # 读取 SQLite 数据
        with sqlite_engine.connect() as conn:
            result = conn.execute(sqlite_table.select())
            rows = result.fetchall()
            columns = result.keys()

        if not rows:
            print(f"   ⏩  表为空，跳过")
            continue

        print(f"   📥 读取到 {len(rows)} 条数据")

        # 插入 MySQL
        # 关闭 MySQL 外键检查（避免顺序问题）
        mysql_session.execute("SET FOREIGN_KEY_CHECKS=0")
        mysql_session.commit()

        # 清空目标表（可选）
        mysql_session.execute(mysql_table.delete())
        mysql_session.commit()

        # 插入数据
        for row in rows:
            data = dict(zip(columns, row))
            # 过滤掉 MySQL 中不存在的列
            valid_columns = [c.name for c in mysql_table.columns]
            data = {k: v for k, v in data.items() if k in valid_columns}
            mysql_session.execute(mysql_table.insert().values(**data))

        mysql_session.commit()
        print(f"   ✅ 成功插入 {len(rows)} 条数据")

    mysql_session.close()
    print("\n🎉 数据迁移完成！")
    print("⚠️  请手动检查数据完整性，并运行：SET FOREIGN_KEY_CHECKS=1;")


if __name__ == "__main__":
    main()
