"""
Seed real athlete data into the Pivot database.

This script imports the demonstration dataset previously stored in
src/data/mockData.js (health metrics, training metrics, check-ins, and
derived alerts) into persistent SQLite tables.

Run from the pivot-backend directory with the virtualenv activated:
    python seed_real_data.py
"""
import os
import sys
import json
import bcrypt
from datetime import datetime, timedelta

# Ensure we import local models even when cwd is elsewhere
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models import (
    init_db, get_db, get_user_by_email, create_user, get_user_by_id,
    create_coach_athlete_link, create_checkin, create_health_metric,
    create_training_metric, create_alert_rule, evaluate_alerts_for_user,
    list_alert_rules,
)

DB_PATH = os.environ.get('DATABASE_URL', 'sqlite:///pivot.db').replace('sqlite:///', '')
PASSWORD = '12345678ABC'

DAYS = ['2026-07-10', '2026-07-11', '2026-07-12', '2026-07-13', '2026-07-14', '2026-07-15', '2026-07-16']


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _drop_seed_tables():
    conn = get_db()
    for table in ['alerts', 'training_metrics', 'health_metrics', 'checkins', 'coach_athlete_links', 'alert_rules']:
        conn.execute(f'DELETE FROM {table}')
    conn.commit()
    conn.close()
    print(f'Cleared seed tables.')


# ─── Raw demonstration datasets (mirrored from mockData.js) ───

# Instead of regenerating, hard-code the same values used by the frontend mock.
ALEX_HEALTH = [
    {'hrv': 65.8, 'rhr': 51, 'sleepHours': 8.0, 'sleepDeep': 21.4, 'sleepREM': 25.8, 'spo2': 97.4, 'respiratoryRate': 13.8, 'skinTemp': 36.5},
    {'hrv': 63.2, 'rhr': 53, 'sleepHours': 7.5, 'sleepDeep': 19.2, 'sleepREM': 24.1, 'spo2': 97.0, 'respiratoryRate': 14.2, 'skinTemp': 36.6},
    {'hrv': 66.5, 'rhr': 52, 'sleepHours': 8.1, 'sleepDeep': 22.0, 'sleepREM': 26.2, 'spo2': 97.6, 'respiratoryRate': 13.9, 'skinTemp': 36.4},
    {'hrv': 64.0, 'rhr': 54, 'sleepHours': 7.8, 'sleepDeep': 20.5, 'sleepREM': 25.0, 'spo2': 97.3, 'respiratoryRate': 14.1, 'skinTemp': 36.5},
    {'hrv': 67.2, 'rhr': 50, 'sleepHours': 8.2, 'sleepDeep': 22.5, 'sleepREM': 26.5, 'spo2': 97.7, 'respiratoryRate': 13.7, 'skinTemp': 36.4},
    {'hrv': 62.5, 'rhr': 55, 'sleepHours': 7.4, 'sleepDeep': 18.8, 'sleepREM': 23.5, 'spo2': 96.9, 'respiratoryRate': 14.4, 'skinTemp': 36.7},
    {'hrv': 64.8, 'rhr': 53, 'sleepHours': 7.7, 'sleepDeep': 20.0, 'sleepREM': 24.8, 'spo2': 97.2, 'respiratoryRate': 14.0, 'skinTemp': 36.5},
]

ALEX_TRAINING = [
    {'distance': 10432, 'avgSplit': 111.5, 'avgSPM': 28, 'maxHR': 178, 'avgHR': 148, 'duration': 52},
    {'distance': 8201, 'avgSplit': 113.8, 'avgSPM': 29, 'maxHR': 172, 'avgHR': 144, 'duration': 42},
    {'distance': 12105, 'avgSplit': 110.2, 'avgSPM': 27, 'maxHR': 181, 'avgHR': 151, 'duration': 58},
    {'distance': 9400, 'avgSplit': 112.5, 'avgSPM': 30, 'maxHR': 175, 'avgHR': 146, 'duration': 47},
    {'distance': 11020, 'avgSplit': 114.0, 'avgSPM': 28, 'maxHR': 179, 'avgHR': 149, 'duration': 55},
    {'distance': 7800, 'avgSplit': 115.5, 'avgSPM': 30, 'maxHR': 170, 'avgHR': 142, 'duration': 40},
    {'distance': 9800, 'avgSplit': 116.2, 'avgSPM': 31, 'maxHR': 176, 'avgHR': 147, 'duration': 50},
]

