import sqlite3
import os
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
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def create_user(data: dict, password_hash: str) -> dict:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (email, password_hash, name, role, sport, school, team_name,
                           position, coach_role, height, weight, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        now, now
    ))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_user_by_id(user_id)


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


def user_to_public(user: dict) -> dict:
    """Strip sensitive fields for API responses."""
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
        'createdAt': user['created_at'],
    }
