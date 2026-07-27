import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.environ.get('DATABASE_URL', 'sqlite:///pivot.db').replace('sqlite:///', '')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
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
        )
    ''')
    # Migration for existing tables created before the preferences column existed
    cols = [r['name'] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if 'preferences' not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN preferences TEXT NOT NULL DEFAULT '{}'")

    # Coach → Athlete direct messages (e.g. "I've sent a note about your alert")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
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
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id, created_at DESC)')
    conn.commit()
    conn.close()


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


def update_user_preferences(user_id: int, prefs: dict) -> dict | None:
    """Merge the given preference patch into the user's stored preferences."""
    now = datetime.utcnow().isoformat()
    conn = get_db()
    row = conn.execute('SELECT preferences FROM users WHERE id = ?', (user_id,)).fetchone()
    if not row:
        conn.close()
        return None
    try:
        current = json.loads(row['preferences'] or '{}')
    except (json.JSONDecodeError, TypeError):
        current = _default_preferences()
    # Whitelist of editable keys
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
    """Strip sensitive fields for API responses."""
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


# ─── Messages ───

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
    """Messages a coach has sent (so they can see delivery history)."""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM messages WHERE sender_id = ? ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_message_read(msg_id: int, user_id: int) -> dict | None:
    """Mark a message read; only the recipient may mark it."""
    now = datetime.utcnow().isoformat()
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM messages WHERE id = ? AND recipient_id = ?',
        (msg_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        return None
    if not row['read_at']:
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
