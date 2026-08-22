from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

from models import (
    get_user_by_id, list_coaches_for_athlete, list_athletes_for_coach,
    create_substitution_request, get_substitution_request,
    list_substitution_requests, find_available_substitutes,
    respond_to_substitution_request, coach_approve_substitution_request,
    notify_substitution_event, create_message,
    list_health_metrics, get_latest_health_summary,
)
from routes.ai import generate_substitution_support_text

substitutions_bp = Blueprint('substitutions', __name__, url_prefix='/api/substitutions')


def _format_date(d):
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, str):
        return d[:10]
    return None


def _get_earliest_rest_date(health):
    """Estimate the earliest recovery/rest date based on recent HRV and sleep."""
    if not health:
        return (datetime.utcnow() + timedelta(days=1)).date().isoformat()
    latest = health[-1]
    hrv = latest.get('hrv') or 0
    sleep = latest.get('sleep_hours') or latest.get('sleepHours') or 0
    # Lower HRV / poor sleep pushes earliest rest further out
    days = 2 if hrv and hrv < 45 and sleep and sleep < 6 else 1
    return (datetime.utcnow() + timedelta(days=days)).date().isoformat()


def _build_athlete_health_context(user_id):
    health = list_health_metrics(user_id, limit=7)
    summary = get_latest_health_summary(user_id)
    return health, summary


@substitutions_bp.route('', methods=['POST'])
@jwt_required()
def create_request():
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user or user['role'] != 'athlete':
        return jsonify({'success': False, 'message': 'Only athletes can create substitution requests'}), 403

    data = request.get_json() or {}
    training_date = _format_date(data.get('trainingDate'))
    reason = (data.get('reason') or '').strip()
    substitute_id = data.get('substituteId')

    if not training_date:
        return jsonify({'success': False, 'message': 'trainingDate is required'}), 400

    position = (user.get('position') or '').strip()
    if not position:
        return jsonify({'success': False, 'message': 'Athlete has no position set'}), 400

    coaches = list_coaches_for_athlete(user_id)
    if not coaches:
        return jsonify({'success': False, 'message': 'No coach assigned'}), 400
    coach_id = coaches[0]['id']

    candidates = find_available_substitutes(user_id, position)
    if not candidates:
        return jsonify({
            'success': False,
            'message': 'No substitute available for your position. Please contact your coach directly.',
            'noSubstitute': True,
        }), 409

    candidate_ids = {c['id'] for c in candidates}
    if not substitute_id or int(substitute_id) not in candidate_ids:
        return jsonify({'success': False, 'message': 'Selected substitute is not available for this position'}), 400

    req = create_substitution_request({
        'requester_id': user_id,
        'substitute_id': int(substitute_id),
        'coach_id': coach_id,
        'position': position,
        'training_date': training_date,
        'reason': reason,
    })
    notify_substitution_event(req, 'created')
    return jsonify({'success': True, 'request': req}), 201


@substitutions_bp.route('', methods=['GET'])
@jwt_required()
def list_requests():
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    requests = list_substitution_requests(user_id, user['role'])
    return jsonify({'success': True, 'requests': requests})


@substitutions_bp.route('/candidates', methods=['GET'])
@jwt_required()
def candidates():
    """Return teammates who can substitute for the current athlete's position."""
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user or user['role'] != 'athlete':
        return jsonify({'success': False, 'message': 'Only athletes can view substitutes'}), 403

    position = (user.get('position') or '').strip()
    if not position:
        return jsonify({'success': True, 'candidates': []})

    candidates = find_available_substitutes(user_id, position)
    return jsonify({'success': True, 'candidates': candidates})


@substitutions_bp.route('/coach-candidates', methods=['GET'])
@jwt_required()
def coach_candidates():
    """Return athletes who can substitute for a given athlete (coach view)."""
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user or user['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can view substitutes'}), 403

    athlete_id = request.args.get('athleteId')
    if not athlete_id:
        return jsonify({'success': False, 'message': 'athleteId is required'}), 400

    athlete = get_user_by_id(int(athlete_id))
    if not athlete or athlete['role'] != 'athlete':
        return jsonify({'success': False, 'message': 'Athlete not found'}), 404

    coach_athletes = list_athletes_for_coach(user_id)
    if athlete['id'] not in {a['id'] for a in coach_athletes}:
        return jsonify({'success': False, 'message': 'Athlete is not on your roster'}), 403

    position = (athlete.get('position') or '').strip()
    if not position:
        return jsonify({'success': True, 'candidates': []})

    candidates = find_available_substitutes(athlete['id'], position)
    return jsonify({'success': True, 'candidates': candidates})


