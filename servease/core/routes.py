"""Core blueprint – home, dashboard, profile, settings, delete account, view_profile, SSE."""
from __future__ import annotations

import json
import os
import time

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, Response, stream_with_context)
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.orm import selectinload

from models import db, User, Provider, ProviderSkill, ServicePost, Finder, Notification
from forms import ProviderProfileForm, FinderProfileForm
from servease.utils import is_valid_image, profile_completion

core_bp = Blueprint('core', __name__)


# ── File upload helper ────────────────────────────────────────────────────────

def _save_image(file, folder: str) -> str | None:
    cfg = current_app.config
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in cfg['ALLOWED_EXTENSIONS']:
        return None
    if not is_valid_image(file.stream):
        return None
    filename = secure_filename(f"{current_user.id}_{int(time.time())}_{file.filename}")
    path = os.path.join(cfg['UPLOAD_FOLDER'], folder, filename)
    file.save(path)
    return f'uploads/{folder}/{filename}'


# ── Routes ────────────────────────────────────────────────────────────────────

@core_bp.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('core.dashboard'))
    return render_template('home.html')


@core_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == 'provider':
        return redirect(url_for('provider.best_matches'))
    return redirect(url_for('finder.dashboard'))


# ── Public profile view ───────────────────────────────────────────────────────

@core_bp.route('/user/<int:user_id>')
def view_profile(user_id: int):
    user = db.session.get(User, user_id) or db.session.execute(
        db.select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    if user is None:
        flash('User not found.', 'danger')
        return redirect(url_for('core.home'))

    try:
        social = json.loads(user.social_links) if user.social_links else {}
    except Exception:
        social = {}

    if user.role == 'provider':
        prov = db.session.get(Provider, user.provider.id) if user.provider else None
        skills = (
            db.session.execute(
                db.select(ProviderSkill)
                .where(ProviderSkill.provider_id == prov.id)
            ).scalars().all()
            if prov else []
        )
        try:
            portfolio_images = json.loads(prov.portfolio_images) if prov and prov.portfolio_images else []
        except Exception:
            portfolio_images = []
        completion = profile_completion(user)
        return render_template('view_profile.html', user=user, skills=skills,
                               social=social, portfolio_images=portfolio_images,
                               completion=completion)
    else:
        posts = []
        if current_user.is_authenticated and current_user.id == user.id:
            posts = (
                db.session.execute(
                    db.select(ServicePost)
                    .where(ServicePost.finder_id == user.id)
                    .order_by(ServicePost.created_at.desc())
                    .limit(5)
                ).scalars().all()
            )
        return render_template('view_profile.html', user=user, posts=posts,
                               social=social, portfolio_images=[],
                               completion=profile_completion(user))


# ── Edit profile (professional_profile.html) ──────────────────────────────────

@core_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    if current_user.role == 'provider':
        form = ProviderProfileForm()
    else:
        form = FinderProfileForm()

    if form.validate_on_submit():
        # Handle image uploads
        if form.profile_image.data:
            path = _save_image(form.profile_image.data, 'profiles')
            if path:
                if current_user.profile_image:
                    try:
                        os.remove(os.path.join(current_app.root_path, 'static', current_user.profile_image))
                    except OSError:
                        pass
                current_user.profile_image = path

        if form.cover_image.data:
            path = _save_image(form.cover_image.data, 'covers')
            if path:
                if current_user.cover_image:
                    try:
                        os.remove(os.path.join(current_app.root_path, 'static', current_user.cover_image))
                    except OSError:
                        pass
                current_user.cover_image = path

        current_user.name = form.name.data
        current_user.tagline = form.tagline.data
        current_user.phone = form.phone.data
        current_user.website = form.website.data
        current_user.location = form.location.data
        current_user.social_links = json.dumps({
            'facebook': form.facebook.data,
            'twitter': form.twitter.data,
            'linkedin': form.linkedin.data,
        })

        if current_user.role == 'provider':
            prov = current_user.provider
            prov.title = form.title.data
            prov.description = form.description.data
            prov.business_name = form.business_name.data
            prov.experience_years = form.experience_years.data
            prov.hourly_rate = form.hourly_rate.data
            prov.location = form.location.data
            if form.portfolio_images.data:
                imgs = []
                try:
                    existing = json.loads(prov.portfolio_images) if prov.portfolio_images else []
                    for old in existing:
                        try:
                            os.remove(os.path.join(current_app.root_path, 'static', old))
                        except OSError:
                            pass
                except Exception:
                    pass
                for img in form.portfolio_images.data:
                    if img:
                        p = _save_image(img, 'portfolio')
                        if p:
                            imgs.append(p)
                prov.portfolio_images = json.dumps(imgs)
        else:
            finder = current_user.finder
            finder.bio = form.bio.data
            finder.company_name = form.company_name.data
            finder.company_size = form.company_size.data
            finder.industry = form.industry.data
            finder.location = form.location.data

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('core.user_profile'))

    # Pre-fill form
    form.name.data = current_user.name
    form.tagline.data = current_user.tagline
    form.phone.data = current_user.phone
    form.website.data = current_user.website
    form.location.data = current_user.location
    if current_user.social_links:
        try:
            sl = json.loads(current_user.social_links)
            form.facebook.data = sl.get('facebook', '')
            form.twitter.data = sl.get('twitter', '')
            form.linkedin.data = sl.get('linkedin', '')
        except Exception:
            pass

    portfolio_images = []
    if current_user.role == 'provider':
        prov = current_user.provider
        form.title.data = prov.title
        form.description.data = prov.description
        form.business_name.data = prov.business_name
        form.experience_years.data = prov.experience_years
        form.hourly_rate.data = prov.hourly_rate
        skills = prov.skills
        try:
            portfolio_images = json.loads(prov.portfolio_images) if prov.portfolio_images else []
        except Exception:
            pass
    else:
        finder = current_user.finder
        form.bio.data = finder.bio
        form.company_name.data = finder.company_name
        form.company_size.data = finder.company_size
        form.industry.data = finder.industry
        posts = ServicePost.query.filter_by(finder_id=current_user.id)\
                                 .order_by(ServicePost.created_at.desc()).limit(5).all()
        skills = []

    return render_template(
        'professional_profile.html',
        form=form, skills=skills if current_user.role == 'provider' else [],
        posts=posts if current_user.role == 'finder' else None,
        user=current_user,
        social=json.loads(current_user.social_links) if current_user.social_links else {},
        portfolio_images=portfolio_images,
        completion=profile_completion(current_user),
    )


