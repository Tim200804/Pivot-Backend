import os
import json
import math
from datetime import datetime, timedelta
from urllib.parse import urlparse

# ═══════════════════════════════════════════════════════════════════════════════
#  Database URL parsing
# ═══════════════════════════════════════════════════════════════════════════════

def _resolve_database_url() -> str:
    """Resolve DB URL from Railway-injected env vars or local defaults."""
    url = (
        os.environ.get('DATABASE_URL')
        or os.environ.get('MYSQL_URL')
        or os.environ.get('MYSQL_PUBLIC_URL')
        or os.environ.get('MYSQL_PRIVATE_URL')
    )
    if url:
        return url

    # Railway MySQL plugin also injects individual connection variables.
    # If the service is linked to MySQL but no URL variable is present, build
    # the URL from these pieces.
    host = os.environ.get('MYSQLHOST')
    if host:
        user = os.environ.get('MYSQLUSER', 'root')
        password = os.environ.get('MYSQLPASSWORD', '')
        port = os.environ.get('MYSQLPORT', '3306')
        database = os.environ.get('MYSQLDATABASE', 'railway')
        return f"mysql://{user}:{password}@{host}:{port}/{database}"

    return 'sqlite:///pivot.db'


DATABASE_URL = _resolve_database_url()


def _is_mysql() -> bool:
    return isinstance(DATABASE_URL, str) and DATABASE_URL.startswith('mysql')


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

    _create_index_if_not_exists(conn, 'idx_checkins_user_date_desc', 'checkins', 'user_id, date DESC')

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

    # ── interventions ──
    if is_mysql:
        conn.execute('''CREATE TABLE IF NOT EXISTS interventions (
            id INT PRIMARY KEY AUTO_INCREMENT,
            alert_id INT,
            athlete_id INT NOT NULL,
            coach_id INT NOT NULL,
            coach_role VARCHAR(50),
            intervention_type VARCHAR(50) NOT NULL,
            description TEXT,
            actions_taken TEXT,
            status VARCHAR(50) NOT NULL DEFAULT 'planned' CHECK(status IN ('planned', 'in_progress', 'completed', 'cancelled')),
            started_at VARCHAR(30) NOT NULL,
            completed_at VARCHAR(30),
            effectiveness_score INT,
            outcome_notes TEXT,
            created_at VARCHAR(30) NOT NULL,
            updated_at VARCHAR(30) NOT NULL,
            FOREIGN KEY (alert_id) REFERENCES alerts(id),
            FOREIGN KEY (athlete_id) REFERENCES users(id),
            FOREIGN KEY (coach_id) REFERENCES users(id)
        )''')
    else:
        conn.execute('''CREATE TABLE IF NOT EXISTS interventions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER,
            athlete_id INTEGER NOT NULL,
            coach_id INTEGER NOT NULL,
            coach_role TEXT,
            intervention_type TEXT NOT NULL,
            description TEXT,
            actions_taken TEXT,
            status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned', 'in_progress', 'completed', 'cancelled')),
            started_at TEXT NOT NULL,
            completed_at TEXT,
            effectiveness_score INTEGER,
            outcome_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (alert_id) REFERENCES alerts(id),
            FOREIGN KEY (athlete_id) REFERENCES users(id),
            FOREIGN KEY (coach_id) REFERENCES users(id)
        )''')

    _create_index_if_not_exists(conn, 'idx_interventions_alert', 'interventions', 'alert_id')
    _create_index_if_not_exists(conn, 'idx_interventions_athlete', 'interventions', 'athlete_id')
    _create_index_if_not_exists(conn, 'idx_interventions_coach', 'interventions', 'coach_id')

    # ── password_reset_codes ──
    if is_mysql:
        conn.execute('''CREATE TABLE IF NOT EXISTS password_reset_codes (
            id INT PRIMARY KEY AUTO_INCREMENT,
            email VARCHAR(255) NOT NULL,
            code VARCHAR(6) NOT NULL,
            expires_at VARCHAR(30) NOT NULL,
            used INT NOT NULL DEFAULT 0,
            created_at VARCHAR(30) NOT NULL
        )''')
    else:
        conn.execute('''CREATE TABLE IF NOT EXISTS password_reset_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )''')

    _create_index_if_not_exists(conn, 'idx_reset_codes_email', 'password_reset_codes', 'email, created_at')

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
#  Password Reset
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_password_reset_table(conn):
    """Ensure the password_reset_codes table exists (runtime migration safety)."""
    is_mysql = conn._is_mysql
    try:
        conn.execute("SELECT 1 FROM password_reset_codes LIMIT 1")
    except Exception:
        if is_mysql:
            conn.execute('''CREATE TABLE IF NOT EXISTS password_reset_codes (
                id INT PRIMARY KEY AUTO_INCREMENT,
                email VARCHAR(255) NOT NULL,
                code VARCHAR(6) NOT NULL,
                expires_at VARCHAR(30) NOT NULL,
                used INT NOT NULL DEFAULT 0,
                created_at VARCHAR(30) NOT NULL
            )''')
            conn.execute("CREATE INDEX idx_reset_codes_email ON password_reset_codes (email, created_at)")
        else:
            conn.execute('''CREATE TABLE IF NOT EXISTS password_reset_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )''')
            conn.execute("CREATE INDEX idx_reset_codes_email ON password_reset_codes (email, created_at)")
        conn.commit()


