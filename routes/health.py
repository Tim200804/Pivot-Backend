from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import (
    get_user_by_id, list_health_metrics, list_training_metrics,
    list_checkins, list_alerts_for_user,
    create_health_metric, create_training_metric,
    health_metric_to_public, training_metric_to_public,
    checkin_to_public, alert_to_public,
    get_latest_health_summary, get_team_summary,
    get_training_impact, get_training_health_correlation,
)

health_bp = Blueprint('health', __name__, url_prefix='/api/health')


def _can_access_target(user, target_id):
    """Athletes can only view themselves; coaches can view linked athletes."""
    from models import list_athletes_for_coach
    if user['role'] == 'athlete':
        return user['id'] == target_id
    if user['role'] == 'coach':
        linked_ids = {a['id'] for a in list_athletes_for_coach(user['id'])}
        return target_id == user['id'] or target_id in linked_ids
    return False


@health_bp.route('/metrics/<int:user_id>', methods=['GET'])
@jwt_required()
def get_health_metrics(user_id):
    """Return physiological metrics for a user (athlete self or linked coach)."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if not _can_access_target(me, user_id):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    limit = min(int(request.args.get('limit', 180)), 365)
    rows = list_health_metrics(user_id, limit=limit)
    return jsonify({
        'success': True,
        'metrics': [health_metric_to_public(r) for r in rows],
    })


@health_bp.route('/metrics/<int:user_id>', methods=['POST'])
@jwt_required()
def post_health_metric(user_id):
    """Create or overwrite a daily health metric entry."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if me['role'] != 'coach' or not _can_access_target(me, user_id):
        return jsonify({'success': False, 'message': 'Only linked coaches can record metrics'}), 403

    data = request.get_json() or {}
    metric = create_health_metric(user_id, data)
    return jsonify({
        'success': True,
        'metric': health_metric_to_public(metric),
    }), 201


@health_bp.route('/training/<int:user_id>', methods=['GET'])
@jwt_required()
def get_training_metrics(user_id):
    """Return training/session metrics for a user."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if not _can_access_target(me, user_id):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    limit = min(int(request.args.get('limit', 180)), 365)
    rows = list_training_metrics(user_id, limit=limit)
    return jsonify({
        'success': True,
        'metrics': [training_metric_to_public(r) for r in rows],
    })


@health_bp.route('/training/<int:user_id>', methods=['POST'])
@jwt_required()
def post_training_metric(user_id):
    """Create or overwrite a daily training metric entry."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if me['role'] != 'coach' or not _can_access_target(me, user_id):
        return jsonify({'success': False, 'message': 'Only linked coaches can record training'}), 403

    data = request.get_json() or {}
    metric = create_training_metric(user_id, data)
    return jsonify({
        'success': True,
        'metric': training_metric_to_public(metric),
    }), 201


@health_bp.route('/summary/<int:user_id>', methods=['GET'])
@jwt_required()
def get_summary(user_id):
    """Return latest derived status summary for a user."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if not _can_access_target(me, user_id):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    return jsonify({
        'success': True,
        'summary': get_latest_health_summary(user_id),
    })


@health_bp.route('/team-summary', methods=['GET'])
@jwt_required()
def get_team_summary_route():
    """Return aggregated team health summary for the logged-in coach."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if me['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can view team summary'}), 403

    return jsonify({
        'success': True,
        'summary': get_team_summary(me['id']),
    })


@health_bp.route('/training-impact/<int:user_id>', methods=['GET'])
@jwt_required()
def get_training_impact_route(user_id):
    """Return health metric changes 1-3 days after a specific training session."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if not _can_access_target(me, user_id):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    date = request.args.get('date')
    if not date:
        return jsonify({'success': False, 'message': 'date query param required'}), 400

    result = get_training_impact(user_id, date)
    if 'error' in result:
        return jsonify({'success': False, 'message': result['error']}), 404
    return jsonify({'success': True, 'impact': result})


@health_bp.route('/correlation/<int:user_id>', methods=['GET'])
@jwt_required()
def get_correlation_route(user_id):
    """Return correlation between training load and next-day health metrics."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if not _can_access_target(me, user_id):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    days = min(int(request.args.get('days', 28)), 365)
    result = get_training_health_correlation(user_id, days=days)
    return jsonify({'success': True, 'correlation': result})


@health_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_athlete_dashboard():
    """Return full dashboard payload for the currently logged-in athlete."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if me['role'] != 'athlete':
        return jsonify({'success': False, 'message': 'Only athletes can view this dashboard'}), 403

    user_id = me['id']
    health_rows = list_health_metrics(user_id, limit=180)
    training_rows = list_training_metrics(user_id, limit=180)
    checkin_rows = list_checkins(user_id, limit=90)
    alert_rows = list_alerts_for_user(user_id, status=None)

    # Build a frontend-compatible athlete profile
    profile = {
        'id': me['id'],
        'name': me['name'],
        'email': me['email'],
        'sport': me.get('sport') or 'Rowing',
        'school': me.get('school') or '',
        'team': me.get('team_name') or 'Varsity Heavyweight 8+',
        'teamName': me.get('team_name') or 'Varsity Heavyweight 8+',
        'position': me.get('position') or 'Rower',
        'age': 19,
        'yearsRowing': 3,
        'height': me.get('height') or 180,
        'weight': me.get('weight') or 75,
    }

    return jsonify({
        'success': True,
        'athlete': profile,
        'summary': get_latest_health_summary(user_id),
        'health': [health_metric_to_public(r) for r in health_rows],
        'training': [training_metric_to_public(r) for r in training_rows],
        'checkins': [checkin_to_public(r) for r in checkin_rows],
        'alerts': [alert_to_public(r, me) for r in alert_rows],
    })
