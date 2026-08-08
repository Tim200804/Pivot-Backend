from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import (
    get_user_by_id, get_alert_by_id, list_athletes_for_coach,
    create_intervention, get_intervention_by_id, list_interventions,
    update_intervention, delete_intervention, intervention_to_public,
)

interventions_bp = Blueprint('interventions', __name__, url_prefix='/api/interventions')


def _can_access_intervention(user, intervention):
    """Coach can access interventions for linked athletes; athletes can access their own."""
    if user['role'] == 'coach':
        linked_ids = {a['id'] for a in list_athletes_for_coach(user['id'])}
        return intervention['athlete_id'] in linked_ids or intervention['coach_id'] == user['id']
    return user['id'] == intervention['athlete_id']


def _can_manage_intervention(user, intervention):
    """Only the coach who created it or a coach linked to the athlete can modify."""
    if user['role'] != 'coach':
        return False
    if intervention['coach_id'] == user['id']:
        return True
    linked_ids = {a['id'] for a in list_athletes_for_coach(user['id'])}
    return intervention['athlete_id'] in linked_ids


@interventions_bp.route('', methods=['GET'])
@jwt_required()
def get_interventions():
    """List interventions filtered by athlete, alert, or status."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    athlete_id = request.args.get('athlete_id', type=int)
    alert_id = request.args.get('alert_id', type=int)
    status = request.args.get('status') or None

    if me['role'] == 'athlete':
        if athlete_id and athlete_id != me['id']:
            return jsonify({'success': False, 'message': 'Not authorized'}), 403
        athlete_id = me['id']
    elif me['role'] == 'coach':
        linked_ids = {a['id'] for a in list_athletes_for_coach(me['id'])}
        if athlete_id and athlete_id not in linked_ids:
            return jsonify({'success': False, 'message': 'Not authorized'}), 403
    else:
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    rows = list_interventions(athlete_id=athlete_id, alert_id=alert_id, status=status, limit=200)
    return jsonify({
        'success': True,
        'interventions': [intervention_to_public(r) for r in rows],
    })


@interventions_bp.route('/<int:intervention_id>', methods=['GET'])
@jwt_required()
def get_intervention(intervention_id):
    """Return a single intervention."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    intervention = get_intervention_by_id(intervention_id)
    if not intervention:
        return jsonify({'success': False, 'message': 'Intervention not found'}), 404
    if not _can_access_intervention(me, intervention):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    return jsonify({
        'success': True,
        'intervention': intervention_to_public(intervention),
    })


@interventions_bp.route('', methods=['POST'])
@jwt_required()
def post_intervention():
    """Create a new intervention for an alert/athlete."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me or me['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can create interventions'}), 403

    data = request.get_json() or {}
    alert_id = data.get('alert_id')
    athlete_id = data.get('athlete_id')

    if alert_id:
        alert = get_alert_by_id(alert_id)
        if not alert:
            return jsonify({'success': False, 'message': 'Alert not found'}), 404
        athlete_id = alert['user_id']
    elif not athlete_id:
        return jsonify({'success': False, 'message': 'alert_id or athlete_id required'}), 400

    linked_ids = {a['id'] for a in list_athletes_for_coach(me['id'])}
    if athlete_id not in linked_ids:
        return jsonify({'success': False, 'message': 'Athlete not linked to coach'}), 403

    required = ['intervention_type']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'success': False, 'message': f'Missing: {", ".join(missing)}'}), 400

    intervention = create_intervention({
        'alert_id': alert_id,
        'athlete_id': athlete_id,
        'coach_id': me['id'],
        'coach_role': me.get('coach_role'),
        'intervention_type': data['intervention_type'],
        'description': data.get('description', ''),
        'actions_taken': data.get('actions_taken', []),
        'status': data.get('status', 'planned'),
        'started_at': data.get('started_at'),
        'completed_at': data.get('completed_at'),
        'effectiveness_score': data.get('effectiveness_score'),
        'outcome_notes': data.get('outcome_notes', ''),
    })

    return jsonify({
        'success': True,
        'intervention': intervention_to_public(intervention),
    }), 201


@interventions_bp.route('/<int:intervention_id>', methods=['PATCH'])
@jwt_required()
def patch_intervention(intervention_id):
    """Update an intervention (status, notes, effectiveness, etc.)."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me or me['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can update interventions'}), 403

    intervention = get_intervention_by_id(intervention_id)
    if not intervention:
        return jsonify({'success': False, 'message': 'Intervention not found'}), 404
    if not _can_manage_intervention(me, intervention):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    data = request.get_json() or {}
    allowed = {
        'intervention_type', 'description', 'actions_taken', 'status',
        'completed_at', 'effectiveness_score', 'outcome_notes',
    }
    payload = {k: v for k, v in data.items() if k in allowed}

    updated = update_intervention(intervention_id, payload)
    if not updated:
        return jsonify({'success': False, 'message': 'Update failed'}), 500

    return jsonify({
        'success': True,
        'intervention': intervention_to_public(updated),
    })


@interventions_bp.route('/<int:intervention_id>', methods=['DELETE'])
@jwt_required()
def remove_intervention(intervention_id):
    """Delete an intervention."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me or me['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can delete interventions'}), 403

    intervention = get_intervention_by_id(intervention_id)
    if not intervention:
        return jsonify({'success': False, 'message': 'Intervention not found'}), 404
    if not _can_manage_intervention(me, intervention):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    delete_intervention(intervention_id)
    return jsonify({'success': True, 'message': 'Deleted'}), 200
