# Server-side whitelist of enum-like values used during registration.
# Frontend MUST source these from /api/auth/options rather than hard-coding.

SPORTS = ('rowing', 'basketball')

COACH_ROLES = (
    'Head Coach',
    'Assistant Coach',
    'Strength & Conditioning Coach',
    'Sports Psychologist',
    'Athletic Trainer',
    'Performance Analyst',
)

ATHLETE_POSITIONS_BY_SPORT = {
    'rowing': [
        'Stroke Seat', '7 Seat', '6 Seat', '5 Seat', '4 Seat',
        '3 Seat', '2 Seat', 'Bow Seat', 'Coxswain', 'Sculler',
        'Port', 'Starboard',
    ],
    'basketball': [
        'Point Guard (PG)', 'Shooting Guard (SG)', 'Small Forward (SF)',
        'Power Forward (PF)', 'Center (C)',
    ],
}