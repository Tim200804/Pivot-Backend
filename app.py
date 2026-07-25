import os
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

load_dotenv()

from models import init_db
from routes.auth import auth_bp


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

    # Health check
    @app.route('/api/health', methods=['GET'])
    def health():
        return {'status': 'ok', 'service': 'pivot-backend'}

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
