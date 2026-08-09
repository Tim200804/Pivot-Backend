import os
from flask import Blueprint, request, jsonify

from models import (
    get_db, get_user_by_email, get_user_by_id,
    create_coach_athlete_link, create_checkin, create_health_metric,
    create_training_metric, evaluate_alerts_for_user,
)
from seed_real_data import (
    DAYS, ALEX_HEALTH, ALEX_TRAINING, ALEX_CHECKINS,
    JORDAN_HEALTH, JORDAN_TRAINING, JORDAN_CHECKINS,
    MORGAN_HEALTH, MORGAN_TRAINING, MORGAN_CHECKINS,
    RILEY_HEALTH, RILEY_TRAINING, RILEY_CHECKINS,
    TAYLOR_HEALTH, TAYLOR_TRAINING, TAYLOR_CHECKINS,
    TRAINING_CONTEXT,
)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

_TOKEN = os.environ.get('ADMIN_SEED_TOKEN')

PROFILE_DATA = {
    'alex': (ALEX_HEALTH, ALEX_TRAINING, ALEX_CHECKINS, 'Alex Chen'),
    'jordan': (JORDAN_HEALTH, JORDAN_TRAINING, JORDAN_CHECKINS, 'Jordan Lee'),
    'morgan': (MORGAN_HEALTH, MORGAN_TRAINING, MORGAN_CHECKINS, 'Morgan Smith'),
    'riley': (RILEY_HEALTH, RILEY_TRAINING, RILEY_CHECKINS, 'Riley Kim'),
    'taylor': (TAYLOR_HEALTH, TAYLOR_TRAINING, TAYLOR_CHECKINS, 'Taylor Brooks'),
}


def _require_token():
    provided = request.args.get('token') or request.headers.get('X-Admin-Token')
    if not _TOKEN or provided != _TOKEN:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    return None


def _import_metrics(user_id, name, health, training):
    context = TRAINING_CONTEXT.get(name, [])
    for i, date in enumerate(DAYS):
        h = health[i]
        create_health_metric(user_id, {
            'date': date,
            'hrv': h['hrv'],
            'rhr': h['rhr'],
            'sleepHours': h['sleepHours'],
            'sleepDeep': h['sleepDeep'],
            'sleepREM': h['sleepREM'],
            'spo2': h['spo2'],
            'respiratoryRate': h['respiratoryRate'],
            'skinTemp': h['skinTemp'],
            'source': 'manual',
        })
        t = training[i]
        ctx = context[i] if i < len(context) else {}
        create_training_metric(user_id, {
            'date': date,
            'distance': t['distance'],
            'avgSplit': t['avgSplit'],
            'avgSPM': t['avgSPM'],
            'maxHR': t['maxHR'],
            'avgHR': t['avgHR'],
            'duration': t['duration'],
            'trainingType': ctx.get('trainingType'),
            'trainingPhase': ctx.get('trainingPhase'),
            'intensityScore': ctx.get('intensityScore'),
            'volumeScore': ctx.get('volumeScore'),
            'focusArea': ctx.get('focusArea'),
            'coachNotes': ctx.get('coachNotes'),
            'plannedLoad': ctx.get('intensityScore', 5) * ctx.get('volumeScore', 5),
            'actualLoad': ctx.get('intensityScore', 5) * ctx.get('volumeScore', 5),
        })


def _import_checkins(user_id, checkins):
    for i, date in enumerate(DAYS):
        c = checkins[i]
        create_checkin(user_id, {
            'date': date,
            'mood': c['mood'],
            'motivation': c['motivation'],
            'fatigue': c['fatigue'],
            'challenge': c['challenge'],
            'journal': c['journal'],
        })


def _link_to_head_coach(athlete_id):
    conn = get_db()
    rows = conn.execute("SELECT id FROM users WHERE role='coach' AND coach_role='Head Coach' ORDER BY id LIMIT 1").fetchall()
    conn.close()
    if rows:
        create_coach_athlete_link(rows[0]['id'], athlete_id, 'primary')
        return rows[0]['id']
    return None


def _counts_for_user(user_id):
    conn = get_db()
    try:
        def c(table, col):
            row = conn.execute(f'SELECT COUNT(*) AS c FROM {table} WHERE {col} = ?', (user_id,)).fetchone()
            return row['c'] if row else 0
        return {
            'health_metrics': c('health_metrics', 'user_id'),
            'training_metrics': c('training_metrics', 'user_id'),
            'checkins': c('checkins', 'user_id'),
            'alerts': c('alerts', 'user_id'),
            'coach_athlete_links': c('coach_athlete_links', 'athlete_id'),
        }
    finally:
        conn.close()


@admin_bp.route('/check-user', methods=['GET'])
def check_user():
    err = _require_token()
    if err:
        return err
    email = request.args.get('email', '').strip().lower()
    if not email:
        return jsonify({'success': False, 'message': 'email required'}), 400
    user = get_user_by_email(email)
    if not user:
        return jsonify({'success': False, 'message': 'user not found'}), 404
    return jsonify({
        'success': True,
        'user': {k: user[k] for k in user if k != 'password_hash'},
        'counts': _counts_for_user(user['id']),
    })


@admin_bp.route('/seed-user', methods=['POST'])
def seed_user():
    err = _require_token()
    if err:
        return err
    email = request.args.get('email', '').strip().lower()
    if not email:
        return jsonify({'success': False, 'message': 'email required'}), 400
    profile = request.args.get('profile', 'alex').lower()
    if profile not in PROFILE_DATA:
        return jsonify({'success': False, 'message': f'profile must be one of {list(PROFILE_DATA.keys())}'}), 400

    user = get_user_by_email(email)
    if not user:
        return jsonify({'success': False, 'message': 'user not found'}), 404
    if user.get('role') != 'athlete':
        return jsonify({'success': False, 'message': 'only athlete accounts can be seeded'}), 400

    health, training, checkins, source_name = PROFILE_DATA[profile]

    # Clear existing seed data for this user (only if it matches DAYS range to avoid deleting real user entries)
    conn = get_db()
    for table, col in [('health_metrics', 'user_id'), ('training_metrics', 'user_id'), ('checkins', 'user_id')]:
        conn.execute(f"DELETE FROM {table} WHERE {col} = ? AND date IN ({','.join('?' * len(DAYS))})", (user['id'], *DAYS))
    conn.commit()
    conn.close()

    _import_metrics(user['id'], source_name, health, training)
    _import_checkins(user['id'], checkins)
    coach_id = _link_to_head_coach(user['id'])

    # Run alert evaluation after data import
    evaluate_alerts_for_user(user['id'])

    return jsonify({
        'success': True,
        'message': f'Seeded {email} with {len(DAYS)} days of {profile} profile data',
        'linked_coach_id': coach_id,
        'counts': _counts_for_user(user['id']),
    })
