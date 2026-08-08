import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEED_DB_PATH = os.path.join(BASE_DIR, 'railway_seed.db')


def _has_db_config() -> bool:
    return bool(
        os.environ.get('DATABASE_URL')
        or os.environ.get('MYSQL_URL')
        or os.environ.get('MYSQL_PUBLIC_URL')
        or os.environ.get('MYSQL_PRIVATE_URL')
        or os.environ.get('MYSQLHOST')
    )


# Railway should inject DATABASE_URL when MySQL is linked, but if it does not
# (e.g. the plugin is not connected to this service), fall back to the bundled
# SQLite seed database so the deployed backend still serves real demo data.
if not _has_db_config() and os.path.exists(SEED_DB_PATH):
    os.environ['DATABASE_URL'] = f'sqlite:///{SEED_DB_PATH}'
    print(f"[startup] No DB env vars found; using bundled seed DB at {SEED_DB_PATH}")

from app import create_app
from models import init_db, DATABASE_URL

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
db_url = DATABASE_URL or ''
print(f"[startup] Active DATABASE_URL starts with: {db_url.split('://')[0] if db_url else 'none'}")
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
