import os
import json
import math
from datetime import datetime, timedelta
from urllib.parse import urlparse

# ═══════════════════════════════════════════════════════════════════════════════
#  Database URL parsing
# ═══════════════════════════════════════════════════════════════════════════════

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///pivot.db')


def _is_mysql() -> bool:
    return DATABASE_URL.startswith('mysql')


def _parse_mysql_url(url: str) -> dict:
    url = url.replace('mysql+pymysql://', 'mysql://')
    parsed = urlparse(url)
    return {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 3306,
        'user': parsed.username or 'root',
        'password': parsed.password or '',
        'database': parsed.path.lstrip('/') if parsed.path else '',
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  SQL Adaptation
# ═══════════════════════════════════════════════════════════════════════════════

def _convert_placeholders(sql: str) -> str:
    """Replace ? placeholders with %s for MySQL, skipping string literals."""
    out = []
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "'":
            out.append(c)
            i += 1
            while i < len(sql):
                c2 = sql[i]
                out.append(c2)
                if c2 == "'":
                    if i + 1 < len(sql) and sql[i + 1] == "'":
                        out.append(sql[i + 1])
                        i += 2
                        continue
                    break
                i += 1
            i += 1
        elif c == '"':
            out.append(c)
            i += 1
            while i < len(sql):
                c2 = sql[i]
                out.append(c2)
                if c2 == '"':
                    break
                i += 1
            i += 1
        elif c == '?':
            out.append('%s')
            i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def _adapt_sql(sql: str, is_mysql: bool) -> str:
    if not is_mysql:
        return sql
    sql = sql.replace('AUTOINCREMENT', 'AUTO_INCREMENT')
    sql = _convert_placeholders(sql)
    return sql


# ═══════════════════════════════════════════════════════════════════════════════
#  Cursor / Connection wrappers
# ═══════════════════════════════════════════════════════════════════════════════

class _CursorProxy:
    def __init__(self, raw_cursor, is_mysql):
        self._cursor = raw_cursor
        self._is_mysql = is_mysql

    def execute(self, sql, params=()):
        sql = _adapt_sql(sql, self._is_mysql)
        self._cursor.execute(sql, params)
        return self

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchone(self):
        return self._cursor.fetchone()

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        if hasattr(self._cursor, 'close'):
            self._cursor.close()


class DBConnection:
    def __init__(self, raw_conn, is_mysql):
        self._conn = raw_conn
        self._is_mysql = is_mysql
        self._cursors = []

    def execute(self, sql, parameters=()):
        sql = _adapt_sql(sql, self._is_mysql)
        if self._is_mysql:
            cur = self._conn.cursor()
            cur.execute(sql, parameters)
            proxy = _CursorProxy(cur, self._is_mysql)
            self._cursors.append(proxy)
            return proxy
        else:
            cur = self._conn.execute(sql, parameters)
            proxy = _CursorProxy(cur, self._is_mysql)
            self._cursors.append(proxy)
            return proxy

    def cursor(self):
        if self._is_mysql:
            raw = self._conn.cursor()
            proxy = _CursorProxy(raw, self._is_mysql)
            self._cursors.append(proxy)
            return proxy
        else:
            raw = self._conn.cursor()
            proxy = _CursorProxy(raw, self._is_mysql)
            self._cursors.append(proxy)
            return proxy

    def commit(self):
        self._conn.commit()

    def close(self):
        for c in self._cursors:
            c.close()
        self._conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  Connection factory
# ═══════════════════════════════════════════════════════════════════════════════

def get_db() -> DBConnection:
    if _is_mysql():
        import pymysql
        cfg = _parse_mysql_url(DATABASE_URL)
        conn = pymysql.connect(
            host=cfg['host'],
            port=cfg['port'],
            user=cfg['user'],
            password=cfg['password'],
            database=cfg['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
        return DBConnection(conn, is_mysql=True)
    else:
        import sqlite3
        path = DATABASE_URL.replace('sqlite:///', '')
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return DBConnection(conn, is_mysql=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  Schema helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _table_has_column(conn: DBConnection, table: str, column: str) -> bool:
    if conn._is_mysql:
        cur = conn.execute(f"SHOW COLUMNS FROM `{table}`")
        rows = cur.fetchall()
        return any(r.get('Field') == column for r in rows)
    else:
        cur = conn.execute(f"PRAGMA table_info({table})")
        rows = cur.fetchall()
        return any(r['name'] == column for r in rows)


def _create_index_if_not_exists(conn: DBConnection, name: str, table: str, columns: str):
    if conn._is_mysql:
        cur = conn.execute(
            """SELECT 1 FROM information_schema.STATISTICS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = %s
                 AND INDEX_NAME = %s""",
            (table, name)
        )
        if cur.fetchone():
            return
        conn.execute(f"CREATE INDEX `{name}` ON `{table}` ({columns})")
    else:
        conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({columns})")


def _upsert_sql(table: str, columns: list, unique_cols: list, updates: list, is_mysql: bool) -> str:
    placeholders = ', '.join(['?'] * len(columns))
    cols = ', '.join(columns)
    if is_mysql:
        upd = ', '.join(f'{c}=VALUES({c})' for c in updates)
        return f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {upd}'
    else:
        upd = ', '.join(f'{c}=excluded.{c}' for c in updates)
        unq = ', '.join(unique_cols)
        return f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT({unq}) DO UPDATE SET {upd}'


# ═══════════════════════════════════════════════════════════════════════════════
#  Init DB
# ═══════════════════════════════════════════════════════════════════════════════

def init_db():
    conn = get_db()
    is_mysql = conn._is_mysql

    # ── users ──
    if is_mysql:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(100) NOT NULL,
            name VARCHAR(100) NOT NULL,
            role VARCHAR(20) NOT NULL CHECK(role IN ('athlete', 'coach')),
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
        )''')
    else:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('athlete', 'coach')),
            sport TEXT,
            school TEXT,
            team_name TEXT,
            position TEXT,
            coach_role TEXT,
            height INTEGER,
            weight INTEGER,
            preferences TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')

    if not _table_has_column(conn, 'users', 'preferences'):
        if is_mysql:
            conn.execute("ALTER TABLE users ADD COLUMN preferences VARCHAR(500) NOT NULL DEFAULT '{}';")
        else:
            conn.execute("ALTER TABLE users ADD COLUMN preferences TEXT NOT NULL DEFAULT '{}';")

    # ── alert_rules (must be created before alerts because of FK) ──
    if is_mysql:
        conn.execute('''CREATE TABLE IF NOT EXISTS alert_rules (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(200) NOT NULL,
            level VARCHAR(20) NOT NULL CHECK(level IN ('yellow', 'red', 'black')),
            sport VARCHAR(50) NOT NULL DEFAULT '*',
            conditions VARCHAR(2000) NOT NULL DEFAULT '{}',
            is_active INT NOT NULL DEFAULT 1,
            created_at VARCHAR(30) NOT NULL,
            updated_at VARCHAR(30) NOT NULL
        )''')
    else:
        conn.execute('''CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            level TEXT NOT NULL CHECK(level IN ('yellow', 'red', 'black')),
            sport TEXT NOT NULL DEFAULT '*',
            conditions TEXT NOT NULL DEFAULT '{}',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')

    # ── messages ──
    if is_mysql:
        conn.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INT PRIMARY KEY AUTO_INCREMENT,
            sender_id INT NOT NULL,
            recipient_id INT NOT NULL,
            subject VARCHAR(255),
            body TEXT NOT NULL,
            alert_level VARCHAR(50),
            alert_type VARCHAR(50),
            read_at VARCHAR(30),
            created_at VARCHAR(30) NOT NULL,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (recipient_id) REFERENCES users(id)
        )''')
    else:
        conn.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            subject TEXT,
            body TEXT NOT NULL,
            alert_level TEXT,
            alert_type TEXT,
            read_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (recipient_id) REFERENCES users(id)
        )''')

    _create_index_if_not_exists(conn, 'idx_messages_recipient', 'messages', 'recipient_id, created_at')
    _create_index_if_not_exists(conn, 'idx_messages_sender', 'messages', 'sender_id, created_at')
    _create_index_if_not_exists(conn, 'idx_messages_conversation', 'messages', 'sender_id, recipient_id, created_at')

    # ── coach_athlete_links ──
    if is_mysql:
        conn.execute('''CREATE TABLE IF NOT EXISTS coach_athlete_links (
            id INT PRIMARY KEY AUTO_INCREMENT,
            coach_id INT NOT NULL,
            athlete_id INT NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'primary',
            created_at VARCHAR(30) NOT NULL,
            updated_at VARCHAR(30) NOT NULL,
            FOREIGN KEY (coach_id) REFERENCES users(id),
            FOREIGN KEY (athlete_id) REFERENCES users(id),
            UNIQUE(coach_id, athlete_id)
        )''')
    else:
        conn.execute('''CREATE TABLE IF NOT EXISTS coach_athlete_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coach_id INTEGER NOT NULL,
            athlete_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'primary',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (coach_id) REFERENCES users(id),
            FOREIGN KEY (athlete_id) REFERENCES users(id),
            UNIQUE(coach_id, athlete_id)
        )''')

    _create_index_if_not_exists(conn, 'idx_links_coach', 'coach_athlete_links', 'coach_id')
    _create_index_if_not_exists(conn, 'idx_links_athlete', 'coach_athlete_links', 'athlete_id')

    # ── checkins ──
    if is_mysql:
        conn.execute('''CREATE TABLE IF NOT EXISTS checkins (
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
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        )''')
    else:
        conn.execute('''CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            mood INTEGER NOT NULL,
            motivation INTEGER NOT NULL,
            fatigue INTEGER NOT NULL,
            challenge TEXT NOT NULL DEFAULT 'none',
            journal TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        )''')

    _create_index_if_not_exists(conn, 'idx_checkins_user_date', 'checkins', 'user_id, date')

    # ── health_metrics ──
    if is_mysql:
        conn.execute('''CREATE TABLE IF NOT EXISTS health_metrics (
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
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        )''')
    else:
        conn.execute('''CREATE TABLE IF NOT EXISTS health_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            hrv REAL,
            rhr REAL,
            sleep_hours REAL,
            sleep_deep_pct REAL,
            sleep_rem_pct REAL,
            spo2 REAL,
            respiratory_rate REAL,
            skin_temp REAL,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        )''')

    _create_index_if_not_exists(conn, 'idx_health_user_date', 'health_metrics', 'user_id, date')

    # ── training_metrics ──
    if is_mysql:
        conn.execute('''CREATE TABLE IF NOT EXISTS training_metrics (
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
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        )''')
    else:
        conn.execute('''CREATE TABLE IF NOT EXISTS training_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            distance REAL,
            avg_split REAL,
            avg_spm REAL,
            max_hr REAL,
            avg_hr REAL,
            duration_minutes REAL,
            training_type TEXT,
            training_phase TEXT,
            intensity_score INTEGER,
            volume_score INTEGER,
            focus_area TEXT,
            coach_notes TEXT,
            planned_load INTEGER,
            actual_load INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        )''')

    # Migration: add new training columns if they don't exist (existing deployments)
    for col, col_type in [
        ('training_type', 'TEXT'),
        ('training_phase', 'TEXT'),
        ('intensity_score', 'INTEGER'),
        ('volume_score', 'INTEGER'),
        ('focus_area', 'TEXT'),
        ('coach_notes', 'TEXT'),
        ('planned_load', 'INTEGER'),
        ('actual_load', 'INTEGER'),
    ]:
        if not _table_has_column(conn, 'training_metrics', col):
            conn.execute(f'ALTER TABLE training_metrics ADD COLUMN {col} {col_type}')

    _create_index_if_not_exists(conn, 'idx_training_user_date', 'training_metrics', 'user_id, date')

    # ── alerts ──
    if is_mysql:
        conn.execute('''CREATE TABLE IF NOT EXISTS alerts (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            level VARCHAR(20) NOT NULL CHECK(level IN ('yellow', 'red', 'black')),
            type VARCHAR(100) NOT NULL,
            message TEXT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'resolved', 'dismissed')),
            rule_id INT,
            triggered_at VARCHAR(30) NOT NULL,
            resolved_at VARCHAR(30),
            created_at VARCHAR(30) NOT NULL,
            updated_at VARCHAR(30) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (rule_id) REFERENCES alert_rules(id)
        )''')
    else:
        conn.execute('''CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            level TEXT NOT NULL CHECK(level IN ('yellow', 'red', 'black')),
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'resolved', 'dismissed')),
            rule_id INTEGER,
            triggered_at TEXT NOT NULL,
            resolved_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (rule_id) REFERENCES alert_rules(id)
        )''')

    _create_index_if_not_exists(conn, 'idx_alerts_user', 'alerts', 'user_id, triggered_at')
    _create_index_if_not_exists(conn, 'idx_alerts_status', 'alerts', 'status, triggered_at')

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  Users
# ═══════════════════════════════════════════════════════════════════════════════

def create_user(data: dict, password_hash: str) -> dict:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (email, password_hash, name, role, sport, school, team_name,
                           position, coach_role, height, weight, preferences, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['email'],
        password_hash,
        data['name'],
        data['role'],
        data.get('sport'),
        data.get('school'),
        data.get('teamName'),
        data.get('position'),
        data.get('coachRole'),
        data.get('height'),
        data.get('weight'),
        json.dumps(_default_preferences()),
        now, now
    ))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_user_by_id(user_id)


