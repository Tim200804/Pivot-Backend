import os
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# Only load .env file in local development. On Railway we rely on injected
# environment variables (DATABASE_URL / MYSQL_URL); loading a local .env here
# would overwrite them with development defaults.
def _is_local_development() -> bool:
    return not any(k.startswith('RAILWAY_') for k in os.environ) and os.environ.get('FLASK_ENV', 'development') == 'development'

if _is_local_development():
    load_dotenv()

from models import init_db
from routes.auth import auth_bp
from routes.ai import ai_bp
from routes.schools import schools_bp
from routes.messages import messages_bp
from routes.checkins import checkins_bp
from routes.health import health_bp
from routes.alerts import alerts_bp
from routes.interventions import interventions_bp


def create_app():
    app = Flask(__name__)

    # Config
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'dev-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 7 * 24 * 60 * 60  # 7 days in seconds

    # Cross-origin: frontend (codebuddy / GitHub Pages) and API (Railway) are different origins.
    # Browsers enforce this; the API must emit Access-Control-* headers (cannot "disable SOP").
    CORS(
        app,
        resources={r"/*": {
            "origins": "*",
            "allow_headers": ["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            "expose_headers": ["Content-Type"],
            "supports_credentials": False,
            "max_age": 86400,
        }},
    )
    JWTManager(app)

    # Belt-and-suspenders: always attach ACAO on API responses (including error paths)
    @app.after_request
    def add_cors_headers(response):
        origin = None
        try:
            from flask import request as flask_request
            origin = flask_request.headers.get('Origin')
        except Exception:
            origin = None
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Vary'] = 'Origin'
        elif 'Access-Control-Allow-Origin' not in response.headers:
            response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers.setdefault(
            'Access-Control-Allow-Headers',
            'Authorization, Content-Type, Accept, Origin, X-Requested-With',
        )
        response.headers.setdefault(
            'Access-Control-Allow-Methods',
            'GET, POST, PUT, DELETE, PATCH, OPTIONS',
        )
        return response

    # Routes
    app.register_blueprint(auth_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(schools_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(checkins_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(interventions_bp)

    # Health check
    @app.route('/api/health', methods=['GET'])
    def health():
        import os
        stats = {}
        try:
            from models import get_db
            conn = get_db()
            def _count(table):
                row = conn.execute(f'SELECT COUNT(*) AS c FROM {table}').fetchone()
                return row['c'] if row else 0
            stats['users'] = _count('users')
            stats['health_metrics'] = _count('health_metrics')
            stats['training_metrics'] = _count('training_metrics')
            stats['alerts'] = _count('alerts')
            stats['checkins'] = _count('checkins')
            stats['messages'] = _count('messages')
            stats['interventions'] = _count('interventions')
            stats['coach_athlete_links'] = _count('coach_athlete_links')
            conn.close()
        except Exception as e:
            stats['error'] = str(e)

        from models import DATABASE_URL as ACTIVE_DATABASE_URL
        seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'railway_seed.db')
        env_keys = {
            k: ('set' if v else 'empty')
            for k, v in os.environ.items()
            if any(x in k.upper() for x in ['DATABASE', 'MYSQL', 'RAILWAY', 'SQL'])
        }
        stats['debug'] = {
            'cwd': os.getcwd(),
            'active_db_url_prefix': ACTIVE_DATABASE_URL.split('://')[0] if ACTIVE_DATABASE_URL else None,
            'active_db_url_host': ACTIVE_DATABASE_URL.split('@')[-1].split('/')[0].split(':')[0] if ACTIVE_DATABASE_URL and '@' in ACTIVE_DATABASE_URL else None,
            'seed_path': seed_path,
            'seed_exists': os.path.exists(seed_path),
            'env_keys': env_keys,
        }
        return {'status': 'ok', 'service': 'pivot-backend', 'stats': stats}

    # Init DB on first request (lazy init)
    @app.before_request
    def init_once():
        if not getattr(app, '_db_initialized', False):
            init_db()
            app._db_initialized = True

    return app


if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 5000))
    app = create_app()
    app.run(host='0.0.0.0', port=port, debug=True)
