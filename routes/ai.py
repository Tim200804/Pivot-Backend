from flask import Blueprint, request, jsonify
from openai import OpenAI
import os, json, re, time, traceback, threading, base64, math

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# Moonshot (Kimi) client — always live; no mock branch
# Auth to Moonshot uses ONLY MOONSHOT_API_KEY below — never the client's Authorization header.
_kimi_client = None
MAX_CHAT_HISTORY = 40

# Org concurrency limit is 3; keep a lower local cap and retry on 429.
_MOONSHOT_MAX_CONCURRENCY = max(1, int(os.environ.get('MOONSHOT_MAX_CONCURRENCY', '2')))
_moonshot_sem = threading.Semaphore(_MOONSHOT_MAX_CONCURRENCY)
_MOONSHOT_MAX_RETRIES = max(1, int(os.environ.get('MOONSHOT_MAX_RETRIES', '5')))
_MOONSHOT_SLOT_TIMEOUT = float(os.environ.get('MOONSHOT_SLOT_TIMEOUT', '90'))


def _is_rate_limit_error(exc):
    msg = str(exc).lower()
    return (
        '429' in msg
        or 'rate_limit' in msg
        or 'concurrency' in msg
        or 'rate limit' in msg
    )


def _retry_after_seconds(exc, attempt):
    match = re.search(r'try again after (\d+)', str(exc), re.I)
    if match:
        return float(match.group(1)) + 0.35
    return min(1.0 * (2 ** attempt), 8.0)


def _ai_error_response(exc):
    """Map Moonshot errors to HTTP status + friendly message."""
    if isinstance(exc, TimeoutError):
        return jsonify({
            'success': False,
            'message': 'AI is busy right now. Please wait a moment and try again.',
        }), 429
    if _is_rate_limit_error(exc):
        return jsonify({
            'success': False,
            'message': 'AI rate limit reached. Please wait a second and try again.',
        }), 429
    return jsonify({'success': False, 'message': f'AI error: {str(exc)}'}), 502


@ai_bp.before_request
def _ignore_client_authorization():
    """AI routes do not use pivot JWT. Drop inbound Authorization so it cannot be mistaken for a Kimi key."""
    request.environ.pop('HTTP_AUTHORIZATION', None)


def _get_client():
    """OpenAI-compatible client authenticated with server-side MOONSHOT_API_KEY only."""
    global _kimi_client
    if _kimi_client is None:
        api_key = os.environ.get('MOONSHOT_API_KEY')
        if not api_key:
            raise RuntimeError('MOONSHOT_API_KEY not configured')
        _kimi_client = OpenAI(
            api_key=api_key,
            base_url='https://api.moonshot.cn/v1',
            timeout=90.0,
        )
    return _kimi_client


def _create_completion(**kwargs):
    """
    Call Moonshot with:
    1) local semaphore so we don't exceed org concurrency (default 2 of 3)
    2) retries on 429 concurrency / rate_limit errors
    Returns the full completion object (non-streaming).
    """
    client = _get_client()
    last_err = None

    for attempt in range(_MOONSHOT_MAX_RETRIES):
        acquired = _moonshot_sem.acquire(timeout=_MOONSHOT_SLOT_TIMEOUT)
        if not acquired:
            raise TimeoutError('AI service is busy, please try again in a moment')

        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            _moonshot_sem.release()
            last_err = e
            if _is_rate_limit_error(e) and attempt < _MOONSHOT_MAX_RETRIES - 1:
                wait = _retry_after_seconds(e, attempt)
                print(f'[ai] Moonshot rate limit, retry {attempt + 1}/{_MOONSHOT_MAX_RETRIES} after {wait:.1f}s')
                time.sleep(wait)
                continue
            raise

    raise last_err


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
    try:
        athlete = data.get('athlete') or {}
        checkin = data.get('checkin') or {}

        if not isinstance(athlete, dict):
            return 'Athlete data unavailable (invalid format).'

        health = athlete.get('health')
        if not isinstance(health, list) or len(health) == 0:
            return 'No health data available.'

        valid_health = [h for h in health if isinstance(h, dict)]
        if len(valid_health) == 0:
            return 'No valid health data available.'

        first = valid_health[0]
        last = valid_health[-1]
        avg_sleep = round(sum(h.get('sleepHours', 0) for h in valid_health) / len(valid_health), 1)
        hrv_trend = 'declining' if last.get('hrv', 0) < first.get('hrv', 0) else 'improving'

        return (
            f"Athlete: {athlete.get('name', 'Unknown')}, {athlete.get('age', '-')}y, "
            f"{athlete.get('position', '-')}, {athlete.get('team', '-')}, {athlete.get('school', '-')}.\n"
            f"Status: {athlete.get('status', '-')}. HRV {first.get('hrv', '-')}→{last.get('hrv', '-')} ({hrv_trend}). "
            f"Sleep avg: {avg_sleep}h. Latest: Mood {checkin.get('mood', '-')}/5, Motivation {checkin.get('motivation', '-')}/10, "
            f"Fatigue {checkin.get('fatigue', '-')}/10. Journal: \"{checkin.get('journal') or 'None'}\""
        )
    except Exception as e:
        traceback.print_exc()
        return f'Data summary unavailable ({str(e)}).'