def _default_preferences() -> dict:
    return {
        'alertNotifications': True,
        'weeklyReport': True,
    }


def get_user_by_email(email: str) -> dict | None:
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_coaches(exclude_id: int | None = None) -> list[dict]:
    conn = get_db()
    if exclude_id is not None:
        rows = conn.execute(
            "SELECT id, email, name, role, sport, coach_role FROM users WHERE role = 'coach' AND id != ? ORDER BY name, id",
            (exclude_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, email, name, role, sport, coach_role FROM users WHERE role = 'coach' ORDER BY name, id"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user_preferences(user_id: int, prefs: dict) -> dict | None:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    row = conn.execute('SELECT preferences FROM users WHERE id = ?', (user_id,)).fetchone()
    if not row:
        conn.close()
        return None
    try:
        current = json.loads(row.get('preferences') or '{}')
    except (json.JSONDecodeError, TypeError):
        current = _default_preferences()
    allowed = {'alertNotifications', 'weeklyReport'}
    for k, v in prefs.items():
        if k in allowed and isinstance(v, bool):
            current[k] = v
    conn.execute(
        'UPDATE users SET preferences = ?, updated_at = ? WHERE id = ?',
        (json.dumps(current), now, user_id)
    )
    conn.commit()
    conn.close()
    return get_user_by_id(user_id)


def user_to_public(user: dict) -> dict:
    try:
        prefs = json.loads(user.get('preferences') or '{}')
    except (json.JSONDecodeError, TypeError):
        prefs = _default_preferences()
    return {
        'id': user['id'],
        'email': user['email'],
        'name': user['name'],
        'role': user['role'],
        'sport': user['sport'],
        'school': user['school'],
        'teamName': user['team_name'],
        'position': user['position'],
        'coachRole': user['coach_role'],
        'height': user['height'],
        'weight': user['weight'],
        'preferences': prefs,
        'createdAt': user['created_at'],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Messages
# ═══════════════════════════════════════════════════════════════════════════════

def create_message(sender_id: int, recipient_id: int, body: str,
                   subject: str = None, alert_level: str = None,
                   alert_type: str = None) -> dict:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (sender_id, recipient_id, subject, body,
                             alert_level, alert_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (sender_id, recipient_id, subject, body, alert_level, alert_type, now))
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_message_by_id(msg_id)


def get_message_by_id(msg_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute('SELECT * FROM messages WHERE id = ?', (msg_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_messages_for_user(user_id: int, limit: int = 50, unread_only: bool = False) -> list[dict]:
    conn = get_db()
    sql = 'SELECT * FROM messages WHERE recipient_id = ?'
    params = [user_id]
    if unread_only:
        sql += ' AND read_at IS NULL'
    sql += ' ORDER BY created_at DESC LIMIT ?'
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_messages_from_user(user_id: int, limit: int = 50) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM messages WHERE sender_id = ? ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_conversation(user_id: int, other_user_id: int, limit: int = 200) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        '''SELECT * FROM messages
           WHERE (sender_id = ? AND recipient_id = ?)
              OR (sender_id = ? AND recipient_id = ?)
           ORDER BY created_at ASC
           LIMIT ?''',
        (user_id, other_user_id, other_user_id, user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_message_read(msg_id: int, user_id: int) -> dict | None:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM messages WHERE id = ? AND recipient_id = ?',
        (msg_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        return None
    if not row.get('read_at'):
        conn.execute('UPDATE messages SET read_at = ? WHERE id = ?', (now, msg_id))
        conn.commit()
    conn.close()
    return get_message_by_id(msg_id)


def count_unread(user_id: int) -> int:
    conn = get_db()
    row = conn.execute(
        'SELECT COUNT(*) AS c FROM messages WHERE recipient_id = ? AND read_at IS NULL',
        (user_id,)
    ).fetchone()
    conn.close()
    return row['c'] if row else 0


def message_to_public(msg: dict, sender: dict = None) -> dict:
    return {
        'id': msg['id'],
        'senderId': msg['sender_id'],
        'senderName': sender['name'] if sender else None,
        'recipientId': msg['recipient_id'],
        'subject': msg.get('subject'),
        'body': msg['body'],
        'alertLevel': msg.get('alert_level'),
        'alertType': msg.get('alert_type'),
        'readAt': msg.get('read_at'),
        'createdAt': msg['created_at'],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Coach-Athlete Links
# ═══════════════════════════════════════════════════════════════════════════════

def create_coach_athlete_link(coach_id: int, athlete_id: int, link_role: str = 'primary') -> dict:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    is_mysql = conn._is_mysql
    sql = _upsert_sql(
        'coach_athlete_links',
        ['coach_id', 'athlete_id', 'role', 'created_at', 'updated_at'],
        ['coach_id', 'athlete_id'],
        ['role', 'updated_at'],
        is_mysql,
    )
    cursor.execute(sql, (coach_id, athlete_id, link_role, now, now))
    link_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_coach_athlete_link_by_id(link_id)


def get_coach_athlete_link_by_id(link_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute('SELECT * FROM coach_athlete_links WHERE id = ?', (link_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_athletes_for_coach(coach_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute('''
        SELECT u.id, u.email, u.name, u.sport, u.school, u.team_name, u.position,
               u.height, u.weight
        FROM coach_athlete_links l
        JOIN users u ON u.id = l.athlete_id
        WHERE l.coach_id = ? AND u.role = 'athlete'
        ORDER BY u.name
    ''', (coach_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_coaches_for_athlete(athlete_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute('''
        SELECT u.id, u.name, u.email, u.coach_role
        FROM coach_athlete_links l
        JOIN users u ON u.id = l.coach_id
        WHERE l.athlete_id = ? AND u.role = 'coach'
        ORDER BY u.name
    ''', (athlete_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_all_athletes_with_summary() -> list[dict]:
    conn = get_db()
    rows = conn.execute('''
        SELECT u.id, u.email, u.name, u.sport, u.school, u.team_name, u.position,
               u.height, u.weight
        FROM users u
        WHERE u.role = 'athlete'
        ORDER BY u.name
    ''').fetchall()
    athletes = [dict(r) for r in rows]
    conn.close()
    for a in athletes:
        a['summary'] = get_latest_health_summary(a['id'])
    return athletes


# ═══════════════════════════════════════════════════════════════════════════════
#  Check-ins
# ═══════════════════════════════════════════════════════════════════════════════

def create_checkin(user_id: int, data: dict) -> dict:
    now = datetime.utcnow().isoformat()
    date = data.get('date') or now[:10]
    conn = get_db()
    cursor = conn.cursor()
    is_mysql = conn._is_mysql
    sql = _upsert_sql(
        'checkins',
        ['user_id', 'date', 'mood', 'motivation', 'fatigue', 'challenge', 'journal', 'created_at', 'updated_at'],
        ['user_id', 'date'],
        ['mood', 'motivation', 'fatigue', 'challenge', 'journal', 'updated_at'],
        is_mysql,
    )
    cursor.execute(sql, (user_id, date, data['mood'], data['motivation'], data['fatigue'],
                         data.get('challenge', 'none'), data.get('journal', ''), now, now))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_checkin_by_id(row_id)


def get_checkin_by_id(checkin_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute('SELECT * FROM checkins WHERE id = ?', (checkin_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_checkins(user_id: int, limit: int = 90) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM checkins WHERE user_id = ? ORDER BY date DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_checkin_for_date(user_id: int, date: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM checkins WHERE user_id = ? AND date = ?',
        (user_id, date)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════════════════════
#  Health Metrics
# ═══════════════════════════════════════════════════════════════════════════════

def create_health_metric(user_id: int, data: dict) -> dict:
    now = datetime.utcnow().isoformat()
    date = data.get('date') or now[:10]
    conn = get_db()
    cursor = conn.cursor()
    is_mysql = conn._is_mysql
    sql = _upsert_sql(
        'health_metrics',
        ['user_id', 'date', 'hrv', 'rhr', 'sleep_hours', 'sleep_deep_pct', 'sleep_rem_pct',
         'spo2', 'respiratory_rate', 'skin_temp', 'source', 'created_at'],
        ['user_id', 'date'],
        ['hrv', 'rhr', 'sleep_hours', 'sleep_deep_pct', 'sleep_rem_pct',
         'spo2', 'respiratory_rate', 'skin_temp', 'source'],
        is_mysql,
    )
    cursor.execute(sql, (user_id, date,
                         data.get('hrv'), data.get('rhr'), data.get('sleepHours'), data.get('sleepDeep'),
                         data.get('sleepREM'), data.get('spo2'), data.get('respiratoryRate'),
                         data.get('skinTemp'), data.get('source', 'manual'), now))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_health_metric_by_id(row_id)


def get_health_metric_by_id(metric_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute('SELECT * FROM health_metrics WHERE id = ?', (metric_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_health_metrics(user_id: int, limit: int = 180) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM health_metrics WHERE user_id = ? ORDER BY date DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_health_metric(user_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM health_metrics WHERE user_id = ? ORDER BY date DESC LIMIT 1',
        (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_health_summary(user_id: int) -> dict:
    latest = get_latest_health_metric(user_id)
    if not latest:
        return {'status': 'unknown', 'hrv': None, 'rhr': None, 'sleepHours': None}

    hrv = latest.get('hrv')
    rhr = latest.get('rhr')
    sleep = latest.get('sleep_hours')
    status = 'good'
    if hrv is not None and rhr is not None:
        if hrv < 35 or (sleep is not None and sleep < 4):
            status = 'urgent'
        elif hrv < 45 or (sleep is not None and sleep < 5.5):
            status = 'danger'
        elif hrv < 55 or (sleep is not None and sleep < 6):
            status = 'warning'
    return {
        'status': status,
        'hrv': hrv,
        'rhr': rhr,
        'sleepHours': sleep,
        'date': latest.get('date'),
    }


def get_team_summary(coach_id: int) -> dict:
    """Aggregate latest health metrics for all athletes linked to a coach."""
    athletes = list_athletes_for_coach(coach_id)
    if not athletes:
        return {
            'totalAthletes': 0,
            'avgHRV': 0,
            'avgRHR': 0,
            'avgSleep': 0,
            'healthScore': 100,
            'athletes': [],
        }

    summaries = []
    for athlete in athletes:
        user_id = athlete['id']
        summary = get_latest_health_summary(user_id)
        # Aggregate recent training load (last 7 days)
        recent_training = list_training_metrics(user_id, limit=7)
        loads = []
        latest_type = None
        latest_date = None
        for t in recent_training:
            load = t.get('planned_load') or t.get('actual_load') or (t.get('intensity_score') or 5) * (t.get('volume_score') or 5)
            loads.append(load)
            if latest_date is None or t['date'] > latest_date:
                latest_date = t['date']
                latest_type = t.get('training_type')
        avg_load = round(sum(loads) / len(loads), 1) if loads else 0
        high_load_days = sum(1 for load in loads if load >= 40)
        training_summary = {
            'recentTrainingLoad': avg_load,
            'latestTrainingType': latest_type,
            'latestTrainingDate': latest_date,
            'highLoadDays': high_load_days,
        }
        summaries.append({**athlete, **summary, **training_summary})

    valid = [s for s in summaries if s.get('hrv') is not None]
    n = len(valid) or 1
    avg_hrv = round(sum(s['hrv'] for s in valid) / n, 1)
    avg_rhr = round(sum(s.get('rhr', 0) or 0 for s in valid) / n, 1)
    avg_sleep = round(sum(s.get('sleepHours', 0) or 0 for s in valid) / n, 1)

    urgent = sum(1 for s in summaries if s.get('status') == 'urgent')
    danger = sum(1 for s in summaries if s.get('status') == 'danger')
    warning = sum(1 for s in summaries if s.get('status') == 'warning')
    total = len(summaries)
    health_score = max(0, min(100, round(100 - (urgent * 30 + danger * 20 + warning * 10) / total)))

    return {
        'totalAthletes': total,
        'avgHRV': avg_hrv,
        'avgRHR': avg_rhr,
        'avgSleep': avg_sleep,
        'healthScore': health_score,
        'athletes': summaries,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Training Metrics
# ═══════════════════════════════════════════════════════════════════════════════

def create_training_metric(user_id: int, data: dict) -> dict:
    now = datetime.utcnow().isoformat()
    date = data.get('date') or now[:10]
    conn = get_db()
    cursor = conn.cursor()
    is_mysql = conn._is_mysql
    columns = [
        'user_id', 'date', 'distance', 'avg_split', 'avg_spm', 'max_hr', 'avg_hr', 'duration_minutes',
        'training_type', 'training_phase', 'intensity_score', 'volume_score', 'focus_area', 'coach_notes',
        'planned_load', 'actual_load', 'created_at',
    ]
    update_columns = [
        'distance', 'avg_split', 'avg_spm', 'max_hr', 'avg_hr', 'duration_minutes',
        'training_type', 'training_phase', 'intensity_score', 'volume_score', 'focus_area', 'coach_notes',
        'planned_load', 'actual_load',
    ]
    sql = _upsert_sql('training_metrics', columns, ['user_id', 'date'], update_columns, is_mysql)
    cursor.execute(sql, (
        user_id, date,
        data.get('distance'), data.get('avgSplit'), data.get('avgSPM'), data.get('maxHR'), data.get('avgHR'), data.get('duration'),
        data.get('trainingType'), data.get('trainingPhase'), data.get('intensityScore'), data.get('volumeScore'),
        data.get('focusArea'), data.get('coachNotes'), data.get('plannedLoad'), data.get('actualLoad'),
        now,
    ))
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_training_metric_by_id(row_id)


def get_training_metric_by_id(metric_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute('SELECT * FROM training_metrics WHERE id = ?', (metric_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_training_metrics(user_id: int, limit: int = 180) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM training_metrics WHERE user_id = ? ORDER BY date DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _load_indexed_metrics(user_id: int, table: str, columns: list[str], limit: int = 180) -> dict:
    """Load metrics indexed by date for quick lookup."""
    conn = get_db()
    cols = ', '.join(columns)
    rows = conn.execute(
        f'SELECT date, {cols} FROM {table} WHERE user_id = ? ORDER BY date DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()
    conn.close()
    return {r['date']: dict(r) for r in rows}


def get_training_impact(user_id: int, date: str) -> dict:
    """Compare health metrics 1-3 days after a training session vs the day before."""
    training_rows = list_training_metrics(user_id, limit=180)
    training_by_date = {t['date']: t for t in training_rows}
    training = training_by_date.get(date)
    if not training:
        return {'error': 'Training session not found'}

    health = _load_indexed_metrics(user_id, 'health_metrics', ['hrv', 'rhr', 'sleep_hours'], limit=180)

    def _delta(target_date: str, baseline_date: str, key: str):
        t = health.get(target_date, {}).get(key)
        b = health.get(baseline_date, {}).get(key)
        if t is None or b is None or b == 0:
            return None
        return round((t - b) / b * 100, 2)

    baseline_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
    impacts = []
    for offset in [1, 2, 3]:
        target_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=offset)).strftime('%Y-%m-%d')
        impacts.append({
            'day': offset,
            'date': target_date,
            'hrvChangePct': _delta(target_date, baseline_date, 'hrv'),
            'rhrChangePct': _delta(target_date, baseline_date, 'rhr'),
            'sleepChangePct': _delta(target_date, baseline_date, 'sleep_hours'),
            'hrv': health.get(target_date, {}).get('hrv'),
            'rhr': health.get(target_date, {}).get('rhr'),
            'sleepHours': health.get(target_date, {}).get('sleep_hours'),
        })

    return {
        'trainingDate': date,
        'training': training_metric_to_public(training),
        'baselineDate': baseline_date,
        'baseline': {
            'hrv': health.get(baseline_date, {}).get('hrv'),
            'rhr': health.get(baseline_date, {}).get('rhr'),
            'sleepHours': health.get(baseline_date, {}).get('sleep_hours'),
        },
        'impacts': impacts,
    }


def get_training_health_correlation(user_id: int, days: int = 28) -> dict:
    """Compute simple Pearson-like correlation between training load and health metrics."""
    training_rows = list_training_metrics(user_id, limit=days + 3)
    health_rows = list_health_metrics(user_id, limit=days + 3)

    # Pair training load on day D with health metrics on day D+1 (next morning)
    health_by_date = {h['date']: h for h in health_rows}
    pairs = []
    for t in training_rows:
        d = datetime.strptime(t['date'], '%Y-%m-%d') + timedelta(days=1)
        next_date = d.strftime('%Y-%m-%d')
        h = health_by_date.get(next_date)
        if not h:
            continue
        load = (t.get('intensity_score') or 5) * (t.get('volume_score') or 5)
        pairs.append({
            'date': t['date'],
            'load': load,
            'hrv': h.get('hrv'),
            'rhr': h.get('rhr'),
            'sleepHours': h.get('sleep_hours'),
        })

    def _corr(values_x, values_y):
        n = len(values_x)
        if n < 3:
            return None
        mean_x = sum(values_x) / n
        mean_y = sum(values_y) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(values_x, values_y))
        den_x = math.sqrt(sum((x - mean_x) ** 2 for x in values_x))
        den_y = math.sqrt(sum((y - mean_y) ** 2 for y in values_y))
        if den_x == 0 or den_y == 0:
            return None
        return round(num / (den_x * den_y), 3)

    return {
        'days': days,
        'pairs': pairs,
        'correlations': {
            'loadVsHrv': _corr([p['load'] for p in pairs], [p['hrv'] for p in pairs]),
            'loadVsRhr': _corr([p['load'] for p in pairs], [p['rhr'] for p in pairs]),
            'loadVsSleep': _corr([p['load'] for p in pairs], [p['sleepHours'] for p in pairs]),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Alerts
# ═══════════════════════════════════════════════════════════════════════════════

def create_alert(data: dict) -> dict:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alerts
            (user_id, level, type, message, status, rule_id, triggered_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data['user_id'], data['level'], data['type'], data['message'],
          data.get('status', 'active'), data.get('rule_id'), data.get('triggered_at', now), now, now))
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_alert_by_id(alert_id)


def get_alert_by_id(alert_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute('SELECT * FROM alerts WHERE id = ?', (alert_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_alerts_for_user(user_id: int, limit: int = 100, status: str = None) -> list[dict]:
    conn = get_db()
    sql = 'SELECT * FROM alerts WHERE user_id = ?'
    params = [user_id]
    if status:
        sql += ' AND status = ?'
        params.append(status)
    sql += ' ORDER BY triggered_at DESC LIMIT ?'
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_alerts_for_coach(coach_id: int, limit: int = 100, status: str = None) -> list[dict]:
    conn = get_db()
    sql = '''
        SELECT a.* FROM alerts a
        JOIN coach_athlete_links l ON l.athlete_id = a.user_id
        WHERE l.coach_id = ?
    '''
    params = [coach_id]
    if status:
        sql += ' AND a.status = ?'
        params.append(status)
    sql += ' ORDER BY a.triggered_at DESC LIMIT ?'
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_alert_status(alert_id: int, status: str, user_id: int | None = None) -> dict | None:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    row = conn.execute('SELECT * FROM alerts WHERE id = ?', (alert_id,)).fetchone()
    if not row:
        conn.close()
        return None
    resolved_at = now if status in ('resolved', 'dismissed') else None
    conn.execute(
        'UPDATE alerts SET status = ?, resolved_at = ?, updated_at = ? WHERE id = ?',
        (status, resolved_at, now, alert_id)
    )
    conn.commit()
    conn.close()
    return get_alert_by_id(alert_id)


# ═══════════════════════════════════════════════════════════════════════════════
#  Alert Rules
# ═══════════════════════════════════════════════════════════════════════════════

def create_alert_rule(data: dict) -> dict:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alert_rules (name, level, sport, conditions, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (data['name'], data['level'], data.get('sport', '*'),
          json.dumps(data.get('conditions', {})), data.get('is_active', True), now, now))
    rule_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_alert_rule_by_id(rule_id)


def get_alert_rule_by_id(rule_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute('SELECT * FROM alert_rules WHERE id = ?', (rule_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_alert_rules(sport: str = None, active_only: bool = True) -> list[dict]:
    conn = get_db()
    sql = 'SELECT * FROM alert_rules WHERE 1=1'
    params = []
    if active_only:
        sql += ' AND is_active = 1'
    if sport:
        sql += " AND (sport = ? OR sport = '*')"
        params.append(sport)
    sql += ' ORDER BY level, name'
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    rules = []
    for r in rows:
        d = dict(r)
        try:
            d['conditions'] = json.loads(d.get('conditions') or '{}')
        except (json.JSONDecodeError, TypeError):
            d['conditions'] = {}
        rules.append(d)
    return rules


def evaluate_alerts_for_user(user_id: int) -> list[dict]:
    user = get_user_by_id(user_id)
    if not user or user['role'] != 'athlete':
        return []

    metrics = list_health_metrics(user_id, limit=7)
    checkins = list_checkins(user_id, limit=7)
    rules = list_alert_rules(sport=user.get('sport'), active_only=True)

    created = []
    for rule in rules:
        cond = rule.get('conditions', {})
        matched = False
        msg = cond.get('message', rule['name'])

        if metrics and cond.get('metric') in ('hrv', 'rhr', 'sleep_hours'):
            vals = [m[cond['metric']] for m in metrics if m[cond['metric']] is not None]
            if vals:
                latest = vals[0]
                if cond.get('operator') == '<' and latest < cond.get('threshold', 0):
                    matched = True
                elif cond.get('operator') == '>' and latest > cond.get('threshold', 0):
                    matched = True

        if checkins and cond.get('checkin'):
            key = cond['checkin']
            recent = [c[key] for c in checkins if c.get(key) is not None]
            if recent:
                if cond.get('operator') == '<' and recent[0] < cond.get('threshold', 0):
                    matched = True
                elif cond.get('operator') == '>' and recent[0] > cond.get('threshold', 0):
                    matched = True

        if cond.get('type') == 'trend' and len(metrics) >= 3:
            hrvs = [m['hrv'] for m in metrics[:3] if m['hrv'] is not None]
            rhrs = [m['rhr'] for m in metrics[:3] if m['rhr'] is not None]
            if len(hrvs) == 3 and len(rhrs) == 3:
                hrv_declining = hrvs[0] < hrvs[1] < hrvs[2]
                rhr_rising = rhrs[0] > rhrs[1] > rhrs[2]
                if hrv_declining and rhr_rising:
                    matched = True

        if matched:
            conn = get_db()
            existing = conn.execute(
                "SELECT id FROM alerts WHERE user_id = ? AND rule_id = ? AND status = 'active'",
                (user_id, rule['id'])
            ).fetchone()
            conn.close()
            if not existing:
                alert = create_alert({
                    'user_id': user_id,
                    'level': rule['level'],
                    'type': rule['name'],
                    'message': msg,
                    'rule_id': rule['id'],
                })
                created.append(alert)
    return created


# ═══════════════════════════════════════════════════════════════════════════════
#  Public serialization helpers
# ═══════════════════════════════════════════════════════════════════════════════

def checkin_to_public(c: dict) -> dict:
    return {
        'id': c['id'],
        'userId': c['user_id'],
        'date': c['date'],
        'mood': c['mood'],
        'motivation': c['motivation'],
        'fatigue': c['fatigue'],
        'challenge': c.get('challenge', 'none'),
        'journal': c.get('journal', ''),
        'createdAt': c['created_at'],
    }


def health_metric_to_public(m: dict) -> dict:
    return {
        'id': m['id'],
        'userId': m['user_id'],
        'date': m['date'],
        'day': m['date'],
        'hrv': m['hrv'],
        'rhr': m['rhr'],
        'sleepHours': m['sleep_hours'],
        'sleepDeep': m['sleep_deep_pct'],
        'sleepREM': m['sleep_rem_pct'],
        'spo2': m['spo2'],
        'respiratoryRate': m['respiratory_rate'],
        'skinTemp': m['skin_temp'],
        'source': m.get('source', 'manual'),
        'createdAt': m['created_at'],
    }


def training_metric_to_public(m: dict) -> dict:
    return {
        'id': m['id'],
        'userId': m['user_id'],
        'date': m['date'],
        'day': m['date'],
        'distance': m['distance'],
        'avgSplit': m['avg_split'],
        'avgSPM': m['avg_spm'],
        'maxHR': m['max_hr'],
        'avgHR': m['avg_hr'],
        'duration': m['duration_minutes'],
        'trainingType': m.get('training_type'),
        'trainingPhase': m.get('training_phase'),
        'intensityScore': m.get('intensity_score'),
        'volumeScore': m.get('volume_score'),
        'focusArea': m.get('focus_area'),
        'coachNotes': m.get('coach_notes'),
        'plannedLoad': m.get('planned_load'),
        'actualLoad': m.get('actual_load'),
        'createdAt': m['created_at'],
    }


def alert_to_public(a: dict, athlete: dict = None) -> dict:
    return {
        'id': a['id'],
        'userId': a['user_id'],
        'athleteId': a['user_id'],
        'athleteName': athlete['name'] if athlete else None,
        'level': a['level'],
        'type': a['type'],
        'message': a['message'],
        'status': a['status'],
        'ruleId': a.get('rule_id'),
        'triggeredAt': a['triggered_at'],
        'resolvedAt': a.get('resolved_at'),
        'createdAt': a['created_at'],
    }


def coach_athlete_link_to_public(link: dict, athlete: dict = None) -> dict:
        return {
            'id': link['id'],
            'coachId': link['coach_id'],
            'athleteId': link['athlete_id'],
            'role': link.get('role', 'primary'),
            'athlete': user_to_public(athlete) if athlete else None,
            'createdAt': link['created_at'],
        }
