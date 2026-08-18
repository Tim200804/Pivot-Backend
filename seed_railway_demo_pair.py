#!/usr/bin/env python3
"""Seed a connected athlete + coach demo pair directly into Railway MySQL."""

import os
import sys
import random
import bcrypt
from datetime import datetime, timedelta

# Force connection via Railway MySQL public proxy when running locally.
# The backend models.py picks up MYSQL_PUBLIC_URL automatically.
os.environ.setdefault('MYSQL_PUBLIC_URL',
    'mysql://root:DymTqauxJNktzVvCHnSEETfEJSvbmNpL@altaria.proxy.rlwy.net:39468/railway')

from models import (
    create_user, get_user_by_email,
    create_coach_athlete_link,
    create_health_metric, create_training_metric,
    create_checkin, create_alert,
)

# ── Demo credentials ──
ATHLETE_EMAIL = 'demo.athlete.0817@pivot.dev'
COACH_EMAIL   = 'demo.coach.0817@pivot.dev'
PASSWORD      = 'PivotDemo2026!'

random.seed(20260817)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def ensure_user(email: str, role: str, name: str, **kwargs):
    existing = get_user_by_email(email)
    if existing:
        print(f'[skip] {role} {email} already exists (id={existing["id"]})')
        return existing
    user = create_user({
        'email': email,
        'name': name,
        'role': role,
        'sport': 'rowing',
        'school': 'University of Pennsylvania',
        'teamName': 'Demo Rowing',
        **kwargs,
    }, hash_password(PASSWORD))
    print(f'[created] {role} id={user["id"]} email={user["email"]}')
    return user


def seed_demo_data(athlete_id: int, coach_id: int, days: int = 14):
    today = datetime.utcnow().date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    for idx, date in enumerate(dates):
        # Simulate a mild declining trend over the last few days
        fatigue_factor = max(0, idx - 9)  # 0 for first 10 days, then rises

        hrv = round(random.uniform(52, 60) - fatigue_factor * 3.2 - random.uniform(0, 2), 1)
        rhr = round(random.uniform(48, 54) + fatigue_factor * 1.5 + random.uniform(0, 2), 1)
        sleep = round(random.uniform(7.0, 8.2) - fatigue_factor * 0.35 - random.uniform(0, 0.4), 2)

        create_health_metric(athlete_id, {
            'date': date,
            'hrv': hrv,
            'rhr': rhr,
            'sleepHours': sleep,
            'sleepDeep': round(random.uniform(12, 20), 1),
            'sleepREM': round(random.uniform(18, 25), 1),
            'spo2': round(random.uniform(97, 99), 1),
            'respiratoryRate': round(random.uniform(13, 16), 1),
            'skinTemp': round(random.uniform(31.5, 33.5), 1),
            'source': 'manual',
        })

        # Training data
        intensity = random.randint(4, 8)
        volume = random.randint(4, 8)
        load = intensity * volume
        create_training_metric(athlete_id, {
            'date': date,
            'distance': round(random.uniform(8, 16), 2),
            'avgSplit': round(random.uniform(105, 125), 1),
            'avgSPM': random.randint(28, 36),
            'maxHR': random.randint(175, 195),
            'avgHR': random.randint(145, 165),
            'duration': random.randint(45, 90),
            'trainingType': random.choice(['Steady State', 'Intervals', 'Tempo', 'Recovery']),
            'trainingPhase': 'Base Building',
            'intensityScore': intensity,
            'volumeScore': volume,
            'focusArea': random.choice(['Endurance', 'Technique', 'Power']),
            'coachNotes': '',
            'plannedLoad': load,
            'actualLoad': load + random.randint(-2, 3),
        })

        # Check-in
        mood = max(1, min(5, int(round(random.uniform(2.5, 4.5) - fatigue_factor * 0.4))))
        motivation = max(1, min(5, int(round(random.uniform(3, 5) - fatigue_factor * 0.5))))
        fatigue = max(1, min(5, int(round(random.uniform(1, 3) + fatigue_factor * 0.6))))
        create_checkin(athlete_id, {
            'date': date,
            'mood': mood,
            'motivation': motivation,
            'fatigue': fatigue,
            'challenge': random.choice(['none', 'sleep', 'academics', 'recovery']) if fatigue >= 4 else 'none',
            'journal': '',
        })

    # Create one active red alert for the most recent day
    create_alert({
        'user_id': athlete_id,
        'level': 'red',
        'type': 'recovery',
        'message': 'HRV and sleep declining over the past 3 days; self-reported fatigue elevated.',
        'status': 'active',
        'triggered_at': f'{dates[-1]}T08:00:00',
    })

    print(f'[seeded] {days} days of health/training/check-in data + 1 red alert')


def main():
    print('Connecting to:', os.environ['MYSQL_PUBLIC_URL'].split('@')[-1])

    athlete = ensure_user(
        ATHLETE_EMAIL, 'athlete', 'Demo Athlete',
        position='Stroke Seat', height=188, weight=82,
    )
    coach = ensure_user(
        COACH_EMAIL, 'coach', 'Demo Coach',
        coachRole='Head Coach',
    )

    create_coach_athlete_link(coach['id'], athlete['id'], 'primary')
    print(f'[linked] coach {coach["id"]} <-> athlete {athlete["id"]}')

    seed_demo_data(athlete['id'], coach['id'])

    print('\n─────────────────────────────')
    print('Demo accounts created/updated')
    print('─────────────────────────────')
    print(f'Athlete: {ATHLETE_EMAIL}')
    print(f'Coach:   {COACH_EMAIL}')
    print(f'Password for both: {PASSWORD}')
    print('─────────────────────────────')


if __name__ == '__main__':
    main()
