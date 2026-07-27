from flask import Blueprint, request, jsonify
import requests
import time

schools_bp = Blueprint('schools', __name__, url_prefix='/api/schools')

# In-memory cache
_schools_cache = None
_cache_time = 0
CACHE_DURATION = 3600  # 1 hour

NCAA_API_URL = 'https://ncaa-api.henrygd.me/schools-index'


def _fetch_schools():
    """Fetch all NCAA schools from public API with caching."""
    global _schools_cache, _cache_time
    if _schools_cache and time.time() - _cache_time < CACHE_DURATION:
        return _schools_cache

    try:
        resp = requests.get(NCAA_API_URL, timeout=15)
        resp.raise_for_status()
        _schools_cache = resp.json()
        _cache_time = time.time()
        return _schools_cache
    except Exception:
        # Return cached data if available, else empty list
        return _schools_cache or []


@schools_bp.route('', methods=['GET'])
def search_schools():
    """Search NCAA schools by name."""
    q = request.args.get('q', '').strip().lower()
    if len(q) < 2:
        return jsonify([])

    schools = _fetch_schools()
    results = []

    for school in schools:
        slug = school.get('slug', '')
        name = school.get('name', '')
        long_name = school.get('long', '')

        # Match against slug, short name, or full name
        if (q in slug.lower()
                or q in name.lower()
                or q in long_name.lower()):
            results.append({
                'id': slug,
                'name': name,
                'fullName': long_name
            })

        if len(results) >= 20:
            break

    return jsonify(results)