def _normalize_chat_messages(messages):
    """Convert client message list into OpenAI chat roles; keep recent history only."""
    api_messages = []
    if not isinstance(messages, list):
        return api_messages

    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get('role')
        text = m.get('text') or m.get('content')
        if role not in ('user', 'assistant', 'system') or not text:
            continue
        api_role = 'assistant' if role == 'assistant' else role
        api_messages.append({'role': api_role, 'content': str(text)})

    if len(api_messages) > MAX_CHAT_HISTORY:
        api_messages = api_messages[-MAX_CHAT_HISTORY:]
    return api_messages


@ai_bp.route('/insight', methods=['POST'])
def ai_insight():
    try:
        data = request.get_json() or {}
        athlete = data.get('athlete')
        checkin = data.get('checkin')

        if not athlete or not checkin:
            return jsonify({'success': False, 'message': 'athlete and checkin required'}), 400

        try:
            _get_client()
        except Exception as e:
            traceback.print_exc()
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
            completion = _create_completion(
                model='kimi-k2.6',
                messages=[
                    {'role': 'system', 'content': _build_system_prompt()},
                    {'role': 'user', 'content': prompt},
                ],
                max_tokens=2000,
            )
            text = (completion.choices[0].message.content or '').strip()
            if not text:
                return jsonify({'success': False, 'message': 'Empty AI response'}), 502
            return jsonify({'success': True, 'text': text})
        except Exception as e:
            traceback.print_exc()
            return _ai_error_response(e)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@ai_bp.route('/chat', methods=['POST'])
def ai_chat():
    """
    Real Kimi conversation — non-streaming JSON response.
    Returns: {"success": true, "text": "..."}
    (Streaming was disabled to simplify the client; full text arrives at once.)
    """
    try:
        data = request.get_json() or {}
        athlete = data.get('athlete')
        checkin = data.get('checkin')
        messages = data.get('messages') or []

        if not athlete or not checkin:
            return jsonify({'success': False, 'message': 'athlete and checkin required'}), 400

        if not isinstance(messages, list):
            return jsonify({'success': False, 'message': 'messages must be a list'}), 400

        try:
            _get_client()
        except Exception as e:
            traceback.print_exc()
            return jsonify({'success': False, 'message': str(e)}), 503

        data_summary = _build_data_summary(data)

        api_messages = [
            {'role': 'system', 'content': _build_system_prompt()},
            {'role': 'system', 'content': f'Athlete context:\n{data_summary}'},
        ]
        api_messages.extend(_normalize_chat_messages(messages))

        if not any(m.get('role') == 'user' for m in api_messages):
            return jsonify({'success': False, 'message': 'at least one user message required'}), 400

        try:
            completion = _create_completion(
                model='kimi-k2.6',
                messages=api_messages,
                max_tokens=4000,
            )
            text = (completion.choices[0].message.content or '').strip()
            if not text:
                return jsonify({'success': False, 'message': 'Empty AI response'}), 502
            return jsonify({'success': True, 'text': text})
        except Exception as e:
            traceback.print_exc()
            return _ai_error_response(e)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@ai_bp.route('/low-period-support', methods=['POST'])
