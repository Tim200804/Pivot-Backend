from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import (
    get_user_by_id, create_checkin, list_checkins, get_checkin_for_date,
    checkin_to_public,
)

checkins_bp = Blueprint('checkins', __name__, url_prefix='/api/checkins')


@checkins_bp.route('', methods=['GET'])
@jwt_required()
def get_checkins():
    """Return the current user's check-in history (newest first)."""
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    limit = min(int(request.args.get('limit', 90)), 365)
    rows = list_checkins(user_id, limit=limit)
    return jsonify({
        'success': True,
        'checkins': [checkin_to_public(r) for r in rows],
    })


@checkins_bp.route('', methods=['POST'])
@jwt_required()
def post_checkin():
    """Submit or overwrite today's check-in for the current user."""
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    data = request.get_json() or {}
    try:
        mood = int(data.get('mood', 0))
        motivation = int(data.get('motivation', 0))
        fatigue = int(data.get('fatigue', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'mood, motivation, fatigue must be integers'}), 400

    if not (1 <= mood <= 5 and 1 <= motivation <= 10 and 1 <= fatigue <= 10):
        return jsonify({
            'success': False,
            'message': 'mood 1-5, motivation/fatigue 1-10',
        }), 400

    checkin = create_checkin(user_id, {
        'date': data.get('date'),
        'mood': mood,
        'motivation': motivation,
        'fatigue': fatigue,
        'challenge': data.get('challenge', 'none'),
        'journal': (data.get('journal') or '').strip(),
    })
    return jsonify({
        'success': True,
        'checkin': checkin_to_public(checkin),
    }), 201


@checkins_bp.route('/today', methods=['GET'])
@jwt_required()
def get_today_checkin():
    """Return today's check-in if it exists."""
    from datetime import datetime
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    today = datetime.utcnow().date().isoformat()
    checkin = get_checkin_for_date(user_id, today)
    return jsonify({
        'success': True,
        'checkedIn': checkin is not None,
        'checkin': checkin_to_public(checkin) if checkin else None,
    })
