import os
from app import create_app
from models import init_db

port = int(os.environ.get('PORT', os.environ.get('FLASK_PORT', 5000)))
app = create_app()

# Eagerly initialize the database on startup. This ensures tables are created
# in serverless / container environments (e.g. Railway) even before the first
# HTTP request arrives. init_db() is idempotent so it is safe to call on every
# worker boot.
try:
    init_db()
    print("[startup] Database initialized successfully")
except Exception as e:
    print(f"[startup] Database initialization failed: {e}")

if __name__ == '__main__':
    debug = os.environ.get('FLASK_ENV') != 'production'
    print(f"Pivot Backend running at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
