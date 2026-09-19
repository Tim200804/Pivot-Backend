"""
Admin Dashboard API
===================
Independent admin routes for managing users and importing data.
Uses a separate admin JWT namespace to avoid conflicts with athlete/coach tokens.

All endpoints are prefixed with /api/admin/.
"""
import os
import json
import io
import csv
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt

from models import (
    get_db, get_user_by_id,
    create_health_metric, get_health_metric_by_id,
    health_metric_to_public,
)

admin_bp = Blueprint('admin', __name__)

# ═══════════════════════════════════════════════════════════════════════════════
#  Admin auth constants
# ═══════════════════════════════════════════════════════════════════════════════

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'pivotadmin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'PivotAdmin2026!')

# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _admin_required(fn):
    """Decorator that ensures the caller is authenticated as admin.
    
    We reuse flask_jwt_extended but verify the token contains the custom claim
    role == 'admin' to keep admin sessions separate from athlete/coach.
    The identity is a plain username string, which flask_jwt_extended requires.
    """
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        identity = get_jwt_identity()
        if not identity or claims.get('role') != 'admin':
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


def _row_to_dict(row):
    """Convert a DB row (sqlite3.Row or pymysql DictCursor) to plain dict."""
    if hasattr(row, 'keys'):
        return {k: row[k] for k in row.keys()}
    return dict(row)


def _parse_sort(sort_param):
    """Parse sort string like '-created_at' or 'name' into (column, desc)."""
    if not sort_param:
        return ('id', True)
    desc = sort_param.startswith('-')
    col = sort_param[1:] if desc else sort_param
    return (col, desc)


# ═══════════════════════════════════════════════════════════════════════════════
#  Auth
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/api/admin/login', methods=['POST'])
def admin_login():
    body = request.get_json(silent=True) or {}
    username = body.get('username', '').strip()
    password = body.get('password', '')

    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

    token = create_access_token(
        identity=username,
        additional_claims={'role': 'admin'},
        expires_delta=None,  # no expiry for admin (or set long expiry)
    )
    return jsonify({
        'success': True,
        'token': token,
        'admin': {'username': username},
    })