ALEX_CHECKINS = [
    {'mood': 4, 'motivation': 8, 'fatigue': 4, 'challenge': 'none', 'journal': 'Feeling strong today, ready to train'},
    {'mood': 4, 'motivation': 7, 'fatigue': 5, 'challenge': 'physical_fatigue', 'journal': ''},
    {'mood': 5, 'motivation': 8, 'fatigue': 3, 'challenge': 'none', 'journal': 'Great sleep last night'},
    {'mood': 4, 'motivation': 7, 'fatigue': 4, 'challenge': 'none', 'journal': ''},
    {'mood': 3, 'motivation': 6, 'fatigue': 6, 'challenge': 'physical_fatigue', 'journal': 'Tired but pushing through'},
    {'mood': 4, 'motivation': 7, 'fatigue': 5, 'challenge': 'none', 'journal': ''},
    {'mood': 4, 'motivation': 8, 'fatigue': 4, 'challenge': 'none', 'journal': 'Feeling strong today, ready to train'},
]

JORDAN_HEALTH = [
    {'hrv': 58.0, 'rhr': 54, 'sleepHours': 7.2, 'sleepDeep': 22.0, 'sleepREM': 26.0, 'spo2': 97.5, 'respiratoryRate': 14.2, 'skinTemp': 36.4},
    {'hrv': 55.0, 'rhr': 55, 'sleepHours': 6.8, 'sleepDeep': 19.0, 'sleepREM': 24.0, 'spo2': 97.2, 'respiratoryRate': 14.5, 'skinTemp': 36.5},
    {'hrv': 52.0, 'rhr': 56, 'sleepHours': 6.5, 'sleepDeep': 17.0, 'sleepREM': 23.0, 'spo2': 97.0, 'respiratoryRate': 14.8, 'skinTemp': 36.6},
    {'hrv': 49.0, 'rhr': 57, 'sleepHours': 6.2, 'sleepDeep': 16.0, 'sleepREM': 21.0, 'spo2': 96.8, 'respiratoryRate': 15.1, 'skinTemp': 36.7},
    {'hrv': 47.0, 'rhr': 58, 'sleepHours': 5.8, 'sleepDeep': 15.0, 'sleepREM': 20.0, 'spo2': 96.5, 'respiratoryRate': 15.3, 'skinTemp': 36.8},
    {'hrv': 44.0, 'rhr': 59, 'sleepHours': 5.5, 'sleepDeep': 14.0, 'sleepREM': 19.0, 'spo2': 96.3, 'respiratoryRate': 15.6, 'skinTemp': 36.9},
    {'hrv': 42.0, 'rhr': 60, 'sleepHours': 5.2, 'sleepDeep': 13.0, 'sleepREM': 18.0, 'spo2': 96.0, 'respiratoryRate': 16.0, 'skinTemp': 37.0},
]

JORDAN_TRAINING = [
    {'distance': 9200, 'avgSplit': 114.5, 'avgSPM': 29, 'maxHR': 177, 'avgHR': 147, 'duration': 48},
    {'distance': 8200, 'avgSplit': 116.0, 'avgSPM': 28, 'maxHR': 173, 'avgHR': 144, 'duration': 43},
    {'distance': 10500, 'avgSplit': 115.2, 'avgSPM': 30, 'maxHR': 179, 'avgHR': 149, 'duration': 51},
    {'distance': 7800, 'avgSplit': 117.5, 'avgSPM': 27, 'maxHR': 171, 'avgHR': 142, 'duration': 40},
    {'distance': 9800, 'avgSplit': 118.0, 'avgSPM': 29, 'maxHR': 176, 'avgHR': 146, 'duration': 49},
    {'distance': 7200, 'avgSplit': 119.2, 'avgSPM': 28, 'maxHR': 169, 'avgHR': 141, 'duration': 38},
    {'distance': 8500, 'avgSplit': 120.5, 'avgSPM': 30, 'maxHR': 174, 'avgHR': 145, 'duration': 44},
]