def ai_low_period_support():
    try:
        data = request.get_json() or {}
        athlete = data.get('athlete')
        checkin = data.get('checkin')

        if not athlete or not checkin:
            return jsonify({'success': False, 'message': 'athlete and checkin required'}), 400

        try:
            _get_client()
        except Exception as e:
            traceback.print_exc()
            return jsonify({'success': False, 'message': str(e)}), 503

        data_summary = _build_data_summary(data)
        prompt = (
            f"{data_summary}\n\n"
            "## Your task:\n"
            "The athlete is currently in a low period. Generate personalized 'Low Period Support' content with exactly 3 cards.\n\n"
            "Card 1 — 'You're Not Alone':\n"
            "- A statistic or reassuring fact relevant to their situation\n"
            "- 1-2 warm, normalizing sentences\n\n"
            "Card 2 — 'You've Come Back Before':\n"
            "- A highlight number based on their data (e.g., recovery count, days)\n"
            "- 1-2 sentences referencing their resilience and past recovery\n\n"
            "Card 3 — 'What You Can Do Now':\n"
            "- 3 actionable, specific bullet points tailored to their sport, data, and current state\n\n"
            "Return ONLY a valid JSON object in this exact format (no markdown, no code fences):\n"
            '{\n'
            '  "cards": [\n'
            '    {"title": "You\'re Not Alone", "highlight": "44%", "body": "string text"},\n'
            '    {"title": "You\'ve Come Back Before", "highlight": "3 times", "body": "string text"},\n'
            '    {"title": "What You Can Do Now", "highlight": null, "body": ["action 1", "action 2", "action 3"]}\n'
            '  ]\n'
            '}'
        )

        try:
            completion = _create_completion(
                model='kimi-k2.6',
                messages=[
                    {'role': 'system', 'content': _build_system_prompt()},
                    {'role': 'user', 'content': prompt},
                ],
                max_tokens=2000,
            )
            raw = (completion.choices[0].message.content or '').strip()
            if raw.startswith('```'):
                raw = raw.split('\n', 1)[1] if '\n' in raw else raw
            if raw.endswith('```'):
                raw = raw.rsplit('\n', 1)[0] if '\n' in raw else raw
            if raw.startswith('json'):
                raw = raw.split('\n', 1)[1] if '\n' in raw else raw
            parsed = json.loads(raw)
            return jsonify({'success': True, 'cards': parsed.get('cards', [])})
        except Exception as e:
            traceback.print_exc()
            return _ai_error_response(e)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


def generate_substitution_support_text(athlete: dict, checkin: dict, earliest_rest_date: str) -> str | None:
    """Generate an encouraging message for an athlete who cannot be substituted."""
    try:
        _get_client()
    except Exception:
        return None

    data_summary = _build_data_summary({'athlete': athlete, 'checkin': checkin})
    prompt = (
        f"{data_summary}\n\n"
        "## Your task:\n"
        f"The athlete is not recovering well enough to skip a mandatory team training session today, but they still need to attend. "
        f"Encourage them and let them know they can plan to rest as early as {earliest_rest_date}. "
        "Write a short, warm, supportive message (2-4 sentences) acknowledging their current metrics, encouraging them to get through today's team session safely, and clearly stating the earliest date they can expect to rest. "
        "Be realistic, caring, and psychologically safe. Keep it under 80 words."
    )

    try:
        completion = _create_completion(
            model='kimi-k2.6',
            messages=[
                {'role': 'system', 'content': _build_system_prompt()},
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=300,
        )
        return (completion.choices[0].message.content or '').strip()
    except Exception:
        traceback.print_exc()
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  Vision-based health data extraction
# ═══════════════════════════════════════════════════════════════════════════════


def _encode_image_to_data_uri(image_bytes: bytes, mime_type: str) -> str:
    """Encode image bytes as a base64 data URI for Kimi vision input."""
    b64 = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:{mime_type};base64,{b64}"


def _strip_code_fences(text: str) -> str:
    """Remove markdown JSON code fences if present."""
    text = (text or '').strip()
    if text.startswith('```'):
        # Drop first fence line
        lines = text.splitlines()
        if len(lines) > 1 and lines[0].strip().startswith('```'):
            lines = lines[1:]
        text = '\n'.join(lines).strip()
    if text.endswith('```'):
        lines = text.splitlines()
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    # Strip leading "json" label if present
    if text.lower().startswith('json'):
        lines = text.splitlines()
        if len(lines) > 1:
            text = '\n'.join(lines[1:]).strip()
    return text


# Accepted image MIME types for Kimi vision
_ALLOWED_IMAGE_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'image/bmp', 'image/heic', 'image/heif',
}