def create_reset_code(email: str, code: str) -> None:
    """Store a new password reset code. Invalidates any existing codes for this email."""
    now = datetime.utcnow().isoformat()
    expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    conn = get_db()
    _ensure_password_reset_table(conn)
    # Mark any existing codes as used
    conn.execute("UPDATE password_reset_codes SET used = 1 WHERE email = ? AND used = 0", (email,))
    conn.execute('''
        INSERT INTO password_reset_codes (email, code, expires_at, used, created_at)
        VALUES (?, ?, ?, 0, ?)
    ''', (email, code, expires, now))
    conn.commit()
    conn.close()


def get_valid_reset_code(email: str, code: str) -> dict | None:
    """Return the reset code record if it exists, is unused, and not expired."""
    conn = get_db()
    _ensure_password_reset_table(conn)
    row = conn.execute('''
        SELECT * FROM password_reset_codes
        WHERE email = ? AND code = ? AND used = 0
        ORDER BY created_at DESC LIMIT 1
    ''', (email, code)).fetchone()
    conn.close()
    if not row:
        return None
    record = dict(row)
    if datetime.utcnow().isoformat() > record['expires_at']:
        return None
    return record


def mark_reset_code_used(code_id: int) -> None:
    conn = get_db()
    _ensure_password_reset_table(conn)
    conn.execute('UPDATE password_reset_codes SET used = 1 WHERE id = ?', (code_id,))
    conn.commit()
    conn.close()


def cleanup_expired_reset_codes() -> None:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    _ensure_password_reset_table(conn)
    conn.execute('DELETE FROM password_reset_codes WHERE expires_at < ?', (now,))
    conn.commit()
    conn.close()


def update_user_password(user_id: int, password_hash: str) -> dict | None:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute(
        'UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?',
        (password_hash, now, user_id)
    )
    conn.commit()
    conn.close()
    return get_user_by_id(user_id)


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


