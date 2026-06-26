"""Messages blueprint – in-app messaging between finders and providers."""
from __future__ import annotations

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app)
from flask_login import login_required, current_user
from sqlalchemy.orm import selectinload

from models import db, User, Message, Conversation, Notification, ServicePost
from forms import MessageForm

messages_bp = Blueprint('messages', __name__)


# ── Inbox ─────────────────────────────────────────────────────────────────────

@messages_bp.route('/')
@login_required
def inbox():
    conversations = (
        db.session.execute(
            db.select(Conversation)
            .where(
                (Conversation.finder_id == current_user.id) |
                (Conversation.provider_user_id == current_user.id)
            )
            .order_by(Conversation.updated_at.desc())
        ).scalars().all()
    )
    # Unread count per conversation
    unread_map = {}
    for conv in conversations:
        count = db.session.execute(
            db.select(db.func.count(Message.id)).where(
                Message.conversation_id == conv.id,
                Message.recipient_id == current_user.id,
                Message.read == False,
            )
        ).scalar()
        unread_map[conv.id] = count or 0
    return render_template('messages/inbox.html', conversations=conversations,
                           unread_map=unread_map)


# ── Start a new conversation ──────────────────────────────────────────────────

@messages_bp.route('/start/<int:other_user_id>', methods=['GET', 'POST'])
@login_required
def start_conversation(other_user_id: int):
    other = db.session.get(User, other_user_id)
    if not other or other.id == current_user.id:
        flash('Invalid user.', 'danger')
        return redirect(url_for('messages.inbox'))

    # Determine finder / provider
    if current_user.role == 'finder' and other.role == 'provider':
        finder_id = current_user.id
        provider_user_id = other.id
    elif current_user.role == 'provider' and other.role == 'finder':
        finder_id = other.id
        provider_user_id = current_user.id
    else:
        flash('Conversations are between finders and providers only.', 'warning')
        return redirect(url_for('core.view_profile', user_id=other_user_id))

    # Find or create conversation
    conv = db.session.execute(
        db.select(Conversation).where(
            Conversation.finder_id == finder_id,
            Conversation.provider_user_id == provider_user_id,
        )
    ).scalar_one_or_none()
    if not conv:
        conv = Conversation(finder_id=finder_id, provider_user_id=provider_user_id)
        db.session.add(conv)
        db.session.commit()
    return redirect(url_for('messages.conversation', conv_id=conv.id))


# ── Conversation view / send ──────────────────────────────────────────────────

@messages_bp.route('/<int:conv_id>', methods=['GET', 'POST'])
@login_required
def conversation(conv_id: int):
    conv = db.session.get(Conversation, conv_id)
    if not conv or (
        current_user.id != conv.finder_id and
        current_user.id != conv.provider_user_id
    ):
        flash('Access denied.', 'danger')
        return redirect(url_for('messages.inbox'))

    form = MessageForm()
    if form.validate_on_submit():
        other_id = (
            conv.provider_user_id if current_user.id == conv.finder_id
            else conv.finder_id
        )
        msg = Message(
            conversation_id=conv.id,
            sender_id=current_user.id,
            recipient_id=other_id,
            content=form.content.data.strip(),
        )
        db.session.add(msg)
        from datetime import datetime
        conv.updated_at = datetime.utcnow()

        # SSE notification for recipient
        db.session.add(Notification(
            user_id=other_id,
            message=f"New message from {current_user.name}",
            notif_type='message',
        ))
        db.session.commit()
        return redirect(url_for('messages.conversation', conv_id=conv_id))

    # Mark messages as read
    db.session.execute(
        db.update(Message).where(
            Message.conversation_id == conv_id,
            Message.recipient_id == current_user.id,
            Message.read == False,
        ).values(read=True)
    )
    db.session.commit()

    messages_list = (
        db.session.execute(
            db.select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
        ).scalars().all()
    )
    other_user = db.session.get(
        User,
        conv.provider_user_id if current_user.id == conv.finder_id else conv.finder_id
    )
    return render_template('messages/conversation.html',
                           conv=conv, messages=messages_list,
                           other_user=other_user, form=form)