def parse_health_metrics_from_image(image_bytes: bytes, mime_type: str = 'image/png') -> dict:
    """Extract daily health metrics from a screenshot using Kimi vision.

    Args:
        image_bytes: raw image bytes
        mime_type: image MIME type (must be in Kimi vision supported list)

    Returns:
        dict with keys:
            - success: bool
            - rows: list of parsed metric dicts (empty on failure)
            - raw_text: the raw model output (for debugging)
            - message: human-readable status message
    """
    if mime_type.lower() not in _ALLOWED_IMAGE_TYPES:
        return {
            'success': False,
            'rows': [],
            'raw_text': '',
            'message': f'Unsupported image type: {mime_type}. Supported: jpeg, png, gif, webp, bmp, heic, heif',
        }

    try:
        _get_client()
    except Exception as e:
        return {
            'success': False,
            'rows': [],
            'raw_text': '',
            'message': f'AI client not configured: {str(e)}',
        }

    data_uri = _encode_image_to_data_uri(image_bytes, mime_type)

    system_prompt = (
        "You are a data extraction assistant for the Pivot athlete resilience platform. "
        "Your job is to read screenshots of health/training data and return ONLY a valid JSON object. "
        "Do not add explanations, markdown, or code fences."
    )

    user_prompt = (
        "Extract daily health metrics from this screenshot. "
        "The screenshot may show a table, chart, wearable app summary, or fitness tracking app screen. "
        "Return a JSON object with this exact structure:\n"
        "{\n"
        "  \"rows\": [\n"
        "    {\"date\": \"YYYY-MM-DD\", \"hrv\": 58, \"rhr\": 54, \"sleepHours\": 7.2, \"sleepDeep\": null, \"sleepREM\": null, \"spo2\": null, \"respiratoryRate\": null, \"skinTemp\": null},\n"
        "    ...\n"
        "  ]\n"
        "}\n\n"
        "Field rules:\n"
        "- date: ISO-8601 format YYYY-MM-DD. If year is missing, use 2026.\n"
        "- hrv: heart rate variability (usually a number 20-100). If not present, null.\n"
        "- rhr: resting heart rate (usually 40-100 bpm). If not present, null.\n"
        "- sleepHours: total sleep in hours (e.g. 7.5). If not present, null.\n"
        "- sleepDeep: deep sleep percentage (0-100) or null.\n"
        "- sleepREM: REM sleep percentage (0-100) or null.\n"
        "- spo2: blood oxygen percentage (80-100) or null.\n"
        "- respiratoryRate: breaths per minute (8-40) or null.\n"
        "- skinTemp: skin temperature in Celsius or null.\n"
        "\n"
        "Only include rows where at least one numeric metric is readable. "
        "If a metric is unclear, use null rather than guessing. "
        "If no usable data is visible, return {\"rows\": []}."
    )

    try:
        completion = _create_completion(
            model='kimi-k3',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {
                    'role': 'user',
                    'content': [
                        {'type': 'image_url', 'image_url': {'url': data_uri}},
                        {'type': 'text', 'text': user_prompt},
                    ],
                },
            ],
            max_tokens=2000,
        )
    except Exception as e:
        traceback.print_exc()
        return {
            'success': False,
            'rows': [],
            'raw_text': '',
            'message': f'AI vision request failed: {str(e)}',
        }

    raw_text = (completion.choices[0].message.content or '').strip()
    cleaned = _strip_code_fences(raw_text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return {
            'success': False,
            'rows': [],
            'raw_text': raw_text,
            'message': f'AI response was not valid JSON: {str(e)}',
        }

    if not isinstance(parsed, dict):
        return {
            'success': False,
            'rows': [],
            'raw_text': raw_text,
            'message': 'AI response was not a JSON object',
        }

    rows = parsed.get('rows')
    if not isinstance(rows, list):
        return {
            'success': False,
            'rows': [],
            'raw_text': raw_text,
            'message': 'AI response did not contain a rows array',
        }

    # Normalize and lightly validate rows
    normalized = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue

        date_val = row.get('date')
        if not date_val:
            continue
        date_str = str(date_val).strip()
        # Basic ISO date validation / normalization
        try:
            from datetime import datetime as _dt
            if len(date_str) == 8 and date_str.isdigit():
                # YYYYMMDD
                date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            _dt.fromisoformat(date_str)
        except Exception:
            continue

        def _num(val):
            if val is None or val == '':
                return None
            try:
                n = float(val)
                return None if math.isnan(n) or math.isinf(n) else n
            except (TypeError, ValueError):
                return None

        normalized_row = {
            'date': date_str,
            'hrv': _num(row.get('hrv')),
            'rhr': _num(row.get('rhr')),
            'sleepHours': _num(row.get('sleepHours')),
            'sleepDeep': _num(row.get('sleepDeep')),
            'sleepREM': _num(row.get('sleepREM')),
            'spo2': _num(row.get('spo2')),
            'respiratoryRate': _num(row.get('respiratoryRate')),
            'skinTemp': _num(row.get('skinTemp')),
        }

        # Keep row if at least date + one numeric metric is present
        if any(v is not None for k, v in normalized_row.items() if k != 'date'):
            normalized.append(normalized_row)

    return {
        'success': True,
        'rows': normalized,
        'raw_text': raw_text,
        'message': f'Extracted {len(normalized)} row(s) from image',
    }
