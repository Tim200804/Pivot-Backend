"""Reset password for test@upenn.edu to the common test password."""
import sys
sys.path.insert(0, '.')

import bcrypt
from models import get_db

EMAIL = 'test@upenn.edu'
PASSWORD = '12345678ABC'

password_hash = bcrypt.hashpw(PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
conn = get_db()
conn.execute('UPDATE users SET password_hash = ? WHERE email = ?', (password_hash, EMAIL))
conn.commit()
conn.close()

# Verify
conn = get_db()
row = conn.execute('SELECT password_hash FROM users WHERE email = ?', (EMAIL,)).fetchone()
conn.close()
ok = bcrypt.checkpw(PASSWORD.encode('utf-8'), row['password_hash'].encode('utf-8'))
print(f'Updated {EMAIL}: password verification = {ok}')
