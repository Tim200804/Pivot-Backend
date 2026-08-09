import bcrypt
from models import create_user, get_user_by_email

EMAIL = '2'
PASSWORD = '12345678ABC'

if get_user_by_email(EMAIL):
    print(f'User {EMAIL} already exists, skipping')
else:
    password_hash = bcrypt.hashpw(PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = create_user({
        'email': EMAIL,
        'name': 'Test Athlete 2',
        'role': 'athlete',
        'sport': 'rowing',
        'school': 'University of Pennsylvania',
        'teamName': 'Test Team',
        'position': 'Stroke Seat',
        'height': 188,
        'weight': 82,
    }, password_hash)
    print(f'Created test athlete: id={user["id"]}, email={user["email"]}, name={user["name"]}')
    # Verify password matches
    ok = bcrypt.checkpw(PASSWORD.encode('utf-8'), password_hash.encode('utf-8'))
    print(f'Password verification check: {ok}')