JORDAN_CHECKINS = [
    {'mood': 4, 'motivation': 7, 'fatigue': 4, 'challenge': 'physical_fatigue', 'journal': 'Okay today'},
    {'mood': 4, 'motivation': 6, 'fatigue': 5, 'challenge': 'physical_fatigue', 'journal': 'Tired but pushing through'},
    {'mood': 3, 'motivation': 5, 'fatigue': 6, 'challenge': 'mental_fatigue', 'journal': 'Tired but pushing through'},
    {'mood': 3, 'motivation': 5, 'fatigue': 6, 'challenge': 'mental_fatigue', 'journal': 'Everything feels heavy. Not sure I want to keep going.'},
    {'mood': 2, 'motivation': 4, 'fatigue': 7, 'challenge': 'mental_fatigue', 'journal': 'Everything feels heavy. Not sure I want to keep going.'},
    {'mood': 2, 'motivation': 3, 'fatigue': 8, 'challenge': 'mental_fatigue', 'journal': 'Everything feels heavy. Not sure I want to keep going.'},
    {'mood': 2, 'motivation': 3, 'fatigue': 8, 'challenge': 'mental_fatigue', 'journal': 'Everything feels heavy. Not sure I want to keep going.'},
]

MORGAN_HEALTH = [
    {'hrv': 55.0, 'rhr': 56, 'sleepHours': 6.8, 'sleepDeep': 18.0, 'sleepREM': 22.0, 'spo2': 97.0, 'respiratoryRate': 14.5, 'skinTemp': 36.5},
    {'hrv': 50.0, 'rhr': 58, 'sleepHours': 6.2, 'sleepDeep': 16.0, 'sleepREM': 20.0, 'spo2': 96.7, 'respiratoryRate': 15.0, 'skinTemp': 36.7},
    {'hrv': 44.0, 'rhr': 60, 'sleepHours': 5.5, 'sleepDeep': 14.0, 'sleepREM': 18.0, 'spo2': 96.3, 'respiratoryRate': 15.5, 'skinTemp': 36.9},
    {'hrv': 38.0, 'rhr': 63, 'sleepHours': 5.0, 'sleepDeep': 11.0, 'sleepREM': 15.0, 'spo2': 95.8, 'respiratoryRate': 16.2, 'skinTemp': 37.1},
    {'hrv': 35.0, 'rhr': 64, 'sleepHours': 4.5, 'sleepDeep': 10.0, 'sleepREM': 14.0, 'spo2': 95.5, 'respiratoryRate': 16.8, 'skinTemp': 37.3},
    {'hrv': 32.0, 'rhr': 66, 'sleepHours': 4.2, 'sleepDeep': 9.0, 'sleepREM': 13.0, 'spo2': 95.2, 'respiratoryRate': 17.2, 'skinTemp': 37.4},
    {'hrv': 30.0, 'rhr': 67, 'sleepHours': 4.0, 'sleepDeep': 8.0, 'sleepREM': 12.0, 'spo2': 95.0, 'respiratoryRate': 17.5, 'skinTemp': 37.5},
]

MORGAN_TRAINING = [
    {'distance': 8000, 'avgSplit': 115.0, 'avgSPM': 28, 'maxHR': 170, 'avgHR': 148, 'duration': 45},
    {'distance': 7400, 'avgSplit': 118.0, 'avgSPM': 28, 'maxHR': 173, 'avgHR': 150, 'duration': 42},
    {'distance': 6800, 'avgSplit': 121.0, 'avgSPM': 27, 'maxHR': 176, 'avgHR': 152, 'duration': 39},
    {'distance': 6200, 'avgSplit': 124.0, 'avgSPM': 27, 'maxHR': 179, 'avgHR': 154, 'duration': 36},
    {'distance': 5600, 'avgSplit': 127.0, 'avgSPM': 26, 'maxHR': 182, 'avgHR': 156, 'duration': 33},
    {'distance': 5000, 'avgSplit': 130.0, 'avgSPM': 26, 'maxHR': 185, 'avgHR': 158, 'duration': 30},
    {'distance': 4400, 'avgSplit': 133.0, 'avgSPM': 25, 'maxHR': 188, 'avgHR': 160, 'duration': 27},
]

