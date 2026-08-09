from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import (
    create_message, list_messages_for_user, list_messages_from_user,
    list_conversation, mark_message_read, count_unread, get_user_by_id,
    get_message_by_id, message_to_public,
)

messages_bp = Blueprint('messages', __name__, url_prefix='/api/messages')


@messages_bp.route('', methods=['GET'])
@jwt_required()
def list_messages():
    """List all messages the current user participates in (both sent and received).

    Optionally pass ?unread=true to get only unread inbox items.
    """
    user_id = int(get_jwt_identity())
    me = get_user_by_id(user_id)
    if not me:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    unread = request.args.get('unread', '').lower() == 'true'
    limit = min(int(request.args.get('limit', 50)), 200)

    inbox = list_messages_for_user(user_id, limit=limit, unread_only=unread)
    sent = list_messages_from_user(user_id, limit=limit)

    # Merge, deduplicate, and sort by created_at DESC
    seen = set()
    merged = []
    for m in inbox + sent:
        if m['id'] in seen:
            continue
        seen.add(m['id'])
        other_id = m['sender_id'] if m['sender_id'] != user_id else m['recipient_id']
        other = get_user_by_id(other_id)
        d = message_to_public(m, other if m['sender_id'] != user_id else None)
        d['otherUserId'] = other_id
        d['otherUserName'] = other['name'] if other else None
        d['otherUserRole'] = other['role'] if other else None
        d['isSender'] = m['sender_id'] == user_id
        merged.append(d)

    merged.sort(key=lambda x: x['createdAt'], reverse=True)
    return jsonify({
        'success': True,
        'messages': merged[:limit],
        'unreadCount': count_unread(user_id),
    })


@messages_bp.route('', methods=['POST'])
@jwt_required()
def send_message():
    """Send a message to another user.

    Allowed pairings: coach <-> athlete (bidirectional) and coach <-> coach.
    Athletes cannot message other athletes.
    """
    sender_id = int(get_jwt_identity())
    sender = get_user_by_id(sender_id)
    if not sender:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    data = request.get_json() or {}
    recipient_id = data.get('recipientId') or data.get('recipient_id')
    body = (data.get('body') or '').strip()
    if not recipient_id or not body:
        return jsonify({'success': False, 'message': 'recipientId and body are required'}), 400

    try:
        recipient_id = int(recipient_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid recipientId'}), 400

    if recipient_id == sender_id:
        return jsonify({'success': False, 'message': 'Cannot message yourself'}), 400

    recipient = get_user_by_id(recipient_id)
    if not recipient:
        return jsonify({'success': False, 'message': 'Recipient not found'}), 404

    # Coach <-> athlete or coach <-> coach messaging is supported.
    # Athletes cannot message other athletes.
    if 'coach' not in {sender['role'], recipient['role']}:
        return jsonify({'success': False, 'message': 'Messages only allowed between coach and athlete, or coach and coach'}), 400

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


@messages_bp.route('/conversation/<int:other_user_id>', methods=['GET'])
@jwt_required()
def get_conversation(other_user_id):
    """Return the full conversation between the current user and another user."""
    user_id = int(get_jwt_identity())
    me = get_user_by_id(user_id)
    other = get_user_by_id(other_user_id)
    if not me or not other:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    if 'coach' not in {me['role'], other['role']}:
        return jsonify({'success': False, 'message': 'Invalid conversation pair'}), 400

    limit = min(int(request.args.get('limit', 200)), 500)
    msgs = list_conversation(user_id, other_user_id, limit=limit)
    result = []
    for m in msgs:
        sender = get_user_by_id(m['sender_id'])
        d = message_to_public(m, sender)
        d['isSender'] = m['sender_id'] == user_id
        result.append(d)

    return jsonify({
        'success': True,
        'messages': result,
        'otherUser': {'id': other['id'], 'name': other['name'], 'role': other['role']},
    })


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
