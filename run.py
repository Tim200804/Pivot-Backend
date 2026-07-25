import os
from app import create_app

port = int(os.environ.get('FLASK_PORT', 5000))
app = create_app()

if __name__ == '__main__':
    print(f"🚀 Pivot Backend running at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