MORGAN_CHECKINS = [
    {'mood': 3, 'motivation': 5, 'fatigue': 5, 'challenge': 'physical_fatigue', 'journal': 'Struggling to keep pace, everything hurts'},
    {'mood': 3, 'motivation': 4, 'fatigue': 6, 'challenge': 'physical_fatigue', 'journal': 'Struggling to keep pace, everything hurts'},
    {'mood': 2, 'motivation': 3, 'fatigue': 7, 'challenge': 'mental_fatigue', 'journal': 'Struggling to keep pace, everything hurts'},
    {'mood': 2, 'motivation': 2, 'fatigue': 8, 'challenge': 'mental_fatigue', 'journal': "Can't do this anymore. Body won't cooperate. Mind is blank."},
    {'mood': 1, 'motivation': 1, 'fatigue': 9, 'challenge': 'mental_fatigue', 'journal': "Can't do this anymore. Body won't cooperate. Mind is blank."},
    {'mood': 1, 'motivation': 1, 'fatigue': 9, 'challenge': 'mental_fatigue', 'journal': "Can't do this anymore. Body won't cooperate. Mind is blank."},
    {'mood': 1, 'motivation': 1, 'fatigue': 9, 'challenge': 'mental_fatigue', 'journal': "Can't do this anymore. Body won't cooperate. Mind is blank."},
]

CASEY_HEALTH = [
    {'hrv': 48.0, 'rhr': 58, 'sleepHours': 6.0, 'sleepDeep': 15.0, 'sleepREM': 20.0, 'spo2': 96.8, 'respiratoryRate': 15.0, 'skinTemp': 36.6},
    {'hrv': 43.0, 'rhr': 60, 'sleepHours': 5.2, 'sleepDeep': 12.0, 'sleepREM': 17.0, 'spo2': 96.3, 'respiratoryRate': 15.8, 'skinTemp': 37.0},
    {'hrv': 38.0, 'rhr': 63, 'sleepHours': 4.5, 'sleepDeep': 10.0, 'sleepREM': 14.0, 'spo2': 95.8, 'respiratoryRate': 16.5, 'skinTemp': 37.2},
    {'hrv': 33.0, 'rhr': 65, 'sleepHours': 4.0, 'sleepDeep': 8.0, 'sleepREM': 12.0, 'spo2': 95.2, 'respiratoryRate': 17.0, 'skinTemp': 37.4},
    {'hrv': 30.0, 'rhr': 67, 'sleepHours': 3.8, 'sleepDeep': 7.0, 'sleepREM': 11.0, 'spo2': 95.0, 'respiratoryRate': 17.5, 'skinTemp': 37.6},
    {'hrv': 28.0, 'rhr': 68, 'sleepHours': 3.5, 'sleepDeep': 6.0, 'sleepREM': 10.0, 'spo2': 94.8, 'respiratoryRate': 18.0, 'skinTemp': 37.7},
    {'hrv': 26.0, 'rhr': 70, 'sleepHours': 3.2, 'sleepDeep': 5.0, 'sleepREM': 9.0, 'spo2': 94.5, 'respiratoryRate': 18.5, 'skinTemp': 37.8},
]

CASEY_TRAINING = [
    {'distance': 7000, 'avgSplit': 118.0, 'avgSPM': 26, 'maxHR': 168, 'avgHR': 150, 'duration': 40},
    {'distance': 6200, 'avgSplit': 122.0, 'avgSPM': 25, 'maxHR': 172, 'avgHR': 153, 'duration': 36},
    {'distance': 5400, 'avgSplit': 126.0, 'avgSPM': 25, 'maxHR': 176, 'avgHR': 156, 'duration': 32},
    {'distance': 4600, 'avgSplit': 130.0, 'avgSPM': 24, 'maxHR': 180, 'avgHR': 159, 'duration': 28},
    {'distance': 3800, 'avgSplit': 134.0, 'avgSPM': 24, 'maxHR': 184, 'avgHR': 162, 'duration': 24},
    {'distance': 3000, 'avgSplit': 138.0, 'avgSPM': 23, 'maxHR': 188, 'avgHR': 165, 'duration': 20},
    {'distance': 2200, 'avgSplit': 142.0, 'avgSPM': 23, 'maxHR': 192, 'avgHR': 168, 'duration': 16},
]

