#!/usr/bin/env python3
"""
Pivot SQLite → Railway MySQL 数据同步脚本

使用方法:
1. 在 Railway Dashboard → MySQL → Connect 中复制 DATABASE_URL
2. 在终端设置环境变量并运行:

   export DATABASE_URL="mysql://root:xxxx@mysql.railway.internal:3306/railway"
   cd pivot-backend
   python sync_to_railway.py

注意:
- 此脚本会先清空 Railway MySQL 中的所有表数据，然后重新导入
- 确保 Railway 后端服务已经至少部署过一次（或脚本会自动建表）
- users.role='head_coach' 会被映射为 'coach'（MySQL CHECK 约束限制）
"""

import os
import sys
import sqlite3
from urllib.parse import urlparse

# ═══════════════════════════════════════════════════════════════════════════════
#  Railway MySQL 连接
# ═══════════════════════════════════════════════════════════════════════════════


def get_railway_mysql_conn(url: str = None):
    """Connect to Railway MySQL using DATABASE_URL env var or provided URL."""
    db_url = url or os.environ.get('DATABASE_URL')
    if not db_url:
        print("❌ 错误: 环境变量 DATABASE_URL 未设置")
        print("请从 Railway Dashboard → MySQL → Connect 复制 DATABASE_URL")
        print("然后执行: export DATABASE_URL='mysql://...'")
        sys.exit(1)

    db_url = db_url.replace('mysql+pymysql://', 'mysql://')
    parsed = urlparse(db_url)

    try:
        import pymysql
        conn = pymysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip('/'),
            charset='utf8mb4',
            autocommit=False
        )
        return conn
    except ImportError:
        print("❌ 错误: 未安装 PyMySQL")
        print("请执行: pip install PyMySQL")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 连接 Railway MySQL 失败: {e}")
        print("请检查 DATABASE_URL 是否正确，以及 Railway MySQL 是否已启动")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  本地 SQLite 连接
# ═══════════════════════════════════════════════════════════════════════════════


def get_sqlite_conn(path: str = None):
    """Connect to local SQLite database."""
    db_path = path or os.path.join(os.path.dirname(__file__), 'pivot.db')
    if not os.path.exists(db_path):
        print(f"❌ 错误: 本地数据库文件不存在: {db_path}")
        sys.exit(1)
    return sqlite3.connect(db_path)


# ═══════════════════════════════════════════════════════════════════════════════
#  表结构定义（与 models.py MySQL 版本完全一致）
# ═══════════════════════════════════════════════════════════════════════════════

TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(100) NOT NULL,
        name VARCHAR(100) NOT NULL,
        role VARCHAR(20) NOT NULL,
        sport VARCHAR(50),
        school VARCHAR(200),
        team_name VARCHAR(200),
        position VARCHAR(100),
        coach_role VARCHAR(100),
        height INT,
        weight INT,
        preferences VARCHAR(500) NOT NULL DEFAULT '{}',
        created_at VARCHAR(30) NOT NULL,
        updated_at VARCHAR(30) NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alert_rules (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(200) NOT NULL,
        level VARCHAR(20) NOT NULL,
        sport VARCHAR(50) NOT NULL DEFAULT '*',
        conditions VARCHAR(2000) NOT NULL DEFAULT '{}',
        is_active INT NOT NULL DEFAULT 1,
        created_at VARCHAR(30) NOT NULL,
        updated_at VARCHAR(30) NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INT PRIMARY KEY AUTO_INCREMENT,
        sender_id INT NOT NULL,
        recipient_id INT NOT NULL,
        subject VARCHAR(255),
        body TEXT NOT NULL,
        alert_level VARCHAR(50),
        alert_type VARCHAR(50),
        read_at VARCHAR(30),
        created_at VARCHAR(30) NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS coach_athlete_links (
        id INT PRIMARY KEY AUTO_INCREMENT,
        coach_id INT NOT NULL,
        athlete_id INT NOT NULL,
        role VARCHAR(50) NOT NULL DEFAULT 'primary',
        created_at VARCHAR(30) NOT NULL,
        updated_at VARCHAR(30) NOT NULL,
        UNIQUE(coach_id, athlete_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS checkins (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        date VARCHAR(30) NOT NULL,
        mood INT NOT NULL,
        motivation INT NOT NULL,
        fatigue INT NOT NULL,
        challenge VARCHAR(100) NOT NULL DEFAULT 'none',
        journal VARCHAR(2000) NOT NULL DEFAULT '',
        created_at VARCHAR(30) NOT NULL,
        updated_at VARCHAR(30) NOT NULL,
        UNIQUE(user_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS health_metrics (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        date VARCHAR(30) NOT NULL,
        hrv REAL,
        rhr REAL,
        sleep_hours REAL,
        sleep_deep_pct REAL,
        sleep_rem_pct REAL,
        spo2 REAL,
        respiratory_rate REAL,
        skin_temp REAL,
        source VARCHAR(50) NOT NULL DEFAULT 'manual',
        created_at VARCHAR(30) NOT NULL,
        UNIQUE(user_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS training_metrics (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        date VARCHAR(30) NOT NULL,
        distance REAL,
        avg_split REAL,
        avg_spm REAL,
        max_hr REAL,
        avg_hr REAL,
        duration_minutes REAL,
        training_type VARCHAR(50),
        training_phase VARCHAR(50),
        intensity_score INT,
        volume_score INT,
        focus_area VARCHAR(100),
        coach_notes TEXT,
        planned_load INT,
        actual_load INT,
        created_at VARCHAR(30) NOT NULL,
        UNIQUE(user_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alerts (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        level VARCHAR(20) NOT NULL,
        type VARCHAR(100) NOT NULL,
        message TEXT NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'active',
        rule_id INT,
        triggered_at VARCHAR(30) NOT NULL,
        resolved_at VARCHAR(30),
        created_at VARCHAR(30) NOT NULL,
        updated_at VARCHAR(30) NOT NULL
    )
    """,
]

INDEXES_SQL = [
    ("idx_messages_recipient", "messages", "recipient_id, created_at"),
    ("idx_messages_sender", "messages", "sender_id, created_at"),
    ("idx_messages_conversation", "messages", "sender_id, recipient_id, created_at"),
    ("idx_links_coach", "coach_athlete_links", "coach_id"),
    ("idx_links_athlete", "coach_athlete_links", "athlete_id"),
    ("idx_checkins_user_date", "checkins", "user_id, date"),
    ("idx_health_user_date", "health_metrics", "user_id, date"),
    ("idx_training_user_date", "training_metrics", "user_id, date"),
    ("idx_alerts_user", "alerts", "user_id, triggered_at"),
    ("idx_alerts_status", "alerts", "status, triggered_at"),
]

# 建表顺序（处理外键依赖）
TABLE_ORDER = [
    'users',
    'alert_rules',
    'messages',
    'coach_athlete_links',
    'checkins',
    'health_metrics',
    'training_metrics',
    'alerts',
]


# ═══════════════════════════════════════════════════════════════════════════════
#  迁移逻辑
# ═══════════════════════════════════════════════════════════════════════════════

def ensure_tables(mysql_conn):
    """Ensure all tables and indexes exist in MySQL."""
    cursor = mysql_conn.cursor()

    # Create tables
    for sql in TABLES_SQL:
        try:
            cursor.execute(sql)
        except Exception as e:
            err = str(e).lower()
            if 'already exists' in err or 'duplicate' in err:
                pass
            else:
                print(f"   ⚠️  建表警告: {e}")

    # Create indexes
    for idx_name, table, cols in INDEXES_SQL:
        try:
            cursor.execute(f"CREATE INDEX {idx_name} ON {table}({cols})")
        except Exception as e:
            err = str(e).lower()
            if 'already exists' in err or 'duplicate' in err:
                pass
            else:
                print(f"   ⚠️  索引警告: {e}")

    mysql_conn.commit()
    cursor.close()
    print("✅ 表结构和索引检查完成")


def clear_mysql_tables(mysql_conn):
    """Clear all data from MySQL tables (in reverse order to avoid FK constraints)."""
    cursor = mysql_conn.cursor()
    for table in reversed(TABLE_ORDER):
        try:
            cursor.execute(f"DELETE FROM {table}")
            print(f"   清空表: {table}")
        except Exception as e:
            print(f"   清空表 {table} 跳过: {e}")
    mysql_conn.commit()
    cursor.close()
    print("✅ MySQL 数据已清空")


def get_sqlite_columns(sqlite_cursor, table):
    """Get column names from SQLite table."""
    sqlite_cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in sqlite_cursor.fetchall()]


def transform_row(table, columns, row):
    """Transform SQLite row data for MySQL compatibility."""
    row_list = list(row)

    # Fix users.role: 'head_coach' → 'coach' (MySQL CHECK constraint)
    if table == 'users' and 'role' in columns:
        idx = columns.index('role')
        if row_list[idx] == 'head_coach':
            row_list[idx] = 'coach'

    return tuple(row_list)


def migrate_table(sqlite_conn, mysql_conn, table):
    """Migrate a single table from SQLite to MySQL."""
    sqlite_cursor = sqlite_conn.cursor()
    mysql_cursor = mysql_conn.cursor()

    # 获取列名
    columns = get_sqlite_columns(sqlite_cursor, table)
    col_str = ', '.join(columns)
    placeholders = ', '.join(['%s'] * len(columns))

    # 读取 SQLite 数据
    sqlite_cursor.execute(f"SELECT {col_str} FROM {table}")
    rows = sqlite_cursor.fetchall()

    if not rows:
        print(f"   {table}: 0 行 (跳过)")
        return 0

    # 插入 MySQL
    sql = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})"
    inserted = 0
    for row in rows:
        transformed = transform_row(table, columns, row)
        try:
            mysql_cursor.execute(sql, transformed)
            inserted += 1
        except Exception as e:
            print(f"   ⚠️  插入失败 ({table}): {e} | 数据: {transformed}")

    mysql_conn.commit()
    sqlite_cursor.close()
    mysql_cursor.close()
    print(f"   {table}: {inserted}/{len(rows)} 行已迁移")
    return inserted


def sync_sqlite_to_mysql(sqlite_path: str = None, mysql_url: str = None, skip_clear: bool = False):
    """Synchronize a SQLite database into Railway MySQL.

    Args:
        sqlite_path: Path to source SQLite file. Defaults to ./pivot.db.
        mysql_url: MySQL connection URL. Defaults to DATABASE_URL env var.
        skip_clear: If True, do not DELETE existing MySQL data before inserting.
    """
    sqlite_conn = get_sqlite_conn(sqlite_path)
    mysql_conn = get_railway_mysql_conn(mysql_url)

    try:
        ensure_tables(mysql_conn)
        if not skip_clear:
            clear_mysql_tables(mysql_conn)

        total = 0
        for table in TABLE_ORDER:
            total += migrate_table(sqlite_conn, mysql_conn, table)
        return total
    finally:
        sqlite_conn.close()
        mysql_conn.close()


def seed_railway_from_bundled(bundled_db: str = 'railway_seed.db'):
    """Seed Railway MySQL from a bundled SQLite file if the users table is empty."""
    if not os.path.exists(bundled_db):
        print(f"[seed] Bundled DB not found: {bundled_db}")
        return 0

    mysql_conn = get_railway_mysql_conn()
    try:
        cursor = mysql_conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
        except Exception:
            count = 0
        cursor.close()

        if count > 0:
            print(f"[seed] Railway MySQL already has {count} users; skipping bundled seed")
            return 0

        print(f"[seed] Railway MySQL is empty; seeding from {bundled_db}")
        total = sync_sqlite_to_mysql(bundled_db, skip_clear=True)
        print(f"[seed] Seeded {total} rows from bundled SQLite")
        return total
    finally:
        mysql_conn.close()


def main():
    print("═" * 60)
    print("  Pivot SQLite → Railway MySQL 数据同步")
    print("═" * 60)
    print()

    total = sync_sqlite_to_mysql()

    print("═" * 60)
    print(f"  ✅ 同步完成！共迁移 {total} 行数据")
    print("═" * 60)
    print()
    print("下一步:")
    print("  1. 在 Railway Dashboard 中检查数据是否已导入")
    print("  2. 重新部署 pivot-backend 服务以刷新连接")
    print("  3. 访问 /api/health 验证服务正常")


if __name__ == '__main__':
    main()