@admin_bp.route('/api/admin/me', methods=['GET'])
@_admin_required
def admin_me():
    identity = get_jwt_identity()
    claims = get_jwt()
    return jsonify({
        'success': True,
        'admin': {
            'username': identity,
            'role': claims.get('role'),
        }
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  Dashboard stats
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/api/admin/stats', methods=['GET'])
@_admin_required
def admin_stats():
    conn = get_db()
    try:
        tables = [
            'users', 'health_metrics', 'training_metrics', 'checkins',
            'alerts', 'messages', 'interventions', 'substitution_requests',
            'coach_athlete_links'
        ]
        stats = {}
        for t in tables:
            try:
                row = conn.execute(f'SELECT COUNT(*) AS c FROM {t}').fetchone()
                stats[t] = row['c'] if row else 0
            except Exception:
                stats[t] = 0

        # Role breakdown
        role_rows = conn.execute("SELECT role, COUNT(*) AS c FROM users GROUP BY role").fetchall()
        stats['role_breakdown'] = {r['role']: r['c'] for r in role_rows}

        # Recent signups (last 7 days)
        recent = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
            if conn._is_mysql else
            "SELECT COUNT(*) AS c FROM users WHERE created_at >= datetime('now', '-7 days')"
        ).fetchone()
        stats['recent_signups'] = recent['c'] if recent else 0

        return jsonify({'success': True, 'stats': stats})
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  Users CRUD
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/api/admin/users', methods=['GET'])
@_admin_required
def list_users():
    conn = get_db()
    try:
        # Query params
        role = request.args.get('role', '')
        search = request.args.get('search', '').strip()
        sort_col, sort_desc = _parse_sort(request.args.get('sort', '-created_at'))
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 20))))

        where_clauses = []
        params = []

        if role:
            where_clauses.append('role = ?')
            params.append(role)
        if search:
            where_clauses.append('(name LIKE ? OR email LIKE ? OR school LIKE ?)')
            like = f'%{search}%'
            params.extend([like, like, like])

        where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

        # Count total
        count_sql = f'SELECT COUNT(*) AS c FROM users {where_sql}'
        total_row = conn.execute(count_sql, tuple(params)).fetchone()
        total = total_row['c'] if total_row else 0

        # Fetch page
        order = 'DESC' if sort_desc else 'ASC'
        offset = (page - 1) * per_page
        query = f"""
            SELECT id, email, name, role, sport, school, team_name,
                   position, coach_role, height, weight,
                   created_at, updated_at
            FROM users
            {where_sql}
            ORDER BY {sort_col} {order}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query, tuple(params + [per_page, offset])).fetchall()
        users = [_row_to_dict(r) for r in rows]

        return jsonify({
            'success': True,
            'users': users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page,
            }
        })
    finally:
        conn.close()


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['GET'])
@_admin_required
def get_user(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT id, email, name, role, sport, school, team_name,
                      position, coach_role, height, weight,
                      preferences, created_at, updated_at
               FROM users WHERE id = ?""",
            (user_id,)
        ).fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        user = _row_to_dict(row)
        try:
            user['preferences'] = json.loads(user.get('preferences') or '{}')
        except Exception:
            user['preferences'] = {}
        return jsonify({'success': True, 'user': user})
    finally:
        conn.close()


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@_admin_required
def update_user(user_id):
    body = request.get_json(silent=True) or {}
    allowed_fields = ['name', 'email', 'role', 'sport', 'school', 'team_name',
                      'position', 'coach_role', 'height', 'weight']

    updates = {k: body[k] for k in allowed_fields if k in body}
    if not updates:
        return jsonify({'success': False, 'message': 'No valid fields to update'}), 400

    conn = get_db()
    try:
        # Check user exists
        row = conn.execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        # Check email uniqueness if changing
        if 'email' in updates:
            dup = conn.execute('SELECT id FROM users WHERE email = ? AND id != ?',
                               (updates['email'], user_id)).fetchone()
            if dup:
                return jsonify({'success': False, 'message': 'Email already in use'}), 409

        updates['updated_at'] = datetime.now().isoformat()
        set_clause = ', '.join(f'{k} = ?' for k in updates)
        conn.execute(
            f'UPDATE users SET {set_clause} WHERE id = ?',
            tuple(updates.values()) + (user_id,)
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'User updated'})
    finally:
        conn.close()


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@_admin_required
def delete_user(user_id):
    conn = get_db()
    try:
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'User deleted'})
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  Bulk import (CSV / Excel)
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/api/admin/users/import', methods=['POST'])
@_admin_required
def import_users():
    """Import users from uploaded CSV or Excel file.

    Expected columns (case-insensitive):
      email, name, role, password, sport, school, team_name,
      position, coach_role, height, weight

    Returns summary of created / skipped / failed rows.
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Empty filename'}), 400

    filename = file.filename.lower()
    try:
        if filename.endswith('.csv'):
            rows = _parse_csv(file)
        elif filename.endswith(('.xlsx', '.xls')):
            rows = _parse_excel(file)
        else:
            return jsonify({'success': False, 'message': 'Only .csv, .xlsx, .xls supported'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Parse error: {str(e)}'}), 400

    if not rows:
        return jsonify({'success': False, 'message': 'No data rows found'}), 400

    conn = get_db()
    try:
        created, skipped, errors = 0, 0, []
        for idx, row in enumerate(rows, start=2):  # start=2 assuming row 1 is header
            email = str(row.get('email', '')).strip()
            name = str(row.get('name', '')).strip()
            role = str(row.get('role', '')).strip().lower()
            password = str(row.get('password', '')).strip()

            if not email or not name or role not in ('athlete', 'coach'):
                errors.append({'row': idx, 'reason': 'Missing required fields (email, name, role)'})
                continue

            # Check duplicate email
            dup = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
            if dup:
                skipped += 1
                continue

            # Hash password
            try:
                import bcrypt
                pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() if password else ''
            except Exception:
                pw_hash = ''

            now = datetime.now().isoformat()
            conn.execute(
                """INSERT INTO users
                   (email, password_hash, name, role, sport, school, team_name,
                    position, coach_role, height, weight, preferences, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    email, pw_hash, name, role,
                    str(row.get('sport', '')).strip() or None,
                    str(row.get('school', '')).strip() or None,
                    str(row.get('team_name', '')).strip() or None,
                    str(row.get('position', '')).strip() or None,
                    str(row.get('coach_role', '')).strip() or None,
                    _int_or_none(row.get('height')),
                    _int_or_none(row.get('weight')),
                    '{}',
                    now, now,
                )
            )
            created += 1

        conn.commit()
        return jsonify({
            'success': True,
            'summary': {'created': created, 'skipped': skipped, 'errors': errors},
        })
    finally:
        conn.close()