CASEY_CHECKINS = [
    {'mood': 2, 'motivation': 4, 'fatigue': 6, 'challenge': 'physical_fatigue', 'journal': 'Barely holding on. Don\'t know how much longer.'},
    {'mood': 2, 'motivation': 3, 'fatigue': 7, 'challenge': 'physical_fatigue', 'journal': 'Barely holding on. Don\'t know how much longer.'},
    {'mood': 2, 'motivation': 2, 'fatigue': 8, 'challenge': 'mental_fatigue', 'journal': 'Barely holding on. Don\'t know how much longer.'},
    {'mood': 1, 'motivation': 2, 'fatigue': 8, 'challenge': 'mental_fatigue', 'journal': 'Barely holding on. Don\'t know how much longer.'},
    {'mood': 1, 'motivation': 1, 'fatigue': 9, 'challenge': 'mental_fatigue', 'journal': 'I feel invisible. Nobody notices I\'m drowning.'},
    {'mood': 1, 'motivation': 1, 'fatigue': 9, 'challenge': 'mental_fatigue', 'journal': 'I feel invisible. Nobody notices I\'m drowning.'},
    {'mood': 1, 'motivation': 1, 'fatigue': 9, 'challenge': 'mental_fatigue', 'journal': 'I feel invisible. Nobody notices I\'m drowning.'},
]

RILEY_HEALTH = [
    {'hrv': 68.2, 'rhr': 50, 'sleepHours': 8.3, 'sleepDeep': 23.5, 'sleepREM': 26.5, 'spo2': 97.6, 'respiratoryRate': 13.8, 'skinTemp': 36.4},
    {'hrv': 66.5, 'rhr': 51, 'sleepHours': 7.9, 'sleepDeep': 21.0, 'sleepREM': 25.0, 'spo2': 97.3, 'respiratoryRate': 14.0, 'skinTemp': 36.5},
    {'hrv': 69.0, 'rhr': 49, 'sleepHours': 8.4, 'sleepDeep': 24.0, 'sleepREM': 27.0, 'spo2': 97.8, 'respiratoryRate': 13.7, 'skinTemp': 36.4},
    {'hrv': 67.5, 'rhr': 50, 'sleepHours': 8.1, 'sleepDeep': 22.5, 'sleepREM': 25.8, 'spo2': 97.5, 'respiratoryRate': 13.9, 'skinTemp': 36.4},
    {'hrv': 70.2, 'rhr': 48, 'sleepHours': 8.5, 'sleepDeep': 24.5, 'sleepREM': 27.5, 'spo2': 97.9, 'respiratoryRate': 13.6, 'skinTemp': 36.3},
    {'hrv': 65.8, 'rhr': 52, 'sleepHours': 7.8, 'sleepDeep': 20.5, 'sleepREM': 24.5, 'spo2': 97.2, 'respiratoryRate': 14.2, 'skinTemp': 36.6},
    {'hrv': 68.5, 'rhr': 50, 'sleepHours': 8.2, 'sleepDeep': 22.0, 'sleepREM': 26.0, 'spo2': 97.5, 'respiratoryRate': 13.8, 'skinTemp': 36.4},
]

RILEY_TRAINING = [
    {'distance': 11200, 'avgSplit': 109.0, 'avgSPM': 27, 'maxHR': 175, 'avgHR': 145, 'duration': 58},
    {'distance': 9500, 'avgSplit': 110.5, 'avgSPM': 28, 'maxHR': 171, 'avgHR': 143, 'duration': 50},
    {'distance': 12000, 'avgSplit': 108.2, 'avgSPM': 27, 'maxHR': 177, 'avgHR': 146, 'duration': 62},
    {'distance': 10200, 'avgSplit': 109.5, 'avgSPM': 28, 'maxHR': 174, 'avgHR': 144, 'duration': 53},
    {'distance': 11500, 'avgSplit': 108.8, 'avgSPM': 27, 'maxHR': 176, 'avgHR': 145, 'duration': 59},
    {'distance': 8800, 'avgSplit': 111.0, 'avgSPM': 29, 'maxHR': 170, 'avgHR': 142, 'duration': 46},
    {'distance': 10500, 'avgSplit': 110.0, 'avgSPM': 28, 'maxHR': 173, 'avgHR': 144, 'duration': 54},
]

