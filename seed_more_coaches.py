#!/usr/bin/env python3
"""Seed additional coaches with varied roles for testing Notify Coaches."""
import bcrypt
from models import create_user, get_user_by_email

COACHES = [
    ('strength@pivot.dev', 'Strength Coach', 'Strength & Conditioning Coach'),
    ('psych@pivot.dev', 'Sports Psych', 'Sports Psychologist'),
    ('trainer@pivot.dev', 'Athletic Trainer', 'Athletic Trainer'),
    ('analyst@pivot.dev', 'Performance Analyst', 'Performance Analyst'),
]
PASSWORD = '12345678ABC'

if __name__ == '__main__':
    for email, name, role in COACHES:
        if get_user_by_email(email):
            print(f'Coach {email} already exists')
            continue
        password_hash = bcrypt.hashpw(PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = create_user({
            'email': email,
            'name': name,
            'role': 'coach',
            'sport': 'rowing',
            'school': 'Test University',
            'teamName': 'Test Rowing',
            'coachRole': role,
        }, password_hash)
        print('Created coach:', user['id'], user['email'], user['name'], role)
