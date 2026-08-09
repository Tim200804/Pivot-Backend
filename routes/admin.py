"""Temporary admin helpers for one-off data operations.

This blueprint is intentionally narrow and token-protected. Remove it once
backfill operations are complete.
"""
import os
from flask import Blueprint, request, jsonify

from seed_athlete import seed_alex_chen

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def _check_token():
    expected = os.environ.get('ADMIN_SEED_TOKEN', '').strip()
    if not expected:
        return False
    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        return header[7:] == expected
    return request.args.get('token') == expected


@admin_bp.route('/seed-alex', methods=['POST'])
def seed_alex():
    if not _check_token():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    try:
        result = seed_alex_chen()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