def list_checkins(user_id: int, limit: int = 30, offset: int = 0, exclude_journal: bool = False) -> list[dict]:
    conn = get_db()
    columns = (
        'id, user_id, date, mood, motivation, fatigue, challenge, created_at'
        if exclude_journal
        else 'id, user_id, date, mood, motivation, fatigue, challenge, journal, created_at'
    )
    rows = conn.execute(
        f'SELECT {columns} FROM checkins WHERE user_id = ? ORDER BY date DESC LIMIT ? OFFSET ?',
        (user_id, limit, offset)
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
#  Interventions
# ═══════════════════════════════════════════════════════════════════════════════

INTERVENTION_TYPES = [
    'conversation',
    'training_adjustment',
    'rest_day',
    'mental_skill',
    'nutrition',
    'medical_referral',
    'sleep_hygiene',
    'other',
]


def create_intervention(data: dict) -> dict:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO interventions
            (alert_id, athlete_id, coach_id, coach_role, intervention_type, description,
             actions_taken, status, started_at, completed_at, effectiveness_score,
             outcome_notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('alert_id'),
        data['athlete_id'],
        data['coach_id'],
        data.get('coach_role'),
        data['intervention_type'],
        data.get('description', ''),
        json.dumps(data.get('actions_taken', [])) if isinstance(data.get('actions_taken'), list) else (data.get('actions_taken') or ''),
        data.get('status', 'planned'),
        data.get('started_at', now),
        data.get('completed_at'),
        data.get('effectiveness_score'),
        data.get('outcome_notes', ''),
        now, now,
    ))
    intervention_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # If linked to an alert and intervention is in_progress, update alert status
    if data.get('alert_id') and data.get('status') == 'in_progress':
        update_alert_status(data['alert_id'], 'active', user_id=data['coach_id'])

    return get_intervention_by_id(intervention_id)


