#!/usr/bin/env python3
"""Seed a coach + 5 athletes demo team into Railway MySQL for substitution testing.

Run from the pivot-backend directory:
    python seed_substitution_demo.py
"""
import os
import sys
import bcrypt
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force connection via Railway MySQL public proxy.
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
    create_substitution_request,
    respond_to_substitution_request,
    coach_approve_substitution_request,
)

PASSWORD = 'PivotDemo2026!'

COACH = {
    'email': 'demo.sub.coach@pivot.dev',
    'name': 'Demo Substitution Coach',
}

ATHLETES = [
    {'email': 'demo.sub.athlete1@pivot.dev', 'name': 'Avery Miller', 'position': 'Stroke Seat'},
    {'email': 'demo.sub.athlete2@pivot.dev', 'name': 'Blake Nguyen', 'position': 'Stroke Seat'},
    {'email': 'demo.sub.athlete3@pivot.dev', 'name': 'Casey Patel', 'position': 'Bow Seat'},
    {'email': 'demo.sub.athlete4@pivot.dev', 'name': 'Drew Thompson', 'position': 'Bow Seat'},
    {'email': 'demo.sub.athlete5@pivot.dev', 'name': 'Emma Rodriguez', 'position': '3 Seat'},
]


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _get_or_create_user(email: str, role: str, name: str, **kwargs) -> dict:
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
        'teamName': 'Demo Substitution Rowing',
        **kwargs,
    }, _hash(PASSWORD))
    print(f'[created] {role} id={user["id"]} email={user["email"]}')
    return user


def _clear_existing_demo_data():
    """Remove previously seeded demo users and their data to keep credentials stable."""
    conn = get_db()
    emails = [COACH['email']] + [a['email'] for a in ATHLETES]
    placeholders = ','.join(['?'] * len(emails))
    rows = conn.execute(f'SELECT id FROM users WHERE email IN ({placeholders})', emails).fetchall()
    user_ids = [r['id'] for r in rows]
    if user_ids:
        id_placeholders = ','.join(['?'] * len(user_ids))
        # User-owned tables
        for table in ('alerts', 'training_metrics', 'health_metrics', 'checkins'):
            conn.execute(f'DELETE FROM {table} WHERE user_id IN ({id_placeholders})', user_ids)
        # Messages (sender/recipient)
        conn.execute(f'DELETE FROM messages WHERE sender_id IN ({id_placeholders}) OR recipient_id IN ({id_placeholders})', user_ids + user_ids)
        # Coach-athlete links
        conn.execute(f'DELETE FROM coach_athlete_links WHERE coach_id IN ({id_placeholders}) OR athlete_id IN ({id_placeholders})', user_ids + user_ids)
        # Substitution requests
        conn.execute(f'DELETE FROM substitution_requests WHERE requester_id IN ({id_placeholders}) OR substitute_id IN ({id_placeholders}) OR coach_id IN ({id_placeholders})', user_ids * 3)
        # Users
        conn.execute(f'DELETE FROM users WHERE id IN ({id_placeholders})', user_ids)
        conn.commit()
        print(f'[cleanup] Removed {len(user_ids)} existing demo users and related data')
    conn.close()


def main():
    db_target = os.environ.get('DATABASE_URL', os.environ.get('MYSQL_PUBLIC_URL', 'sqlite:///pivot.db'))
    print(f'Database target: {db_target.split("@")[-1] if "@" in db_target else db_target}')
    init_db()

    # Start fresh so credentials always match
    _clear_existing_demo_data()

    coach = _get_or_create_user(
        COACH['email'], 'coach', COACH['name'],
        coachRole='Head Coach',
    )
    coach_id = coach['id']

    print('Seeding athletes...')
    athlete_users = []
    for spec in ATHLETES:
        athlete = _get_or_create_user(
            spec['email'], 'athlete', spec['name'],
            position=spec['position'],
            height=178,
            weight=75,
        )
        athlete_users.append((athlete, spec))
        create_coach_athlete_link(coach_id, athlete['id'], 'primary')
        print(f'  Linked athlete {athlete["id"]} to coach {coach_id}')

    print('Creating substitution requests...')
    today = datetime.utcnow().date()
    tomorrow = (today + timedelta(days=1)).isoformat()
    day_after = (today + timedelta(days=2)).isoformat()

    a1 = athlete_users[0][0]  # Stroke Seat
    a2 = athlete_users[1][0]  # Stroke Seat
    a3 = athlete_users[2][0]  # Bow Seat
    a4 = athlete_users[3][0]  # Bow Seat

    # 1. Pending: athlete1 asks athlete2 to cover
    req1 = create_substitution_request({
        'requester_id': a1['id'],
        'substitute_id': a2['id'],
        'coach_id': coach_id,
        'position': a1['position'],
        'training_date': tomorrow,
        'reason': 'Feeling feverish, need to rest tomorrow.',
    })
    print(f'  Created pending request id={req1["id"]}: {a1["name"]} -> {a2["name"]}')

    # 2. Teammate accepted: athlete3 asks athlete4, athlete4 accepts
    req2 = create_substitution_request({
        'requester_id': a3['id'],
        'substitute_id': a4['id'],
        'coach_id': coach_id,
        'position': a3['position'],
        'training_date': day_after,
        'reason': 'Have a midterm exam and cannot make practice.',
    })
    respond_to_substitution_request(req2['id'], a4['id'], True, 'I can cover, but will arrive 10 minutes late.')
    print(f'  Created accepted request id={req2["id"]}: {a3["name"]} -> {a4["name"]} (ready for coach approval)')

    # 3. Teammate rejected: athlete2 asks athlete1, athlete1 declines
    req3 = create_substitution_request({
        'requester_id': a2['id'],
        'substitute_id': a1['id'],
        'coach_id': coach_id,
        'position': a2['position'],
        'training_date': tomorrow,
        'reason': 'Family emergency, need someone to take my seat.',
    })
    respond_to_substitution_request(req3['id'], a1['id'], False, 'Sorry, I already have a conflicting appointment.')
    print(f'  Created rejected request id={req3["id"]}: {a2["name"]} -> {a1["name"]}')

    # 4. Coach approved: athlete4 asks athlete3, athlete3 accepts, coach approves
    req4 = create_substitution_request({
        'requester_id': a4['id'],
        'substitute_id': a3['id'],
        'coach_id': coach_id,
        'position': a4['position'],
        'training_date': tomorrow,
        'reason': 'Need to attend a mandatory academic advising session.',
    })
    respond_to_substitution_request(req4['id'], a3['id'], True, 'I got you covered.')
    coach_approve_substitution_request(req4['id'], coach_id, True, 'Approved — thank you Casey for covering.')
    print(f'  Created approved request id={req4["id"]}: {a4["name"]} -> {a3["name"]}')

    print('\n' + '=' * 60)
    print('Substitution demo team ready on Railway MySQL')
    print('=' * 60)
    print(f'Coach login:')
    print(f'  Email:    {COACH["email"]}')
    print(f'  Password: {PASSWORD}')
    print()
    print('Athlete logins (all share same password):')
    for spec in ATHLETES:
        print(f'  {spec["name"]:18s} {spec["email"]}  ({spec["position"]})')
    print(f'  Password: {PASSWORD}')
    print('=' * 60)


if __name__ == '__main__':
    main()
