from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
import bcrypt
import re
from models import create_user, get_user_by_email, get_user_by_id, update_user_preferences, user_to_public, list_coaches
from models import create_reset_code, get_valid_reset_code, mark_reset_code_used, update_user_password
from email_service import generate_reset_code, send_reset_email
from options import COACH_ROLES, ATHLETE_POSITIONS_BY_SPORT, SPORTS

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Permissive email regex: any non-whitespace local part, an @, and a domain with a TLD >= 2 chars.
EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$')

# Password: at least 8 chars, alphanumeric only, and must contain at least one letter and one digit.
PASSWORD_RE = re.compile(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$')


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def _is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


@auth_bp.route('/options', methods=['GET'])
def options():
    """Return server-side whitelist of role/position/sport options.

    Frontend MUST source these from this endpoint rather than hard-coding them,
    so that the source of truth (and any security-sensitive filtering) lives on
    the server.
    """
    role = (request.args.get('role') or '').strip().lower()
    sport = (request.args.get('sport') or '').strip().lower()

    payload = {
        'success': True,
        'sports': SPORTS,
        'coachRoles': COACH_ROLES,
    }

    if role == 'athlete':
        if sport in ATHLETE_POSITIONS_BY_SPORT:
            payload['positions'] = ATHLETE_POSITIONS_BY_SPORT[sport]
        elif sport:
            payload['positions'] = []
        else:
            # Return positions for all sports when role=sport not specified
            payload['positionsBySport'] = ATHLETE_POSITIONS_BY_SPORT
    elif role == 'coach':
        payload['positions'] = []
    return jsonify(payload)


@auth_bp.route('/check-email', methods=['GET'])
def check_email():
    """Check whether an email is already registered."""
    email = (request.args.get('email') or '').strip().lower()
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400
    if not _is_valid_email(email):
        return jsonify({'success': False, 'message': 'Invalid email format'}), 400
    exists = get_user_by_email(email) is not None
    return jsonify({'success': True, 'available': not exists})


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    required = ['email', 'password', 'name', 'role']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'success': False, 'message': f'Missing fields: {", ".join(missing)}'}), 400

    email = data['email'].strip().lower()
    if not _is_valid_email(email):
        return jsonify({'success': False, 'message': 'Invalid email format'}), 400

    if not PASSWORD_RE.match(data['password']):
        return jsonify({
            'success': False,
            'message': 'Password must be at least 8 characters and contain both letters and digits',
        }), 400

    if data['role'] not in ('athlete', 'coach'):
        return jsonify({'success': False, 'message': 'Role must be athlete or coach'}), 400

    # Validate sport against server-side whitelist
    sport = (data.get('sport') or '').strip().lower()
    if sport not in SPORTS:
        return jsonify({'success': False, 'message': f'Sport must be one of: {", ".join(SPORTS)}'}), 400

    # Validate coach role / athlete position against server-side whitelist
    if data['role'] == 'coach':
        coach_role = (data.get('coachRole') or '').strip()
        if coach_role not in COACH_ROLES:
            return jsonify({'success': False, 'message': 'Invalid coach role'}), 400
    else:  # athlete
        position = (data.get('position') or '').strip()
        valid_positions = ATHLETE_POSITIONS_BY_SPORT.get(sport, [])
        if position not in valid_positions:
            return jsonify({'success': False, 'message': 'Invalid position for selected sport'}), 400

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
    requested_role = (data.get('role') or '').strip().lower()

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required'}), 400

    if requested_role not in ('athlete', 'coach'):
        return jsonify({
            'success': False,
            'message': 'Role is required and must be athlete or coach',
        }), 400

    user = get_user_by_email(email)
    if not user or not _check_password(password, user['password_hash']):
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

    # Portal isolation: credentials alone are not enough — login source must match account role
    if user['role'] != requested_role:
        return jsonify({
            'success': False,
            'message': (
                f'This account is registered as a {user["role"]}. '
                f'Please sign in from the {user["role"]} portal.'
            ),
        }), 403

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


