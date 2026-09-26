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
    generate_training_adjustment_suggestion,
    get_health_metric_for_date,
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
    days = min(max(int(request.args.get('days', 7)), 1), 180)
    health_rows = list_health_metrics(user_id, limit=days)
    training_rows = list_training_metrics(user_id, limit=days)
    checkin_rows = list_checkins(user_id, limit=min(days, 30), exclude_journal=True)
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


@health_bp.route('/training-suggestion/<int:user_id>', methods=['GET'])
@jwt_required()
def get_training_suggestion_route(user_id):
    """Return an AI-style training adjustment suggestion based on recent load and recovery data."""
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if not _can_access_target(me, user_id):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    days = min(int(request.args.get('days', 14)), 90)
    result = generate_training_adjustment_suggestion(user_id, days=days)
    return jsonify({'success': True, 'suggestion': result})


@health_bp.route('/import', methods=['POST'])
@jwt_required()
def import_health_metrics():
    """Bulk import daily health metrics from a spreadsheet (date/hrv/rhr/sleepHours).

    Athletes may import for themselves; coaches may import for linked athletes.
    Existing entries for the same (user_id, date) are overwritten.

    Request body:
        {
            "user_id": 8,                 // optional, defaults to current user
            "rows": [
                {"date": "2026-08-22", "hrv": 58, "rhr": 54, "sleepHours": 7.2},
                ...
            ]
        }
    """
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    data = request.get_json() or {}
    target_id = data.get('user_id') or me['id']
    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'user_id must be an integer'}), 400

    if not _can_access_target(me, target_id):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    rows = data.get('rows') or []
    if not isinstance(rows, list):
        return jsonify({'success': False, 'message': 'rows must be an array'}), 400

    imported = 0
    errors = []
    for idx, row in enumerate(rows):
        date = row.get('date')
        if not date:
            errors.append(f'Row {idx + 1}: missing date')
            continue
        try:
            metric = create_health_metric(target_id, {
                'date': date,
                'hrv': float(row.get('hrv')) if row.get('hrv') is not None else None,
                'rhr': float(row.get('rhr')) if row.get('rhr') is not None else None,
                'sleepHours': float(row.get('sleepHours')) if row.get('sleepHours') is not None else None,
                'source': 'import',
            })
            if metric:
                imported += 1
        except Exception as e:
            errors.append(f'Row {idx + 1}: {str(e)}')

    return jsonify({
        'success': imported > 0 and not errors,
        'imported': imported,
        'errors': errors,
        'message': f'Imported {imported} row(s)' + (f'; {len(errors)} error(s)' if errors else ''),
    }), 201 if imported > 0 else 400


@health_bp.route('/metrics/me', methods=['GET'])
@jwt_required()
def get_my_health_metric_for_date():
    """Return the current athlete's health metric for a specific date.

    Query params:
        date: YYYY-MM-DD

    Returns the existing row or a placeholder object so the manual entry form
    can pre-fill previously recorded values.
    """
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if me['role'] != 'athlete':
        return jsonify({'success': False, 'message': 'Only athletes can use manual entry here'}), 403

    date = request.args.get('date')
    if not date:
        return jsonify({'success': False, 'message': 'date query param is required'}), 400
    try:
        from datetime import date as _date
        _date.fromisoformat(date)
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    from models import get_health_metric_for_date
    metric = get_health_metric_for_date(me['id'], date)
    if metric:
        return jsonify({'success': True, 'metric': health_metric_to_public(metric)}), 200
    return jsonify({
        'success': True,
        'metric': {'date': date, 'hrv': None, 'rhr': None, 'sleepHours': None, 'source': None},
    }), 200