# ── Settings ──────────────────────────────────────────────────────────────────

@core_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    from forms import SettingsForm
    form = SettingsForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        if form.current_password.data:
            if check_password_hash(current_user.password, form.current_password.data):
                if form.new_password.data:
                    current_user.password = generate_password_hash(form.new_password.data)
                    flash('Password updated.', 'success')
            else:
                flash('Current password is incorrect.', 'danger')
                return render_template('settings.html', form=form)
        current_user.email_notifications = form.email_notifications.data
        if current_user.role == 'provider':
            current_user.provider.profile_visible = form.profile_visible.data
        db.session.commit()
        flash('Settings saved.', 'success')
        return redirect(url_for('core.settings'))

    form.name.data = current_user.name
    form.email.data = current_user.email
    form.email_notifications.data = current_user.email_notifications
    if current_user.role == 'provider':
        form.profile_visible.data = current_user.provider.profile_visible
    return render_template('settings.html', form=form)


# ── Delete account ────────────────────────────────────────────────────────────

@core_bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    from flask_login import logout_user
    try:
        if current_user.role == 'provider':
            ProviderSkill.query.filter_by(provider_id=current_user.provider.id).delete()
            db.session.delete(current_user.provider)
        else:
            ServicePost.query.filter_by(finder_id=current_user.id).delete()
            if current_user.finder:
                db.session.delete(current_user.finder)
        if current_user.profile_image:
            try:
                os.remove(os.path.join(current_app.root_path, 'static', current_user.profile_image))
            except OSError:
                pass
        user_id = current_user.id
        logout_user()
        db.session.execute(db.delete(User).where(User.id == user_id))
        db.session.commit()
        flash('Your account has been deleted.', 'info')
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Delete account error: {exc}")
        flash('Error deleting account. Please try again.', 'danger')
    return redirect(url_for('core.home'))


# ── SSE – Notification stream ─────────────────────────────────────────────────

@core_bp.route('/notifications/stream')
@login_required
def notification_stream():
    """Server-Sent Events endpoint for real-time notifications."""
    user_id = current_user.id

    def generate():
        import time
        last_id = 0
        while True:
            notifications = (
                db.session.execute(
                    db.select(Notification)
                    .where(Notification.user_id == user_id, Notification.id > last_id, ~Notification.read)
                    .order_by(Notification.created_at.asc())
                ).scalars().all()
            )
            for n in notifications:
                last_id = n.id
                yield f"data: {json.dumps({'message': n.message, 'type': n.notif_type, 'id': n.id})}\n\n"
            time.sleep(5)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


@core_bp.route('/notifications/read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id: int):
    n = db.session.get(Notification, notif_id)
    if n and n.user_id == current_user.id:
        n.read = True
        db.session.commit()
    return ('', 204)
