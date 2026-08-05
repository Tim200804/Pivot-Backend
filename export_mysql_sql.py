#!/usr/bin/env python3
"""
Pivot SQLite → Railway MySQL 完整数据迁移 SQL 导出

生成包含 CREATE TABLE + INSERT 的完整 SQL 文件，可直接在 Railway MySQL Console 执行。

使用方法:
   cd pivot-backend
   python export_mysql_sql.py
   
这会生成 railway_data.sql 文件 (~230 行)，你可以:
1. 复制全部内容粘贴到 Railway Dashboard → MySQL → Console 执行
2. 或通过 mysql CLI: mysql -h <host> -u <user> -p < railway_data.sql
"""

import os
import sqlite3


# MySQL 表结构（与 models.py 完全一致）
CREATE_TABLES = [
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
    "CREATE INDEX idx_messages_recipient ON messages(recipient_id, created_at)",
    "CREATE INDEX idx_messages_sender ON messages(sender_id, created_at)",
    "CREATE INDEX idx_messages_conversation ON messages(sender_id, recipient_id, created_at)",
    "CREATE INDEX idx_links_coach ON coach_athlete_links(coach_id)",
    "CREATE INDEX idx_links_athlete ON coach_athlete_links(athlete_id)",
    "CREATE INDEX idx_checkins_user_date ON checkins(user_id, date)",
    "CREATE INDEX idx_health_user_date ON health_metrics(user_id, date)",
    "CREATE INDEX idx_training_user_date ON training_metrics(user_id, date)",
    "CREATE INDEX idx_alerts_user ON alerts(user_id, triggered_at)",
    "CREATE INDEX idx_alerts_status ON alerts(status, triggered_at)",
]


def escape_sql_value(val):
    """Escape a Python value for SQL INSERT."""
    if val is None:
        return 'NULL'
    if isinstance(val, bool):
        return '1' if val else '0'
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val).replace("'", "''")
    return f"'{s}'"


def main():
    db_path = os.path.join(os.path.dirname(__file__), 'pivot.db')
    if not os.path.exists(db_path):
        print(f"❌ 错误: 数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    output_path = os.path.join(os.path.dirname(__file__), 'railway_data.sql')
    lines = []

    lines.append("-- ═══════════════════════════════════════════════════════════════")
    lines.append("--  Pivot SQLite → Railway MySQL 完整数据迁移")
    lines.append("--  包含: CREATE TABLE + INDEXES + INSERT DATA")
    lines.append("-- ═══════════════════════════════════════════════════════════════")
    lines.append("")
    lines.append("SET FOREIGN_KEY_CHECKS = 0;")
    lines.append("")

    # CREATE TABLES
    lines.append("-- ┌─────────────────────────────────────────────────────────────┐")
    lines.append("-- │  1. 创建表结构")
    lines.append("-- └─────────────────────────────────────────────────────────────┘")
    lines.append("")
    for sql in CREATE_TABLES:
        lines.append(sql.strip() + ";")
        lines.append("")

    # CREATE INDEXES
    lines.append("-- ┌─────────────────────────────────────────────────────────────┐")
    lines.append("-- │  2. 创建索引")
    lines.append("-- └─────────────────────────────────────────────────────────────┘")
    lines.append("")
    for sql in INDEXES_SQL:
        lines.append(sql + ";")
    lines.append("")

    # INSERT DATA
    lines.append("-- ┌─────────────────────────────────────────────────────────────┐")
    lines.append("-- │  3. 导入数据")
    lines.append("-- └─────────────────────────────────────────────────────────────┘")
    lines.append("")

    table_order = ['users', 'alert_rules', 'messages', 'coach_athlete_links',
                   'checkins', 'health_metrics', 'training_metrics', 'alerts']
    ordered_tables = [t for t in table_order if t in tables] + [t for t in tables if t not in table_order]

    total_rows = 0
    for table in ordered_tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        col_str = ', '.join(columns)

        cursor.execute(f"SELECT {col_str} FROM {table}")
        rows = cursor.fetchall()

        if not rows:
            lines.append(f"-- {table}: 0 rows (跳过)")
            lines.append("")
            continue

        lines.append(f"-- {table}: {len(rows)} 行")
        lines.append(f"DELETE FROM {table};")

        for row in rows:
            if table == 'users' and 'role' in columns:
                idx = columns.index('role')
                row_list = list(row)
                if row_list[idx] == 'head_coach':
                    row_list[idx] = 'coach'
                row = tuple(row_list)

            values = ', '.join(escape_sql_value(v) for v in row)
            lines.append(f"INSERT INTO {table} ({col_str}) VALUES ({values});")

        lines.append("")
        total_rows += len(rows)

    lines.append("SET FOREIGN_KEY_CHECKS = 1;")
    lines.append("")
    lines.append(f"-- ✅ 迁移完成，共 {total_rows} 行数据")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    conn.close()

    print(f"✅ SQL 导出完成: {output_path}")
    print(f"   共 {len(lines)} 行 SQL，包含 {total_rows} 行数据")
    print()
    print("使用方法:")
    print("  1. 打开 railway_data.sql 文件")
    print("  2. 复制全部内容")
    print("  3. 在 Railway Dashboard → MySQL → Console 中粘贴执行")
    print()
    print("或者使用 mysql CLI:")
    print("  mysql -h <host> -u <user> -p < railway_data.sql")


if __name__ == '__main__':
    main()
