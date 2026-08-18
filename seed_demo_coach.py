#!/usr/bin/env python3
"""Seed demo coach account and linked athletes for Railway/production demos.

Links health/training/check-in data to demo.coach.0817@pivot.dev without
wiping unrelated users. Safe to run multiple times (idempotent links/metrics).

Run from the pivot-backend directory:
    python seed_demo_coach.py

This script connects directly to Railway MySQL via MYSQL_PUBLIC_URL.
"""
import os
import sys
import bcrypt
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force connection via Railway MySQL public proxy when running locally.
os.environ.setdefault(
    'MYSQL_PUBLIC_URL',
    'mysql://root:DymTqauxJNktzVvCHnSEETfEJSvbmNpL@altaria.proxy.rlwy.net:39468/railway',
)

from models import (
    init_db,
    get_db,
    get_user_by_email,
    create_user,
    create_coach_athlete_link,
    create_health_metric,
    create_training_metric,
    create_checkin,
    evaluate_alerts_for_user,
    create_alert_rule,
    list_alert_rules,
)

from seed_real_data import (
    ATHLETE_SPECS,
    ALERT_RULES,
    TRAINING_CONTEXT,
)

DEMO_COACH_EMAIL = 'demo.coach.0817@pivot.dev'
DEMO_COACH_PASSWORD = 'PivotDemo2026!'