RILEY_CHECKINS = [
    {'mood': 5, 'motivation': 9, 'fatigue': 3, 'challenge': 'none', 'journal': 'Feeling strong today, ready to train'},
    {'mood': 4, 'motivation': 8, 'fatigue': 3, 'challenge': 'none', 'journal': 'Feeling strong today, ready to train'},
    {'mood': 5, 'motivation': 9, 'fatigue': 2, 'challenge': 'none', 'journal': 'Feeling strong today, ready to train'},
    {'mood': 4, 'motivation': 8, 'fatigue': 3, 'challenge': 'none', 'journal': 'Feeling strong today, ready to train'},
    {'mood': 5, 'motivation': 9, 'fatigue': 2, 'challenge': 'none', 'journal': 'Feeling strong today, ready to train'},
    {'mood': 4, 'motivation': 7, 'fatigue': 4, 'challenge': 'none', 'journal': 'Feeling strong today, ready to train'},
    {'mood': 5, 'motivation': 9, 'fatigue': 3, 'challenge': 'none', 'journal': 'Feeling strong today, ready to train'},
]

TAYLOR_HEALTH = [
    {'hrv': 44.0, 'rhr': 60, 'sleepHours': 5.5, 'sleepDeep': 14.0, 'sleepREM': 18.0, 'spo2': 96.8, 'respiratoryRate': 15.5, 'skinTemp': 36.8},
    {'hrv': 46.0, 'rhr': 59, 'sleepHours': 5.8, 'sleepDeep': 15.0, 'sleepREM': 19.0, 'spo2': 97.0, 'respiratoryRate': 15.2, 'skinTemp': 36.7},
    {'hrv': 49.0, 'rhr': 57, 'sleepHours': 6.2, 'sleepDeep': 17.0, 'sleepREM': 20.0, 'spo2': 97.1, 'respiratoryRate': 14.9, 'skinTemp': 36.6},
    {'hrv': 53.0, 'rhr': 55, 'sleepHours': 6.8, 'sleepDeep': 19.0, 'sleepREM': 22.0, 'spo2': 97.3, 'respiratoryRate': 14.6, 'skinTemp': 36.5},
    {'hrv': 57.0, 'rhr': 53, 'sleepHours': 7.2, 'sleepDeep': 21.0, 'sleepREM': 24.0, 'spo2': 97.5, 'respiratoryRate': 14.3, 'skinTemp': 36.4},
    {'hrv': 60.0, 'rhr': 52, 'sleepHours': 7.5, 'sleepDeep': 22.0, 'sleepREM': 25.0, 'spo2': 97.6, 'respiratoryRate': 14.1, 'skinTemp': 36.4},
    {'hrv': 63.0, 'rhr': 51, 'sleepHours': 7.8, 'sleepDeep': 23.0, 'sleepREM': 26.0, 'spo2': 97.7, 'respiratoryRate': 14.0, 'skinTemp': 36.3},
]

TAYLOR_TRAINING = [
    {'distance': 6000, 'avgSplit': 113.0, 'avgSPM': 28, 'maxHR': 178, 'avgHR': 150, 'duration': 40},
    {'distance': 6500, 'avgSplit': 112.0, 'avgSPM': 28, 'maxHR': 177, 'avgHR': 149, 'duration': 42},
    {'distance': 7000, 'avgSplit': 111.0, 'avgSPM': 29, 'maxHR': 176, 'avgHR': 148, 'duration': 44},
    {'distance': 7500, 'avgSplit': 110.0, 'avgSPM': 29, 'maxHR': 175, 'avgHR': 147, 'duration': 46},
    {'distance': 8000, 'avgSplit': 109.0, 'avgSPM': 29, 'maxHR': 174, 'avgHR': 146, 'duration': 48},
    {'distance': 8500, 'avgSplit': 108.0, 'avgSPM': 30, 'maxHR': 173, 'avgHR': 145, 'duration': 50},
    {'distance': 9000, 'avgSplit': 107.0, 'avgSPM': 30, 'maxHR': 172, 'avgHR': 144, 'duration': 52},
]