@auth_bp.route('/athletes', methods=['GET'])
@jwt_required()
def list_athletes():
    """Return a lightweight directory of athletes (id + name + school) for
    coaches who need to select a recipient for messages."""
    from models import get_db
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if user['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can list athletes'}), 403
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, school, sport, position FROM users WHERE role='athlete' ORDER BY name"
    ).fetchall()
    conn.close()
    return jsonify({
        'success': True,
        'athletes': [
            {
                'id': r['id'],
                'name': r['name'],
                'school': r['school'],
                'sport': r['sport'],
                'position': r['position'],
            }
            for r in rows
        ]
    })


@auth_bp.route('/coaches', methods=['GET'])
@jwt_required()
def list_coaches_route():
    """Return a lightweight directory of coaches for peer notifications."""
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if user['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can list coaches'}), 403
    coaches = list_coaches(exclude_id=user_id)
    return jsonify({
        'success': True,
        'coaches': [
            {
                'id': c['id'],
                'name': c['name'],
                'email': c['email'],
                'sport': c['sport'],
                'coachRole': c['coach_role'],
            }
            for c in coaches
        ]
    })


@auth_bp.route('/me/preferences', methods=['PATCH', 'PUT'])
@jwt_required()
def update_preferences():
    """Persist user preferences (notification toggles, etc.).

    Accepts a partial patch of the preferences object; only known boolean keys
    are stored. Response returns the full updated user (with merged prefs).
    """
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    prefs_patch = data.get('preferences') if isinstance(data, dict) else None
    if not isinstance(prefs_patch, dict):
        return jsonify({'success': False, 'message': 'preferences object required'}), 400
    user = update_user_preferences(user_id, prefs_patch)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    return jsonify({'success': True, 'user': user_to_public(user)})


# ═══════════════════════════════════════════════════════════════════════════════
#  Password Reset
# ═══════════════════════════════════════════════════════════════════════════════

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Send a 6-digit reset code to the user's email."""
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()

    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400
    if not _is_valid_email(email):
        return jsonify({'success': False, 'message': 'Invalid email format'}), 400

    user = get_user_by_email(email)
    if not user:
        # Return success even if user not found to prevent email enumeration
        return jsonify({'success': True, 'message': 'If an account exists, a reset code has been sent.'})

    code = generate_reset_code()
    create_reset_code(email, code)

    sent = send_reset_email(email, code, user.get('name'))
    if not sent:
        return jsonify({'success': False, 'message': 'Failed to send reset email. Please try again later.'}), 500

    return jsonify({'success': True, 'message': 'If an account exists, a reset code has been sent.'})


@auth_bp.route('/verify-reset-code', methods=['POST'])
def verify_reset_code():
    """Verify that the 6-digit code is valid and not expired."""
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()

    if not email or not code:
        return jsonify({'success': False, 'message': 'Email and code are required'}), 400

    record = get_valid_reset_code(email, code)
    if not record:
        return jsonify({'success': False, 'message': 'Invalid or expired code'}), 400

    return jsonify({'success': True, 'message': 'Code verified'})


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password using a verified 6-digit code."""
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()
    new_password = data.get('newPassword', '')

    if not email or not code or not new_password:
        return jsonify({'success': False, 'message': 'Email, code, and new password are required'}), 400

    if not PASSWORD_RE.match(new_password):
        return jsonify({
            'success': False,
            'message': 'Password must be at least 8 characters and contain both letters and digits',
        }), 400

    record = get_valid_reset_code(email, code)
    if not record:
        return jsonify({'success': False, 'message': 'Invalid or expired code'}), 400

    user = get_user_by_email(email)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    password_hash = _hash_password(new_password)
    update_user_password(user['id'], password_hash)
    mark_reset_code_used(record['id'])

    return jsonify({'success': True, 'message': 'Password has been reset successfully'})
