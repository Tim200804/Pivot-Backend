from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import (
    get_user_by_id, list_alerts_for_user, list_alerts_for_coach,
    update_alert_status, list_alert_rules, create_alert_rule,
    alert_to_public, evaluate_alerts_for_user,
)

alerts_bp = Blueprint('alerts', __name__, url_prefix='/api/alerts')


@alerts_bp.route('/athlete', methods=['GET'])
@jwt_required()
def get_athlete_alerts():
    """Return alerts for the currently logged-in athlete."""
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    status = request.args.get('status') or None
    rows = list_alerts_for_user(user_id, status=status)
    return jsonify({
        'success': True,
        'alerts': [alert_to_public(r, user) for r in rows],
    })


@alerts_bp.route('/coach', methods=['GET'])
@jwt_required()
def get_coach_alerts():
    """Return alerts for all athletes linked to the logged-in coach."""
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if user['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can view team alerts'}), 403

    status = request.args.get('status') or None
    rows = list_alerts_for_coach(user_id, status=status)
    result = []
    for r in rows:
        athlete = get_user_by_id(r['user_id'])
        result.append(alert_to_public(r, athlete))
    return jsonify({
        'success': True,
        'alerts': result,
    })


@alerts_bp.route('/<int:alert_id>/status', methods=['PATCH'])
@jwt_required()
def patch_alert_status(alert_id):
    """Resolve or dismiss an alert."""
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    data = request.get_json() or {}
    status = data.get('status')
    if status not in ('active', 'resolved', 'dismissed'):
        return jsonify({'success': False, 'message': 'status must be active/resolved/dismissed'}), 400

    updated = update_alert_status(alert_id, status, user_id=user_id)
    if not updated:
        return jsonify({'success': False, 'message': 'Alert not found'}), 404

    athlete = get_user_by_id(updated['user_id'])
    return jsonify({
        'success': True,
        'alert': alert_to_public(updated, athlete),
    })


@alerts_bp.route('/rules', methods=['GET'])
@jwt_required()
def get_alert_rules():
    """Return active alert rules (optionally filtered by sport)."""
    sport = request.args.get('sport') or None
    rules = list_alert_rules(sport=sport, active_only=True)
    return jsonify({
        'success': True,
        'rules': rules,
    })


@alerts_bp.route('/rules', methods=['POST'])
@jwt_required()
def post_alert_rule():
    """Create a new alert rule (coach/admin only)."""
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user or user['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can create rules'}), 403

    data = request.get_json() or {}
    required = ['name', 'level']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'success': False, 'message': f'Missing: {", ".join(missing)}'}), 400

    rule = create_alert_rule({
        'name': data['name'],
        'level': data['level'],
        'sport': data.get('sport', '*'),
        'conditions': data.get('conditions', {}),
        'is_active': data.get('is_active', True),
    })
    return jsonify({
        'success': True,
        'rule': rule,
    }), 201


@alerts_bp.route('/evaluate/<int:user_id>', methods=['POST'])
@jwt_required()
def evaluate_user_alerts(user_id):
    """Re-run rule engine for a specific athlete."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if me['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can evaluate alerts'}), 403

    created = evaluate_alerts_for_user(user_id)
    return jsonify({
        'success': True,
        'created': len(created),
        'alerts': [alert_to_public(a) for a in created],
    })
