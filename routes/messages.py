from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import (
    create_message, list_messages_for_user, list_messages_from_user,
    mark_message_read, count_unread, get_user_by_id, get_message_by_id,
    message_to_public,
)

messages_bp = Blueprint('messages', __name__, url_prefix='/api/messages')


@messages_bp.route('', methods=['GET'])
@jwt_required()
def list_messages():
    """List messages for the current user.

    - Athletes (role=athlete) see their inbox (recipient_id == self).
    - Coaches (role=coach) see their sent history (sender_id == self).
      Optionally pass ?unread=true to get only unread inbox items.
    """
    user_id = int(get_jwt_identity())
    me = get_user_by_id(user_id)
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    unread = request.args.get('unread', '').lower() == 'true'
    limit = min(int(request.args.get('limit', 50)), 200)

    if me['role'] == 'athlete':
        msgs = list_messages_for_user(user_id, limit=limit, unread_only=unread)
        # Hydrate sender name so the UI can show "Coach Williams"
        result = []
        for m in msgs:
            sender = get_user_by_id(m['sender_id'])
            result.append(message_to_public(m, sender))
        return jsonify({
            'success': True,
            'messages': result,
            'unreadCount': count_unread(user_id),
        })

    # Coach: sent history
    msgs = list_messages_from_user(user_id, limit=limit)
    result = []
    for m in msgs:
        recipient = get_user_by_id(m['recipient_id'])
        d = message_to_public(m)
        if recipient:
            d['recipientName'] = recipient['name']
        result.append(d)
    return jsonify({'success': True, 'messages': result})


@messages_bp.route('', methods=['POST'])
@jwt_required()
def send_message():
    """Coach sends a message to an athlete."""
    sender_id = int(get_jwt_identity())
    sender = get_user_by_id(sender_id)
    if not sender or sender['role'] != 'coach':
        return jsonify({'success': False, 'message': 'Only coaches can send messages'}), 403

    data = request.get_json() or {}
    recipient_id = data.get('recipientId') or data.get('recipient_id')
    body = (data.get('body') or '').strip()
    if not recipient_id or not body:
        return jsonify({'success': False, 'message': 'recipientId and body are required'}), 400

    try:
        recipient_id = int(recipient_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid recipientId'}), 400

    recipient = get_user_by_id(recipient_id)
    if not recipient:
        return jsonify({'success': False, 'message': 'Recipient not found'}), 404
    if recipient['role'] != 'athlete':
        return jsonify({'success': False, 'message': 'Recipient must be an athlete'}), 400

    msg = create_message(
        sender_id=sender_id,
        recipient_id=recipient_id,
        body=body,
        subject=data.get('subject'),
        alert_level=data.get('alertLevel'),
        alert_type=data.get('alertType'),
    )
    return jsonify({
        'success': True,
        'message': message_to_public(msg, sender),
    }), 201


@messages_bp.route('/<int:msg_id>/read', methods=['PATCH', 'POST'])
@jwt_required()
def mark_read(msg_id):
    user_id = int(get_jwt_identity())
    msg = mark_message_read(msg_id, user_id)
    if not msg:
        return jsonify({'success': False, 'message': 'Message not found'}), 404
    return jsonify({'success': True, 'message': message_to_public(msg)})


@messages_bp.route('/unread-count', methods=['GET'])
@jwt_required()
def unread_count():
    user_id = int(get_jwt_identity())
    return jsonify({'success': True, 'unreadCount': count_unread(user_id)})
