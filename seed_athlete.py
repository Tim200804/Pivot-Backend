"""
Idempotent seed helper for a single athlete.

Used by the temporary admin endpoint to backfill data for a specific account
(e.g. Alex Chen) without wiping other athletes' data.
"""
from datetime import datetime

from models import (
    get_user_by_email,
    create_user,
    create_coach_athlete_link,
    create_health_metric,
    create_training_metric,
    create_checkin,
    evaluate_alerts_for_user,
    list_alert_rules,
    create_alert_rule,
)
from seed_real_data import (
    ALEX_HEALTH,
    ALEX_TRAINING,
    ALEX_CHECKINS,
    TRAINING_CONTEXT,
    ALERT_RULES,
    DAYS,
    _hash,
    _link_to_head_coach,
)


SEED_PASSWORD = '12345678ABC'


def ensure_alert_rules():
    """Create default alert rules if they don't already exist."""
    existing = {r['name'] for r in list_alert_rules(sport=None, active_only=False)}
    for rule in ALERT_RULES:
        if rule['name'] not in existing:
            create_alert_rule(rule)


def seed_alex_chen():
    """Create Alex Chen (if missing) and import health/training/checkin data."""
    email = 'alex.chen@pivot.dev'
    spec = {
        'email': email,
        'name': 'Alex Chen',
        'position': 'Stroke Seat',
        'school': 'University of Pennsylvania',
        'team': 'Varsity Heavyweight 8+',
        'height': 191,
        'weight': 86,
    }

    user = get_user_by_email(email)
    if not user:
        user = create_user({
            'email': spec['email'],
            'name': spec['name'],
            'role': 'athlete',
            'sport': 'rowing',
            'school': spec['school'],
            'teamName': spec['team'],
            'position': spec['position'],
            'height': spec['height'],
            'weight': spec['weight'],
        }, _hash(SEED_PASSWORD))

    ensure_alert_rules()
    _link_to_head_coach(user['id'])

    context = TRAINING_CONTEXT.get('Alex Chen', [])
    for i, date in enumerate(DAYS):
        h = ALEX_HEALTH[i]
        create_health_metric(user['id'], {
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

        t = ALEX_TRAINING[i]
        ctx = context[i] if i < len(context) else {}
        create_training_metric(user['id'], {
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

        c = ALEX_CHECKINS[i]
        create_checkin(user['id'], {
            'date': date,
            'mood': c['mood'],
            'motivation': c['motivation'],
            'fatigue': c['fatigue'],
            'challenge': c['challenge'],
            'journal': c['journal'],
        })

    created = evaluate_alerts_for_user(user['id'])

    return {
        'userId': user['id'],
        'email': user['email'],
        'name': user['name'],
        'daysImported': len(DAYS),
        'alertsCreated': len(created),
    }