@health_bp.route('/metrics/me', methods=['POST'])
@jwt_required()
def post_my_health_metric():
    """Create or overwrite a daily health metric entry for the current athlete.

    Request body:
        {
            "date": "2026-09-26",
            "hrv": 58,            // optional
            "rhr": 54,            // optional
            "sleepHours": 7.2     // optional
        }

    Any metric not provided is left unchanged if a row already exists for the
    date. Missing fields on a new row are stored as NULL. Athletes only.
    """
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if me['role'] != 'athlete':
        return jsonify({'success': False, 'message': 'Only athletes can use manual entry here'}), 403

    data = request.get_json() or {}
    date = data.get('date')
    if not date:
        return jsonify({'success': False, 'message': 'Date is required'}), 400

    try:
        from datetime import date as _date
        parsed = _date.fromisoformat(date)
        if parsed > _date.today():
            return jsonify({'success': False, 'message': 'Date cannot be in the future'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    import math

    def _parse_value(value, name):
        if value is None or value == '':
            return None
        try:
            value = float(value)
            if not math.isfinite(value) or value <= 0:
                raise ValueError
            return value
        except (TypeError, ValueError, AttributeError):
            raise ValueError(f'{name} must be a positive number')

    try:
        payload = {'date': date, 'source': 'manual'}
        for key in ('hrv', 'rhr', 'sleepHours'):
            if key in data:
                payload[key] = _parse_value(data[key], key)
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400

    if 'hrv' not in payload and 'rhr' not in payload and 'sleepHours' not in payload:
        return jsonify({'success': False, 'message': 'At least one metric is required'}), 400

    metric = create_health_metric(me['id'], payload)
    return jsonify({
        'success': True,
        'metric': health_metric_to_public(metric),
    }), 201


@health_bp.route('/import-from-image', methods=['POST'])
@jwt_required()
def import_health_metrics_from_image():
    """Extract health metrics from an uploaded screenshot using Kimi vision.

    Request: multipart/form-data with:
        - image: image file (png, jpg, etc.)
        - user_id: optional integer, defaults to current user

    Returns:
        {
            "success": true,
            "imported": N,
            "rows": [...],
            "message": "..."
        }
    """
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    target_id = request.form.get('user_id') or me['id']
    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'user_id must be an integer'}), 400

    if not _can_access_target(me, target_id):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'image file is required'}), 400

    file = request.files['image']
    if not file or not file.filename:
        return jsonify({'success': False, 'message': 'image file is required'}), 400

    image_bytes = file.read()
    if not image_bytes:
        return jsonify({'success': False, 'message': 'image file is empty'}), 400

    mime_type = file.mimetype or 'image/png'

    # Import here to avoid circular import at module load time
    from routes.ai import parse_health_metrics_from_image

    result = parse_health_metrics_from_image(image_bytes, mime_type)
    if not result['success']:
        return jsonify({
            'success': False,
            'message': result['message'],
            'raw_text': result.get('raw_text', ''),
        }), 400

    rows = result['rows']
    if not rows:
        return jsonify({
            'success': True,
            'imported': 0,
            'rows': [],
            'message': 'No usable health data found in the image',
        }), 200

    # Preview mode: return extracted rows without saving so the user can review.
    preview = request.args.get('preview', 'false').lower() in ('1', 'true', 'yes')
    if preview:
        return jsonify({
            'success': True,
            'imported': 0,
            'rows': rows,
            'preview': True,
            'message': f'Found {len(rows)} row(s) in image; review before saving',
        }), 200

    imported = 0
    errors = []
    for idx, row in enumerate(rows):
        try:
            metric = create_health_metric(target_id, {
                'date': row['date'],
                'hrv': row.get('hrv'),
                'rhr': row.get('rhr'),
                'sleepHours': row.get('sleepHours'),
                'sleepDeep': row.get('sleepDeep'),
                'sleepREM': row.get('sleepREM'),
                'spo2': row.get('spo2'),
                'respiratoryRate': row.get('respiratoryRate'),
                'skinTemp': row.get('skinTemp'),
                'source': 'image-import',
            })
            if metric:
                imported += 1
        except Exception as e:
            errors.append(f'Row {idx + 1}: {str(e)}')

    return jsonify({
        'success': imported > 0,
        'imported': imported,
        'rows': rows,
        'errors': errors,
        'message': f'Imported {imported} row(s) from image' + (f'; {len(errors)} error(s)' if errors else ''),
    }), 201 if imported > 0 else 400


