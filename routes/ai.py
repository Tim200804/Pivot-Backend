from flask import Blueprint, request, jsonify
from openai import OpenAI
import os

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# Moonshot (Kimi) client
_kimi_client = None


def _get_client():
    global _kimi_client
    if _kimi_client is None:
        api_key = os.environ.get('MOONSHOT_API_KEY')
        if not api_key:
            raise RuntimeError('MOONSHOT_API_KEY not configured')
        _kimi_client = OpenAI(
            api_key=api_key,
            base_url='https://api.moonshot.cn/v1',
            timeout=60.0,
        )
    return _kimi_client


def _build_system_prompt():
    return (
        'You are Pivot, a supportive sports psychology AI coach for NCAA Division 1 athletes.\n\n'
        'Your role:\n'
        '- Help athletes understand what their mind and body are telling them\n'
        '- Be warm, direct, and psychologically aware\n'
        '- Use "you" language and short, readable sentences\n'
        '- Ground responses in the athlete\'s actual data when relevant\n'
        '- Never give medical diagnoses; suggest talking to coaches/medical staff when needed\n'
        '- Keep most responses to 2-4 sentences unless the user asks for detail'
    )


def _build_data_summary(data):
    athlete = data.get('athlete', {})
    checkin = data.get('checkin', {})
    health = athlete.get('health', [])

    if not health:
        return 'No health data available.'

    first = health[0]
    last = health[-1]
    avg_sleep = round(sum(h.get('sleepHours', 0) for h in health) / len(health), 1)
    hrv_trend = 'declining' if last.get('hrv', 0) < first.get('hrv', 0) else 'improving'

    return (
        f"Athlete: {athlete.get('name', 'Unknown')}, {athlete.get('age', '-')}, "
        f"{athlete.get('position', '-')}, {athlete.get('team', '-')}, {athlete.get('school', '-')}.\n"
        f"Status: {athlete.get('status', '-')}. HRV {first.get('hrv')}→{last.get('hrv')} ({hrv_trend}). "
        f"Sleep avg: {avg_sleep}h. Latest: Mood {checkin.get('mood', '-')}/5, Motivation {checkin.get('motivation', '-')}/10, "
        f"Fatigue {checkin.get('fatigue', '-')}/10. Journal: \"{checkin.get('journal') or 'None'}\""
    )


@ai_bp.route('/insight', methods=['POST'])
def ai_insight():
    data = request.get_json() or {}
    athlete = data.get('athlete')
    checkin = data.get('checkin')

    if not athlete or not checkin:
        return jsonify({'success': False, 'message': 'athlete and checkin required'}), 400

    try:
        client = _get_client()
    except RuntimeError as e:
        return jsonify({'success': False, 'message': str(e)}), 503

    data_summary = _build_data_summary(data)
    prompt = (
        f"{data_summary}\n\n"
        "## Your task:\n"
        "Write a 2-3 sentence personalized insight as their AI coach.\n"
        "DO NOT analyze data. Instead, speak directly to the athlete with psychological awareness.\n"
        "- If they're struggling: be warm, normalize their experience, suggest one concrete action\n"
        "- If they're recovering: acknowledge progress, encourage patience\n"
        "- If they're doing well: challenge them to maintain, note what to watch for\n"
        'Use "you" language. Be human, not robotic. Keep it under 60 words.'
    )

    try:
        completion = client.chat.completions.create(
            model='kimi-k2.6',
            messages=[
                {'role': 'system', 'content': _build_system_prompt()},
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=2000,
        )
        text = completion.choices[0].message.content.strip()
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'message': f'AI error: {str(e)}'}), 502


@ai_bp.route('/chat', methods=['POST'])
def ai_chat():
    data = request.get_json() or {}
    athlete = data.get('athlete')
    checkin = data.get('checkin')
    messages = data.get('messages', [])

    if not athlete or not checkin:
        return jsonify({'success': False, 'message': 'athlete and checkin required'}), 400

    try:
        client = _get_client()
    except RuntimeError as e:
        return jsonify({'success': False, 'message': str(e)}), 503

    data_summary = _build_data_summary(data)

    api_messages = [
        {'role': 'system', 'content': _build_system_prompt()},
        {'role': 'system', 'content': f'Athlete context:\n{data_summary}'},
    ]

    for m in messages:
        role = m.get('role')
        text = m.get('text') or m.get('content')
        if role and text:
            api_messages.append({'role': role, 'content': text})

    try:
        completion = client.chat.completions.create(
            model='kimi-k2.6',
            messages=api_messages,
            max_tokens=4000,
        )
        text = completion.choices[0].message.content.strip()
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'message': f'AI error: {str(e)}'}), 502
