"""Provider blueprint – dashboard, skills, best matches, post applications."""
from __future__ import annotations

import json
import os
import time

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app)
from flask_login import login_required, current_user
from sqlalchemy.orm import selectinload, joinedload
from werkzeug.utils import secure_filename

from models import db, Provider, ProviderSkill, ServicePost, JobApplication, Notification
from forms import ProviderProfileForm, SkillForm
from servease.ai.matching import gemini_match_posts
from servease import cache

provider_bp = Blueprint('provider', __name__)

# Lazy gemini model accessor
def _gemini():
    from flask import current_app
    key = current_app.config.get('GEMINI_API_KEY', '')
    if not key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        return genai.GenerativeModel(current_app.config.get('GEMINI_MODEL', 'gemini-1.5-flash'))
    except Exception:
        return None


@provider_bp.route('/')
@login_required
def dashboard():
    if current_user.role != 'provider':
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    prov = current_user.provider
    skills = (
        db.session.execute(
            db.select(ProviderSkill).where(ProviderSkill.provider_id == prov.id)
        ).scalars().all()
    )
    form = ProviderProfileForm()
    form.title.data = prov.title
    form.description.data = prov.description
    form.location.data = prov.location
    return render_template('provider_dashboard.html', provider=prov, skills=skills, form=form)


@provider_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.role != 'provider':
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    form = ProviderProfileForm()
    prov = current_user.provider
    if form.validate_on_submit():
        prov.title = form.title.data
        prov.description = form.description.data
        prov.location = form.location.data
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('provider.dashboard'))
    form.title.data = prov.title
    form.description.data = prov.description
    form.location.data = prov.location
    return render_template('provider_dashboard.html', provider=prov, skills=prov.skills, form=form)


@provider_bp.route('/add-skill', methods=['GET', 'POST'])
@login_required
def add_skill():
    if current_user.role != 'provider':
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    form = SkillForm()
    if form.validate_on_submit():
        prov = current_user.provider
        db.session.add(ProviderSkill(
            provider_id=prov.id,
            skill=form.skill.data.strip(),
            proficiency=form.proficiency.data,
            years_experience=form.years_experience.data,
        ))
        db.session.commit()
        cache.delete_memoized(gemini_match_posts)   # invalidate cached matches
        flash('Skill added.', 'success')
        return redirect(url_for('provider.dashboard'))
    return render_template('add_skill.html', form=form)


@provider_bp.route('/delete-skill/<int:skill_id>')
@login_required
def delete_skill(skill_id: int):
    if current_user.role != 'provider':
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    skill = db.session.get(ProviderSkill, skill_id)
    if not skill or skill.provider_id != current_user.provider.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    db.session.delete(skill)
    db.session.commit()
    flash('Skill removed.', 'success')
    return redirect(url_for('core.user_profile'))


@provider_bp.route('/best-matches')
@login_required
@cache.cached(timeout=300, key_prefix=lambda: f'best_matches_{current_user.id}')
def best_matches():
    if current_user.role != 'provider':
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    prov = current_user.provider

    # Paginate: fetch up to 50 open posts with eager-loaded relationships
    posts = (
        db.session.execute(
            db.select(ServicePost)
            .where(ServicePost.status == 'open')
            .order_by(ServicePost.created_at.desc())
            .limit(50)
        ).scalars().all()
    )
    scored = gemini_match_posts(prov, posts, _gemini())
    return render_template('provider_best_matches.html',
                           provider=prov, matches=[s[1] for s in scored[:10]],
                           scored=scored[:10])


# ── Job Application: provider applies to a post ───────────────────────────────

@provider_bp.route('/apply/<int:post_id>', methods=['POST'])
@login_required
def apply_to_post(post_id: int):
    if current_user.role != 'provider':
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    post = db.session.get(ServicePost, post_id)
    if not post or post.status != 'open':
        flash('Job post not available.', 'warning')
        return redirect(url_for('provider.best_matches'))

    existing = db.session.execute(
        db.select(JobApplication).where(
            JobApplication.post_id == post_id,
            JobApplication.provider_id == current_user.provider.id,
        )
    ).scalar_one_or_none()
    if existing:
        flash('You have already applied to this post.', 'info')
        return redirect(url_for('core.view_post', post_id=post_id))

    app_ = JobApplication(
        post_id=post_id,
        provider_id=current_user.provider.id,
        status='pending',
    )
    db.session.add(app_)
    # Notify the finder
    db.session.add(Notification(
        user_id=post.finder_id,
        message=f"{current_user.name} applied to your job: {post.title}",
        notif_type='application',
    ))
    db.session.commit()
    flash('Application submitted! The finder will review your profile.', 'success')
    return redirect(url_for('core.view_post', post_id=post_id))
