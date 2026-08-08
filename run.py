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

# When running on Railway (MySQL) with a bundled SQLite seed file, auto-seed
# the database if it is empty. This avoids manual SQL copy-paste in the
# Railway Console and its 32KB paste limit.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEED_DB_PATH = os.path.join(BASE_DIR, 'railway_seed.db')
db_url = os.environ.get('DATABASE_URL', '')
print(f"[startup] DATABASE_URL starts with mysql: {db_url.startswith('mysql')}")
print(f"[startup] Seed DB exists at {SEED_DB_PATH}: {os.path.exists(SEED_DB_PATH)}")

if db_url.startswith('mysql') and os.path.exists(SEED_DB_PATH):
    try:
        from sync_to_railway import seed_railway_from_bundled
        seeded = seed_railway_from_bundled(SEED_DB_PATH)
        print(f"[startup] Bundled seed finished: {seeded} rows")
    except Exception as e:
        import traceback
        print(f"[startup] Bundled seed failed: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_ENV') != 'production'
    print(f"Pivot Backend running at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
