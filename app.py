import os
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

load_dotenv()

from models import init_db
from routes.auth import auth_bp
from routes.ai import ai_bp
from routes.schools import schools_bp
from routes.messages import messages_bp
from routes.checkins import checkins_bp
from routes.health import health_bp
from routes.alerts import alerts_bp


def create_app():
    app = Flask(__name__)

    # Config
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'dev-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 7 * 24 * 60 * 60  # 7 days in seconds

    # Extensions
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    JWTManager(app)

    # Routes
    app.register_blueprint(auth_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(schools_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(checkins_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(alerts_bp)

    # Health check
    @app.route('/api/health', methods=['GET'])
    def health():
        import os
        stats = {}
        try:
            from models import get_db
            conn = get_db()
            stats['users'] = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            stats['health_metrics'] = conn.execute('SELECT COUNT(*) FROM health_metrics').fetchone()[0]
            stats['training_metrics'] = conn.execute('SELECT COUNT(*) FROM training_metrics').fetchone()[0]
            stats['alerts'] = conn.execute('SELECT COUNT(*) FROM alerts').fetchone()[0]
            stats['checkins'] = conn.execute('SELECT COUNT(*) FROM checkins').fetchone()[0]
            stats['messages'] = conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]
            conn.close()
        except Exception as e:
            stats['error'] = str(e)

        db_url = os.environ.get('DATABASE_URL', '')
        seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'railway_seed.db')
        stats['debug'] = {
            'cwd': os.getcwd(),
            'db_url_prefix': db_url[:20] + '...' if db_url else None,
            'seed_path': seed_path,
            'seed_exists': os.path.exists(seed_path),
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
