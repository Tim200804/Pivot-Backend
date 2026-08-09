"""Reset all athlete test account passwords to the common test password."""
import sys
sys.path.insert(0, '.')

import bcrypt
from models import get_db

PASSWORD = '12345678ABC'
password_hash = bcrypt.hashpw(PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

conn = get_db()
conn.execute("UPDATE users SET password_hash = ? WHERE role = 'athlete'", (password_hash,))
conn.commit()

rows = conn.execute("SELECT email FROM users WHERE role = 'athlete'").fetchall()
conn.close()

print(f'Reset password for {len(rows)} athlete account(s) to {PASSWORD}:')
for row in rows:
    print(f'  - {row["email"]}')