def _parse_csv(file):
    stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
    reader = csv.DictReader(stream)
    return [_normalize_keys(row) for row in reader]


def _parse_excel(file):
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError('pandas not installed; cannot parse Excel files')

    df = pd.read_excel(file.stream)
    df = df.where(pd.notnull(df), None)
    return [_normalize_keys(row) for row in df.to_dict('records')]


def _normalize_keys(row):
    """Lower-case and strip keys so 'Email' matches 'email'."""
    return {str(k).lower().strip(): v for k, v in row.items()}


def _int_or_none(val):
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  Preview import (validate without writing)
# ═══════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/api/admin/users/import-preview', methods=['POST'])
@_admin_required
def preview_import():
    """Validate an uploaded file and return a preview of what would be imported."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400

    file = request.files['file']
    filename = file.filename.lower()
    try:
        if filename.endswith('.csv'):
            rows = _parse_csv(file)
        elif filename.endswith(('.xlsx', '.xls')):
            rows = _parse_excel(file)
        else:
            return jsonify({'success': False, 'message': 'Only .csv, .xlsx, .xls supported'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Parse error: {str(e)}'}), 400

    conn = get_db()
    try:
        preview = []
        for idx, row in enumerate(rows, start=2):
            email = str(row.get('email', '')).strip()
            name = str(row.get('name', '')).strip()
            role = str(row.get('role', '')).strip().lower()

            issues = []
            if not email:
                issues.append('Missing email')
            if not name:
                issues.append('Missing name')
            if role not in ('athlete', 'coach'):
                issues.append(f"Invalid role: '{role}'")

            dup = False
            if email:
                dup = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone() is not None

            preview.append({
                'row': idx,
                'email': email,
                'name': name,
                'role': role,
                'valid': len(issues) == 0 and not dup,
                'issues': issues,
                'duplicate': dup,
            })

        return jsonify({'success': True, 'preview': preview, 'total': len(preview)})
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  Health metrics management
# ═══════════════════════════════════════════════════════════════════════════════

# Columns that can be edited through the admin dashboard.
_HEALTH_FIELDS = [
    'date', 'hrv', 'rhr', 'sleep_hours', 'sleep_deep_pct', 'sleep_rem_pct',
    'spo2', 'respiratory_rate', 'skin_temp',
]


def _float_or_none(val):
    if val is None or val == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


@admin_bp.route('/api/admin/health-metrics', methods=['GET'])
@_admin_required
def list_health_metrics_admin():
    """List health metrics with optional user filter and pagination."""
    conn = get_db()
    try:
        user_id = request.args.get('user_id', '').strip()
        search = request.args.get('search', '').strip()
        sort_col, sort_desc = _parse_sort(request.args.get('sort', '-date'))
        if sort_col not in _HEALTH_FIELDS and sort_col != 'id':
            sort_col = 'date'
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 20))))

        where_clauses = []
        params = []

        if user_id:
            where_clauses.append('hm.user_id = ?')
            params.append(int(user_id))
        if search:
            where_clauses.append('(u.name LIKE ? OR u.email LIKE ? OR hm.date LIKE ?)')
            like = f'%{search}%'
            params.extend([like, like, like])

        where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

        # Count total
        count_sql = f"""
            SELECT COUNT(*) AS c
            FROM health_metrics hm
            JOIN users u ON u.id = hm.user_id
            {where_sql}
        """
        total_row = conn.execute(count_sql, tuple(params)).fetchone()
        total = total_row['c'] if total_row else 0

        # Fetch page
        order = 'DESC' if sort_desc else 'ASC'
        offset = (page - 1) * per_page
        query = f"""
            SELECT hm.id, hm.user_id, hm.date, hm.hrv, hm.rhr, hm.sleep_hours,
                   hm.sleep_deep_pct, hm.sleep_rem_pct, hm.spo2,
                   hm.respiratory_rate, hm.skin_temp, hm.source, hm.created_at,
                   u.name AS user_name, u.email AS user_email
            FROM health_metrics hm
            JOIN users u ON u.id = hm.user_id
            {where_sql}
            ORDER BY {sort_col} {order}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query, tuple(params + [per_page, offset])).fetchall()
        metrics = [_row_to_dict(r) for r in rows]

        return jsonify({
            'success': True,
            'metrics': metrics,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page,
            }
        })
    finally:
        conn.close()


