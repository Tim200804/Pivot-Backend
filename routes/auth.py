from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
import bcrypt
from models import create_user, get_user_by_email, get_user_by_id, user_to_public

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    required = ['email', 'password', 'name', 'role']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'success': False, 'message': f'Missing fields: {", ".join(missing)}'}), 400

    email = data['email'].strip().lower()
    if len(data['password']) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    if data['role'] not in ('athlete', 'coach'):
        return jsonify({'success': False, 'message': 'Role must be athlete or coach'}), 400

    if get_user_by_email(email):
        return jsonify({'success': False, 'message': 'Email already registered'}), 409

    password_hash = _hash_password(data['password'])
    user = create_user(data, password_hash)
    token = create_access_token(identity=str(user['id']))

    return jsonify({
        'success': True,
        'token': token,
        'user': user_to_public(user)
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required'}), 400

    user = get_user_by_email(email)
    if not user or not _check_password(password, user['password_hash']):
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

    token = create_access_token(identity=str(user['id']))
    return jsonify({
        'success': True,
        'token': token,
        'user': user_to_public(user)
    })


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    return jsonify({'success': True, 'user': user_to_public(user)})