def get_intervention_by_id(intervention_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute('SELECT * FROM interventions WHERE id = ?', (intervention_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_interventions(athlete_id: int | None = None, alert_id: int | None = None,
                       coach_id: int | None = None, status: str | None = None,
                       limit: int = 100) -> list[dict]:
    conn = get_db()
    sql = 'SELECT * FROM interventions WHERE 1=1'
    params = []
    if athlete_id is not None:
        sql += ' AND athlete_id = ?'
        params.append(athlete_id)
    if alert_id is not None:
        sql += ' AND alert_id = ?'
        params.append(alert_id)
    if coach_id is not None:
        sql += ' AND coach_id = ?'
        params.append(coach_id)
    if status is not None:
        sql += ' AND status = ?'
        params.append(status)
    sql += ' ORDER BY started_at DESC LIMIT ?'
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_intervention(intervention_id: int, data: dict) -> dict | None:
    now = datetime.utcnow().isoformat()
    intervention = get_intervention_by_id(intervention_id)
    if not intervention:
        return None

    fields = []
    values = []
    if 'intervention_type' in data:
        fields.append('intervention_type = ?')
        values.append(data['intervention_type'])
    if 'description' in data:
        fields.append('description = ?')
        values.append(data['description'])
    if 'actions_taken' in data:
        fields.append('actions_taken = ?')
        actions = data['actions_taken']
        if isinstance(actions, list):
            actions = json.dumps(actions)
        values.append(actions or '')
    if 'status' in data:
        fields.append('status = ?')
        values.append(data['status'])
    if 'completed_at' in data:
        fields.append('completed_at = ?')
        values.append(data['completed_at'])
    if 'effectiveness_score' in data:
        fields.append('effectiveness_score = ?')
        values.append(data['effectiveness_score'])
    if 'outcome_notes' in data:
        fields.append('outcome_notes = ?')
        values.append(data['outcome_notes'])
    if not fields:
        return intervention

    fields.append('updated_at = ?')
    values.append(now)
    values.append(intervention_id)

    conn = get_db()
    conn.execute(f"UPDATE interventions SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()

    updated = get_intervention_by_id(intervention_id)
    # If status changed to completed and linked alert exists, mark alert resolved
    if data.get('status') == 'completed' and updated and updated.get('alert_id'):
        update_alert_status(updated['alert_id'], 'resolved', user_id=updated['coach_id'])
    return updated


def delete_intervention(intervention_id: int) -> bool:
    conn = get_db()
    conn.execute('DELETE FROM interventions WHERE id = ?', (intervention_id,))
    conn.commit()
    conn.close()
    return True


def intervention_to_public(i: dict, include_coach: bool = True, include_athlete: bool = True) -> dict:
    actions = i.get('actions_taken', '')
    if isinstance(actions, str) and actions.strip().startswith('['):
        try:
            actions = json.loads(actions)
        except (json.JSONDecodeError, TypeError):
            actions = actions.split('\n') if actions else []
    elif isinstance(actions, str):
        actions = actions.split('\n') if actions else []

    result = {
        'id': i['id'],
        'alertId': i.get('alert_id'),
        'athleteId': i['athlete_id'],
        'coachId': i['coach_id'],
        'coachRole': i.get('coach_role'),
        'interventionType': i['intervention_type'],
        'description': i.get('description'),
        'actionsTaken': actions,
        'status': i['status'],
        'startedAt': i['started_at'],
        'completedAt': i.get('completed_at'),
        'effectivenessScore': i.get('effectiveness_score'),
        'outcomeNotes': i.get('outcome_notes'),
        'createdAt': i['created_at'],
        'updatedAt': i['updated_at'],
    }
    if include_coach and i.get('coach_id'):
        coach = get_user_by_id(i['coach_id'])
        if coach:
            result['coachName'] = coach.get('name')
            result['coachEmail'] = coach.get('email')
    if include_athlete and i.get('athlete_id'):
        athlete = get_user_by_id(i['athlete_id'])
        if athlete:
            result['athleteName'] = athlete.get('name')
            result['athleteEmail'] = athlete.get('email')
    return result


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


def generate_training_adjustment_suggestion(user_id: int, days: int = 14) -> dict:
    """Generate an evidence-based training adjustment suggestion from recent load and recovery data.

    This function combines rule-based sports-science heuristics with correlation insights.
    It returns a structured recommendation that can be rendered directly in the UI or fed to an LLM.
    """
    training_rows = list_training_metrics(user_id, limit=days + 7)
    health_rows = list_health_metrics(user_id, limit=days + 7)
    latest_summary = get_latest_health_summary(user_id)

    if not training_rows or not health_rows:
        return {
            'hasEnoughData': False,
            'suggestion': 'Not enough recent data to generate a training suggestion.',
            'rationale': 'Keep logging training and health metrics for at least 3 days.',
            'actions': ['Log today\'s training session', 'Complete the evening check-in', 'Wear recovery device tonight'],
            'riskLevel': 'unknown',
        }

    # Sort chronologically for trend analysis
    training_rows = sorted(training_rows, key=lambda r: r['date'])
    health_rows = sorted(health_rows, key=lambda r: r['date'])

    # Recent load trend (last 3 sessions vs prior 3)
    recent_training = training_rows[-3:]
    prior_training = training_rows[-6:-3] if len(training_rows) >= 6 else training_rows[:3]

    def avg_load(rows):
        loads = [(r.get('intensity_score') or 5) * (r.get('volume_score') or 5) for r in rows]
        return round(sum(loads) / len(loads), 1) if loads else 0

    recent_load = avg_load(recent_training)
    prior_load = avg_load(prior_training)
    load_delta_pct = round((recent_load - prior_load) / prior_load * 100, 1) if prior_load else 0

    # Recovery trend (last 3 health records vs prior 3)
    recent_health = health_rows[-3:]
    prior_health = health_rows[-6:-3] if len(health_rows) >= 6 else health_rows[:3]

    avg_hrv_recent = round(sum(h.get('hrv') or 0 for h in recent_health) / len(recent_health), 1)
    avg_hrv_prior = round(sum(h.get('hrv') or 0 for h in prior_health) / len(prior_health), 1)
    hrv_delta = round(avg_hrv_recent - avg_hrv_prior, 1)
    hrv_delta_pct = round(hrv_delta / avg_hrv_prior * 100, 1) if avg_hrv_prior else 0

    avg_rhr_recent = round(sum(h.get('rhr') or 0 for h in recent_health) / len(recent_health), 1)
    avg_rhr_prior = round(sum(h.get('rhr') or 0 for h in prior_health) / len(prior_health), 1)
    rhr_delta = round(avg_rhr_recent - avg_rhr_prior, 1)

    sleep_recent = round(sum(h.get('sleep_hours') or 0 for h in recent_health) / len(recent_health), 1)
    sleep_prior = round(sum(h.get('sleep_hours') or 0 for h in prior_health) / len(prior_health), 1)

    # Correlation insights
    correlation = get_training_health_correlation(user_id, days=days)
    corr_hrv = correlation.get('correlations', {}).get('loadVsHrv')
    corr_rhr = correlation.get('correlations', {}).get('loadVsRhr')

    # Build rationale and recommendation
    risk_level = 'low'
    reasons = []
    actions = []

    if recent_load >= 49 and hrv_delta_pct <= -5:
        risk_level = 'high'
        reasons.append(f'High recent load (load score {recent_load}) is paired with a {abs(hrv_delta_pct)}% HRV drop.')
        actions.append('Reduce intensity by 20-30% for the next 1-2 sessions.')
        actions.append('Replace one hard session with active recovery or technique work.')
        actions.append('Prioritize 8+ hours of sleep and hydration monitoring.')
    elif recent_load >= 40 and rhr_delta >= 4:
        risk_level = 'high'
        reasons.append(f'Resting heart rate is up {rhr_delta} bpm while training load is elevated (score {recent_load}).')
        actions.append('Add a full rest day within the next 48 hours.')
        actions.append('Shorten tomorrow\'s session by 20% and keep it in UT2.')
        actions.append('Review nutrition and hydration around training.')
    elif load_delta_pct >= 30 and hrv_delta_pct <= -3:
        risk_level = 'moderate'
        reasons.append(f'Load increased {load_delta_pct}% recently and HRV is starting to decline.')
        actions.append('Hold volume steady; do not add more load this week.')
        actions.append('Increase recovery modalities (stretching, massage, cool-down).')
    elif hrv_delta_pct >= 5 and recent_load < 30:
        risk_level = 'low'
        reasons.append('HRV is improving and recent load is low; recovery capacity looks good.')
        actions.append('You can gradually add one quality session (intervals or tempo) this week.')
        actions.append('Keep sleep and nutrition consistent to protect the rebound.')
    elif sleep_recent < 6 and recent_load >= 30:
        risk_level = 'moderate'
        reasons.append(f'Sleep average dropped to {sleep_recent}h while load remains significant.')
        actions.append('Move hard sessions earlier in the day; avoid late screens.')
        actions.append('Use a 20-minute nap or relaxation breathing before bed.')
    else:
        risk_level = 'low'
        reasons.append('Recent load and recovery signals are in balance.')
        actions.append('Continue current training plan with normal weekly progression.')
        actions.append('Monitor HRV and sleep over the next 3 days.')

    # Add correlation-based nuance
    if corr_hrv is not None and corr_hrv < -0.3:
        reasons.append(f'Training load shows a {abs(corr_hrv)} negative correlation with HRV, confirming high load suppresses recovery.')
    if corr_rhr is not None and corr_rhr > 0.3:
        reasons.append(f'Training load shows a {corr_rhr} positive correlation with RHR, suggesting incomplete recovery after hard days.')

    suggestion_text = (
        f"{ 'Reduce load immediately' if risk_level == 'high' else ('Proceed with caution' if risk_level == 'moderate' else 'Maintain or progress carefully') } — "
        f"recent load is {recent_load} (up {load_delta_pct}% vs prior block), HRV moved {hrv_delta_pct}%, and sleep averaged {sleep_recent}h. "
        + reasons[0]
    )

    return {
        'hasEnoughData': True,
        'suggestion': suggestion_text,
        'rationale': reasons,
        'actions': actions,
        'riskLevel': risk_level,
        'metrics': {
            'recentLoad': recent_load,
            'priorLoad': prior_load,
            'loadDeltaPct': load_delta_pct,
            'avgHrvRecent': avg_hrv_recent,
            'avgHrvPrior': avg_hrv_prior,
            'hrvDeltaPct': hrv_delta_pct,
            'rhrDelta': rhr_delta,
            'sleepRecent': sleep_recent,
            'sleepPrior': sleep_prior,
            'correlation': correlation.get('correlations'),
        },
        'latestSummary': latest_summary,
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