@admin_bp.route('/api/admin/health-metrics/<int:metric_id>', methods=['GET'])
@_admin_required
def get_health_metric_admin(metric_id):
    """Get a single health metric by ID."""
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT hm.id, hm.user_id, hm.date, hm.hrv, hm.rhr, hm.sleep_hours,
                      hm.sleep_deep_pct, hm.sleep_rem_pct, hm.spo2,
                      hm.respiratory_rate, hm.skin_temp, hm.source, hm.created_at,
                      u.name AS user_name, u.email AS user_email
               FROM health_metrics hm
               JOIN users u ON u.id = hm.user_id
               WHERE hm.id = ?""",
            (metric_id,)
        ).fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Metric not found'}), 404
        return jsonify({'success': True, 'metric': _row_to_dict(row)})
    finally:
        conn.close()


@admin_bp.route('/api/admin/health-metrics', methods=['POST'])
@_admin_required
def create_health_metric_admin():
    """Create a new health metric entry for an athlete."""
    body = request.get_json(silent=True) or {}
    user_id = body.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'user_id is required'}), 400

    user = get_user_by_id(int(user_id))
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if user['role'] != 'athlete':
        return jsonify({'success': False, 'message': 'Health metrics can only be assigned to athletes'}), 400

    data = {
        'date': body.get('date'),
        'hrv': _float_or_none(body.get('hrv')),
        'rhr': _float_or_none(body.get('rhr')),
        'sleepHours': _float_or_none(body.get('sleep_hours')),
        'sleepDeep': _float_or_none(body.get('sleep_deep_pct')),
        'sleepREM': _float_or_none(body.get('sleep_rem_pct')),
        'spo2': _float_or_none(body.get('spo2')),
        'respiratoryRate': _float_or_none(body.get('respiratory_rate')),
        'skinTemp': _float_or_none(body.get('skin_temp')),
        'source': body.get('source') or 'admin',
    }

    metric = create_health_metric(int(user_id), data)
    return jsonify({'success': True, 'metric': health_metric_to_public(metric)}), 201


@admin_bp.route('/api/admin/health-metrics/<int:metric_id>', methods=['PUT'])
@_admin_required
def update_health_metric_admin(metric_id):
    """Update an existing health metric entry."""
    body = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        row = conn.execute('SELECT id FROM health_metrics WHERE id = ?', (metric_id,)).fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Metric not found'}), 404

        allowed_fields = {
            'date': body.get('date'),
            'hrv': _float_or_none(body.get('hrv')),
            'rhr': _float_or_none(body.get('rhr')),
            'sleep_hours': _float_or_none(body.get('sleep_hours')),
            'sleep_deep_pct': _float_or_none(body.get('sleep_deep_pct')),
            'sleep_rem_pct': _float_or_none(body.get('sleep_rem_pct')),
            'spo2': _float_or_none(body.get('spo2')),
            'respiratory_rate': _float_or_none(body.get('respiratory_rate')),
            'skin_temp': _float_or_none(body.get('skin_temp')),
        }

        updates = {k: v for k, v in allowed_fields.items() if v is not None or (body.get(k) is not None and body.get(k) == '')}
        # Allow explicit null by checking if key exists in body.
        for k in allowed_fields:
            if k in body:
                updates[k] = allowed_fields[k]

        if not updates:
            return jsonify({'success': False, 'message': 'No valid fields to update'}), 400

        updates['updated_at'] = datetime.utcnow().isoformat()
        set_clause = ', '.join(f'{k} = ?' for k in updates)
        conn.execute(
            f'UPDATE health_metrics SET {set_clause} WHERE id = ?',
            tuple(updates.values()) + (metric_id,)
        )
        conn.commit()

        metric = get_health_metric_by_id(metric_id)
        return jsonify({'success': True, 'metric': health_metric_to_public(metric)})
    finally:
        conn.close()


@admin_bp.route('/api/admin/health-metrics/<int:metric_id>', methods=['DELETE'])
@_admin_required
def delete_health_metric_admin(metric_id):
    """Delete a health metric entry."""
    conn = get_db()
    try:
        conn.execute('DELETE FROM health_metrics WHERE id = ?', (metric_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Metric deleted'})
    finally:
        conn.close()


@admin_bp.route('/api/admin/health-metrics/athletes', methods=['GET'])
@_admin_required
def list_athletes_for_metrics():
    """Return a lightweight list of athletes for the metrics filter dropdown."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, name, email FROM users WHERE role = 'athlete' ORDER BY name"
        ).fetchall()
        return jsonify({'success': True, 'athletes': [_row_to_dict(r) for r in rows]})
    finally:
        conn.close()