@substitutions_bp.route('/<int:req_id>/respond', methods=['POST'])
@jwt_required()
def respond(req_id):
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user or user['role'] != 'athlete':
        return jsonify({'success': False, 'message': 'Only athletes can respond'}), 403

    data = request.get_json() or {}
    accept = bool(data.get('accept'))
    note = (data.get('note') or '').strip() or None

    req = respond_to_substitution_request(req_id, user_id, accept, note)
    if not req:
        return jsonify({'success': False, 'message': 'Request not found or cannot be responded to'}), 400

    notify_substitution_event(req, 'teammate_accepted' if accept else 'teammate_rejected')
    return jsonify({'success': True, 'request': req})


@substitutions_bp.route('/<int:req_id>/coach-approve', methods=['POST'])
@jwt_required()
def coach_approve(req_id):
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user or user['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can approve'}), 403

    data = request.get_json() or {}
    approve = bool(data.get('approve'))
    note = (data.get('note') or '').strip() or None

    req = coach_approve_substitution_request(req_id, user_id, approve, note)
    if not req:
        return jsonify({'success': False, 'message': 'Request not found or teammate has not accepted yet'}), 400

    notify_substitution_event(req, 'coach_approved' if approve else 'coach_rejected')
    return jsonify({'success': True, 'request': req})


@substitutions_bp.route('/coach-initiate', methods=['POST'])
@jwt_required()
def coach_initiate():
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user or user['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can initiate substitutions'}), 403

    data = request.get_json() or {}
    athlete_id = data.get('athleteId')
    substitute_id = data.get('substituteId')
    training_date = _format_date(data.get('trainingDate'))
    reason = (data.get('reason') or 'Coach initiated substitution').strip()

    if not athlete_id or not training_date:
        return jsonify({'success': False, 'message': 'athleteId and trainingDate are required'}), 400

    athlete = get_user_by_id(int(athlete_id))
    if not athlete or athlete['role'] != 'athlete':
        return jsonify({'success': False, 'message': 'Athlete not found'}), 404

    # Verify athlete is linked to this coach
    coach_athletes = list_athletes_for_coach(user_id)
    if athlete_id not in {a['id'] for a in coach_athletes}:
        return jsonify({'success': False, 'message': 'Athlete is not on your roster'}), 403

    position = (athlete.get('position') or '').strip()
    if not position:
        return jsonify({'success': False, 'message': 'Athlete has no position set'}), 400

    candidates = find_available_substitutes(athlete_id, position)
    if not candidates:
        return jsonify({
            'success': False,
            'message': 'No substitute available for this position',
            'noSubstitute': True,
        }), 409

    candidate_ids = {c['id'] for c in candidates}
    if not substitute_id or int(substitute_id) not in candidate_ids:
        return jsonify({'success': False, 'message': 'Selected substitute is not available for this position'}), 400

    req = create_substitution_request({
        'requester_id': athlete_id,
        'substitute_id': int(substitute_id),
        'coach_id': user_id,
        'position': position,
        'training_date': training_date,
        'reason': reason,
    })
    notify_substitution_event(req, 'created')
    return jsonify({'success': True, 'request': req}), 201


@substitutions_bp.route('/coach-message', methods=['POST'])
@jwt_required()
def coach_message():
    """When no substitute is available, send an LLM-generated supportive message to the athlete."""
    user_id = int(get_jwt_identity())
    user = get_user_by_id(user_id)
    if not user or user['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can send coach messages'}), 403

    data = request.get_json() or {}
    athlete_id = data.get('athleteId')
    if not athlete_id:
        return jsonify({'success': False, 'message': 'athleteId is required'}), 400

    athlete = get_user_by_id(int(athlete_id))
    if not athlete or athlete['role'] != 'athlete':
        return jsonify({'success': False, 'message': 'Athlete not found'}), 404

    coach_athletes = list_athletes_for_coach(user_id)
    if athlete['id'] not in {a['id'] for a in coach_athletes}:
        return jsonify({'success': False, 'message': 'Athlete is not on your roster'}), 403

    health, summary = _build_athlete_health_context(athlete['id'])
    earliest_rest = _get_earliest_rest_date(health)

    checkin = {
        'mood': summary.get('mood') or 3,
        'motivation': summary.get('motivation') or 5,
        'fatigue': summary.get('fatigue') or 5,
        'journal': summary.get('journal') or '',
    }
    athlete_context = {
        **athlete,
        'health': health,
        'status': summary.get('status') or 'warning',
        'age': athlete.get('age') or '-',
    }

    text = generate_substitution_support_text(athlete_context, checkin, earliest_rest)
    if not text:
        text = (
            f"{athlete['name']}, your recovery metrics suggest you need rest, but today's team training is important. "
            f"Get through the session safely, and plan to rest on {earliest_rest}. You've got this."
        )

    msg = create_message(
        sender_id=user_id,
        recipient_id=athlete['id'],
        body=text,
        subject='A note from your coach',
        alert_type='substitution',
    )
    return jsonify({'success': True, 'message': msg, 'earliestRestDate': earliest_rest})
