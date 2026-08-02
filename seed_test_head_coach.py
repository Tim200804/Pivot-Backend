#!/usr/bin/env python3
"""Seed a head coach account with known password for testing notifications."""
import bcrypt
from models import create_user, get_user_by_email

EMAIL = 'head@pivot.dev'
PASSWORD = '12345678ABC'

if __name__ == '__main__':
    if get_user_by_email(EMAIL):
        print(f'Coach {EMAIL} already exists')
    else:
        password_hash = bcrypt.hashpw(PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = create_user({
            'email': EMAIL,
            'name': 'Head Coach',
            'role': 'coach',
            'sport': 'rowing',
            'school': 'Test University',
            'teamName': 'Test Rowing',
            'coachRole': 'Head Coach',
        }, password_hash)
        print('Created coach:', user['id'], user['email'], user['name'])