@health_bp.route('/sync', methods=['POST'])
@jwt_required()
def sync_health_records():
    """Bulk sync HealthKit records from the iOS companion app.

    Request body:
        {
            "user_id": 8,
            "records": [
                {
                    "metricType": "heart_rate",
                    "value": 58,
                    "unit": "bpm",
                    "startDate": "2026-08-12T06:30:00.000+08:00",
                    "endDate": "2026-08-12T06:31:00.000+08:00",
                    "source": "Apple Watch"
                },
                ...
            ]
        }

    Currently supported metricType values:
        - heart_rate  -> aggregated as resting heart rate (rhr) per day
        - sleep       -> aggregated as sleep_hours per day
        - steps       -> stored as source notes (not a dedicated column yet)
        - active_energy / distance -> ignored silently

    Returns:
        {"success": True, "synced": N, "message": "..."}
    """
    me = get_user_by_id(int(get_jwt_identity()))
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    data = request.get_json() or {}
    user_id = data.get('user_id')
    if not user_id or not isinstance(user_id, int):
        return jsonify({'success': False, 'message': 'user_id is required and must be an integer'}), 400

    # Athletes can only sync their own data; coaches can sync for linked athletes.
    if not _can_access_target(me, user_id):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    records = data.get('records') or []
    if not isinstance(records, list):
        return jsonify({'success': False, 'message': 'records must be an array'}), 400

    from collections import defaultdict
    from datetime import datetime as _dt

    daily: dict[str, dict] = defaultdict(lambda: {
        'hrv': None,
        'rhr_values': [],
        'sleep_seconds': 0.0,
        'source': 'HealthKit',
    })

    parsed = 0
    ignored = 0

    for rec in records:
        metric_type = (rec.get('metricType') or '').lower()
        value = rec.get('value')
        start = rec.get('startDate') or rec.get('start')

        if value is None or metric_type not in {'heart_rate', 'sleep', 'steps', 'active_energy', 'distance'}:
            ignored += 1
            continue

        # Normalize date from ISO-8601 string
        try:
            date_key = start[:10] if start and len(start) >= 10 else _dt.utcnow().isoformat()[:10]
        except Exception:
            date_key = _dt.utcnow().isoformat()[:10]

        day = daily[date_key]

        if metric_type == 'heart_rate':
            day['rhr_values'].append(float(value))
        elif metric_type == 'sleep':
            # value is already in hours from iOS; convert back to seconds for aggregation
            day['sleep_seconds'] += float(value) * 3600
        elif metric_type == 'steps':
            # Steps are not a dedicated column yet; keep in source for traceability.
            day['source'] = f"HealthKit (steps: {int(value)})"
        else:
            ignored += 1

        parsed += 1

    synced = 0
    for date_key, agg in daily.items():
        rhr = None
        if agg['rhr_values']:
            rhr = round(sum(agg['rhr_values']) / len(agg['rhr_values']), 1)

        sleep_hours = None
        if agg['sleep_seconds'] > 0:
            sleep_hours = round(agg['sleep_seconds'] / 3600, 1)

        create_health_metric(user_id, {
            'date': date_key,
            'hrv': agg['hrv'],
            'rhr': rhr,
            'sleepHours': sleep_hours,
            'sleepDeep': None,
            'sleepREM': None,
            'spo2': None,
            'respiratoryRate': None,
            'skinTemp': None,
            'source': agg['source'],
        })
        synced += 1

    return jsonify({
        'success': True,
        'synced': synced,
        'parsed': parsed,
        'ignored': ignored,
        'message': f'Synced {synced} day(s) of health data for user {user_id}',
    }), 201