# Subset of mock athletes re-mapped for the demo coach roster
DEMO_ATHLETE_SPECS = [
    {
        'email': 'alex.chen.demo@pivot.dev',
        'name': 'Alex Chen',
        'position': 'Stroke Seat',
        'school': 'University of Pennsylvania',
        'team': 'Demo Rowing',
        'height': 191,
        'weight': 86,
        **{k: ATHLETE_SPECS[0][k] for k in ('health', 'training', 'checkins')},
    },
    {
        'email': 'jordan.lee.demo@pivot.dev',
        'name': 'Jordan Lee',
        'position': 'Bow Seat',
        'school': 'University of Pennsylvania',
        'team': 'Demo Rowing',
        'height': 188,
        'weight': 82,
        **{k: ATHLETE_SPECS[1][k] for k in ('health', 'training', 'checkins')},
    },
    {
        'email': 'morgan.smith.demo@pivot.dev',
        'name': 'Morgan Smith',
        'position': '3 Seat',
        'school': 'University of Pennsylvania',
        'team': 'Demo Rowing',
        'height': 185,
        'weight': 80,
        **{k: ATHLETE_SPECS[2][k] for k in ('health', 'training', 'checkins')},
    },
    {
        'email': 'taylor.brooks.demo@pivot.dev',
        'name': 'Taylor Brooks',
        'position': '4 Seat',
        'school': 'University of Pennsylvania',
        'team': 'Demo Rowing',
        'height': 190,
        'weight': 84,
        **{k: ATHLETE_SPECS[5][k] for k in ('health', 'training', 'checkins')},
    },
]


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _recent_days(n: int = 7) -> list[str]:
    today = datetime.utcnow().date()
    return [(today - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]


def _ensure_alert_rules():
    existing = {r['name'] for r in list_alert_rules()}
    created = 0
    for rule in ALERT_RULES:
        if rule['name'] not in existing:
            create_alert_rule(rule)
            created += 1
    if created:
        print(f'  Created {created} alert rules')


def _get_or_create_coach():
    coach = get_user_by_email(DEMO_COACH_EMAIL)
    if coach:
        print(f'Found demo coach: {coach["id"]} {coach["email"]}')
        return coach
    coach = create_user({
        'email': DEMO_COACH_EMAIL,
        'name': 'Demo Coach',
        'role': 'coach',
        'sport': 'rowing',
        'school': 'University of Pennsylvania',
        'teamName': 'Demo Rowing',
        'coachRole': 'Head Coach',
    }, _hash(DEMO_COACH_PASSWORD))
    print(f'Created demo coach: {coach["id"]} {coach["email"]}')
    return coach


def _get_or_create_athlete(spec: dict) -> dict:
    existing = get_user_by_email(spec['email'])
    if existing:
        print(f'  Found athlete {existing["id"]} {existing["email"]}')
        return existing
    athlete = create_user({
        'email': spec['email'],
        'name': spec['name'],
        'role': 'athlete',
        'sport': 'rowing',
        'school': spec['school'],
        'teamName': spec['team'],
        'position': spec['position'],
        'height': spec['height'],
        'weight': spec['weight'],
    }, _hash(DEMO_COACH_PASSWORD))
    print(f'  Created athlete {athlete["id"]} {athlete["email"]}')
    return athlete


def _link_coach_athlete(coach_id: int, athlete_id: int):
    conn = get_db()
    row = conn.execute(
        'SELECT id FROM coach_athlete_links WHERE coach_id = ? AND athlete_id = ?',
        (coach_id, athlete_id),
    ).fetchone()
    conn.close()
    if row:
        return
    create_coach_athlete_link(coach_id, athlete_id, 'primary')
    print(f'  Linked athlete {athlete_id} to coach {coach_id}')


def _clear_athlete_metrics(user_id: int):
    conn = get_db()
    for table in ('alerts', 'training_metrics', 'health_metrics', 'checkins'):
        conn.execute(f'DELETE FROM {table} WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()


def _import_recent_metrics(user_id: int, name: str, health, training):
    days = _recent_days(len(health))
    context = TRAINING_CONTEXT.get(name, [])
    for i, date in enumerate(days):
        h = health[i]
        create_health_metric(user_id, {
            'date': date,
            'hrv': h['hrv'],
            'rhr': h['rhr'],
            'sleepHours': h['sleepHours'],
            'sleepDeep': h.get('sleepDeep'),
            'sleepREM': h.get('sleepREM'),
            'spo2': h.get('spo2'),
            'respiratoryRate': h.get('respiratoryRate'),
            'skinTemp': h.get('skinTemp'),
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


def _import_recent_checkins(user_id: int, checkins):
    days = _recent_days(len(checkins))
    for i, date in enumerate(days):
        c = checkins[i]
        create_checkin(user_id, {
            'date': date,
            'mood': c['mood'],
            'motivation': c['motivation'],
            'fatigue': c['fatigue'],
            'challenge': c['challenge'],
            'journal': c.get('journal', ''),
        })


def main():
    db_target = os.environ.get('DATABASE_URL', os.environ.get('MYSQL_PUBLIC_URL', 'sqlite:///pivot.db'))
    print(f'Database target: {db_target.split("@")[-1] if "@" in db_target else db_target}')
    init_db()
    print('Ensuring alert rules...')
    _ensure_alert_rules()

    coach = _get_or_create_coach()
    coach_id = coach['id']

    print('Seeding demo athletes...')
    for spec in DEMO_ATHLETE_SPECS:
        athlete = _get_or_create_athlete(spec)
        _link_coach_athlete(coach_id, athlete['id'])
        _clear_athlete_metrics(athlete['id'])
        _import_recent_metrics(athlete['id'], spec['name'], spec['health'], spec['training'])
        _import_recent_checkins(athlete['id'], spec['checkins'])
        alerts = evaluate_alerts_for_user(athlete['id'])
        print(f"  {spec['name']}: metrics imported, {len(alerts)} alerts")

    conn = get_db()
    row = conn.execute(
        'SELECT COUNT(*) AS cnt FROM coach_athlete_links WHERE coach_id = ?',
        (coach_id,),
    ).fetchone()
    link_count = row['cnt'] if isinstance(row, dict) else row[0]
    conn.close()
    print(f'\nDemo coach roster ready: {link_count} linked athletes')
    print(f'Coach login: {DEMO_COACH_EMAIL} / {DEMO_COACH_PASSWORD}')


if __name__ == '__main__':
    main()