TAYLOR_CHECKINS = [
    {'mood': 3, 'motivation': 5, 'fatigue': 7, 'challenge': 'mental_fatigue', 'journal': 'Coming back slowly, feeling better each day'},
    {'mood': 3, 'motivation': 6, 'fatigue': 6, 'challenge': 'mental_fatigue', 'journal': 'Coming back slowly, feeling better each day'},
    {'mood': 4, 'motivation': 7, 'fatigue': 5, 'challenge': 'none', 'journal': 'Back on track! Energy is returning'},
    {'mood': 4, 'motivation': 7, 'fatigue': 4, 'challenge': 'none', 'journal': 'Back on track! Energy is returning'},
    {'mood': 4, 'motivation': 8, 'fatigue': 3, 'challenge': 'none', 'journal': 'Back on track! Energy is returning'},
    {'mood': 5, 'motivation': 8, 'fatigue': 3, 'challenge': 'none', 'journal': 'Back on track! Energy is returning'},
    {'mood': 5, 'motivation': 9, 'fatigue': 2, 'challenge': 'none', 'journal': 'Back on track! Energy is returning'},
]

ATHLETE_SPECS = [
    {
        'email': 'alex.chen@pivot.dev', 'name': 'Alex Chen', 'position': 'Stroke Seat',
        'school': 'University of Pennsylvania', 'team': 'Varsity Heavyweight 8+',
        'height': 191, 'weight': 86, 'health': ALEX_HEALTH, 'training': ALEX_TRAINING, 'checkins': ALEX_CHECKINS,
    },
    {
        'email': 'jordan.lee@pivot.dev', 'name': 'Jordan Lee', 'position': 'Bow Seat',
        'school': 'University of Pennsylvania', 'team': 'Varsity Heavyweight 8+',
        'height': 188, 'weight': 82, 'health': JORDAN_HEALTH, 'training': JORDAN_TRAINING, 'checkins': JORDAN_CHECKINS,
    },
    {
        'email': 'morgan.smith@pivot.dev', 'name': 'Morgan Smith', 'position': '3 Seat',
        'school': 'University of Pennsylvania', 'team': 'Varsity Heavyweight 8+',
        'height': 196, 'weight': 89, 'health': MORGAN_HEALTH, 'training': MORGAN_TRAINING, 'checkins': MORGAN_CHECKINS,
    },
    {
        'email': 'casey.park@pivot.dev', 'name': 'Casey Park', 'position': 'Coxswain',
        'school': 'University of Pennsylvania', 'team': 'Varsity Heavyweight 8+',
        'height': 165, 'weight': 55, 'health': CASEY_HEALTH, 'training': CASEY_TRAINING, 'checkins': CASEY_CHECKINS,
    },
    {
        'email': 'riley.kim@pivot.dev', 'name': 'Riley Kim', 'position': '2 Seat',
        'school': 'University of Washington', 'team': 'Varsity 8+',
        'height': 193, 'weight': 88, 'health': RILEY_HEALTH, 'training': RILEY_TRAINING, 'checkins': RILEY_CHECKINS,
    },
    {
        'email': 'taylor.brooks@pivot.dev', 'name': 'Taylor Brooks', 'position': '4 Seat',
        'school': 'University of Washington', 'team': 'Varsity 8+',
        'height': 190, 'weight': 84, 'health': TAYLOR_HEALTH, 'training': TAYLOR_TRAINING, 'checkins': TAYLOR_CHECKINS,
    },
]

ALERT_RULES = [
    {
        'name': 'Recovery Deficiency',
        'level': 'yellow',
        'sport': 'rowing',
        'conditions': {'type': 'trend', 'message': 'HRV declined over recent check-ins — prioritize active recovery today.'},
    },
    {
        'name': 'Sleep Deprivation',
        'level': 'yellow',
        'sport': 'rowing',
        'conditions': {'metric': 'sleep_hours', 'operator': '<', 'threshold': 6, 'message': 'Reported sleep under 6 hours — emotional vulnerability risk.'},
    },
    {
        'name': 'Physical & Mental Fatigue',
        'level': 'red',
        'sport': 'rowing',
        'conditions': {'metric': 'hrv', 'operator': '<', 'threshold': 45, 'message': 'HRV critically low — burnout risk.'},
    },
    {
        'name': 'Sleep Deprivation — Critical',
        'level': 'red',
        'sport': 'rowing',
        'conditions': {'metric': 'sleep_hours', 'operator': '<', 'threshold': 5, 'message': '3+ nights poor sleep — consider reducing load.'},
    },
    {
        'name': 'Mood Decline',
        'level': 'red',
        'sport': '*',
        'conditions': {'checkin': 'mood', 'operator': '<', 'threshold': 2, 'message': 'Mood score dropped significantly — check in personally.'},
    },
    {
        'name': 'URGENT: Athlete in Crisis',
        'level': 'black',
        'sport': 'rowing',
        'conditions': {'metric': 'hrv', 'operator': '<', 'threshold': 35, 'message': 'Multiple severe markers — immediate coach intervention needed.'},
    },
]


def _get_or_create_athlete(spec):
    existing = get_user_by_email(spec['email'])
    if existing:
        return existing
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
    }, _hash(PASSWORD))
    print(f"Created athlete: {spec['name']} (id={user['id']})")
    return user


def _link_to_head_coach(athlete_id):
    conn = get_db()
    rows = conn.execute("SELECT id FROM users WHERE role='coach' AND coach_role='Head Coach' ORDER BY id LIMIT 1").fetchall()
    conn.close()
    if rows:
        coach_id = rows[0]['id']
        create_coach_athlete_link(coach_id, athlete_id, 'primary')
        print(f"  Linked athlete {athlete_id} to head coach {coach_id}")


def _import_metrics(user_id, health, training):
    for i, date in enumerate(DAYS):
        h = health[i]
        create_health_metric(user_id, {
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
        t = training[i]
        create_training_metric(user_id, {
            'date': date,
            'distance': t['distance'],
            'avgSplit': t['avgSplit'],
            'avgSPM': t['avgSPM'],
            'maxHR': t['maxHR'],
            'avgHR': t['avgHR'],
            'duration': t['duration'],
        })


def _import_checkins(user_id, checkins):
    for i, date in enumerate(DAYS):
        c = checkins[i]
        create_checkin(user_id, {
            'date': date,
            'mood': c['mood'],
            'motivation': c['motivation'],
            'fatigue': c['fatigue'],
            'challenge': c['challenge'],
            'journal': c['journal'],
        })


def main():
    init_db()
    _drop_seed_tables()

    print('Creating alert rules...')
    for rule in ALERT_RULES:
        create_alert_rule(rule)
    print(f'  Created {len(ALERT_RULES)} rules')

    print('Creating/upserting athletes and importing data...')
    for spec in ATHLETE_SPECS:
        user = _get_or_create_athlete(spec)
        _link_to_head_coach(user['id'])
        _import_metrics(user['id'], spec['health'], spec['training'])
        _import_checkins(user['id'], spec['checkins'])
        created = evaluate_alerts_for_user(user['id'])
        print(f"  {spec['name']}: imported {len(DAYS)} days, created {len(created)} alerts")

    print('\nSeed complete.')
    conn = get_db()
    stats = {
        'athletes': conn.execute("SELECT COUNT(*) FROM users WHERE role='athlete'").fetchone()[0],
        'coaches': conn.execute("SELECT COUNT(*) FROM users WHERE role='coach'").fetchone()[0],
        'checkins': conn.execute('SELECT COUNT(*) FROM checkins').fetchone()[0],
        'health_metrics': conn.execute('SELECT COUNT(*) FROM health_metrics').fetchone()[0],
        'training_metrics': conn.execute('SELECT COUNT(*) FROM training_metrics').fetchone()[0],
        'alerts': conn.execute('SELECT COUNT(*) FROM alerts').fetchone()[0],
        'links': conn.execute('SELECT COUNT(*) FROM coach_athlete_links').fetchone()[0],
    }
    conn.close()
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
