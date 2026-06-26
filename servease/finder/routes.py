"""Finder blueprint – dashboard, posts, matches, job workflow, reviews."""
from __future__ import annotations

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app)
from flask_login import login_required, current_user
from sqlalchemy.orm import selectinload

from models import (db, Provider, ProviderSkill, ServicePost, Finder,
                    JobApplication, Review, Notification)
from forms import PostForm, FinderProfileForm, ReviewForm
from servease.ai.matching import gemini_match_providers
from servease import cache

finder_bp = Blueprint('finder', __name__)


def _gemini():
    key = current_app.config.get('GEMINI_API_KEY', '')
    if not key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        return genai.GenerativeModel(current_app.config.get('GEMINI_MODEL', 'gemini-1.5-flash'))
    except Exception:
        return None


# ── Dashboard ────────────────────────────────────────────────────────────────

@finder_bp.route('/')
@login_required
def dashboard():
    if current_user.role != 'finder':
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    posts = (
        db.session.execute(
            db.select(ServicePost)
            .where(ServicePost.finder_id == current_user.id)
            .order_by(ServicePost.created_at.desc())
        ).scalars().all()
    )
    return render_template('finder_dashboard.html', posts=posts)


# ── Finder profile ────────────────────────────────────────────────────────────

@finder_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.role != 'finder':
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    finder = current_user.finder
    if not finder:
        finder = Finder(user_id=current_user.id, bio='', location='')
        db.session.add(finder)
        db.session.commit()
    form = FinderProfileForm()
    if form.validate_on_submit():
        finder.bio = form.bio.data
        finder.location = form.location.data
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('finder.dashboard'))
    form.bio.data = finder.bio
    form.location.data = finder.location
    return render_template('finder_profile.html', finder=finder, form=form)


# ── Create post ───────────────────────────────────────────────────────────────

@finder_bp.route('/create-post', methods=['GET', 'POST'])
@login_required
def create_post():
    if current_user.role != 'finder':
        flash('Only finders can create posts.', 'danger')
        return redirect(url_for('core.dashboard'))
    form = PostForm()
    if form.validate_on_submit():
        post = ServicePost(
            finder_id=current_user.id,
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            location=(form.location.data or '').strip(),
            budget_min=form.budget_min.data or 0,
            budget_max=form.budget_max.data or 0,
        )
        db.session.add(post)
        db.session.commit()
        flash('Post created! AI is finding your best matches...', 'success')
        return redirect(url_for('finder.view_matches', post_id=post.id))
    return render_template('create_post.html', form=form)


# ── View / edit individual post ───────────────────────────────────────────────

@finder_bp.route('/post/<int:post_id>')
@login_required
def view_post(post_id: int):
    post = db.session.get(ServicePost, post_id)
    if not post:
        flash('Post not found.', 'danger')
        return redirect(url_for('finder.dashboard'))
    applications = (
        db.session.execute(
            db.select(JobApplication)
            .where(JobApplication.post_id == post_id)
            .options(selectinload(JobApplication.provider))
        ).scalars().all()
        if current_user.role == 'finder' and post.finder_id == current_user.id
        else []
    )
    already_applied = False
    if current_user.role == 'provider':
        already_applied = bool(
            db.session.execute(
                db.select(JobApplication).where(
                    JobApplication.post_id == post_id,
                    JobApplication.provider_id == current_user.provider.id,
                )
            ).scalar_one_or_none()
        )
    return render_template('view_post.html', post=post,
                           applications=applications,
                           already_applied=already_applied)


# ── AI matches ────────────────────────────────────────────────────────────────

@finder_bp.route('/matches/<int:post_id>')
@login_required
def view_matches(post_id: int):
    post = db.session.get(ServicePost, post_id)
    if not post:
        flash('Post not found.', 'danger')
        return redirect(url_for('finder.dashboard'))
    if current_user.role != 'finder' or post.finder_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))

    # Eager-load skills to prevent N+1
    providers = (
        db.session.execute(
            db.select(Provider)
            .options(selectinload(Provider.skills))
            .limit(50)
        ).scalars().all()
    )
    scored = gemini_match_providers(post, providers, _gemini())
    return render_template('view_matches.html', post=post,
                           matches=[s[1] for s in scored[:10]],
                           scored=scored[:10])


# ── Job Application Workflow ──────────────────────────────────────────────────

@finder_bp.route('/application/<int:app_id>/accept', methods=['POST'])
@login_required
def accept_application(app_id: int):
    application = db.session.get(JobApplication, app_id)
    if not application:
        flash('Application not found.', 'danger')
        return redirect(url_for('finder.dashboard'))
    post = db.session.get(ServicePost, application.post_id)
    if post.finder_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))

    application.status = 'accepted'
    post.status = 'in_progress'
    post.accepted_provider_id = application.provider_id

    # Reject all other applications
    other_apps = db.session.execute(
        db.select(JobApplication).where(
            JobApplication.post_id == post.id,
            JobApplication.id != app_id,
        )
    ).scalars().all()
    for oa in other_apps:
        oa.status = 'rejected'
        db.session.add(Notification(
            user_id=oa.provider.user_id,
            message=f"Your application for '{post.title}' was not selected.",
            notif_type='application',
        ))

    db.session.add(Notification(
        user_id=application.provider.user_id,
        message=f"Congratulations! You were accepted for '{post.title}'.",
        notif_type='application',
    ))
    db.session.commit()
    flash('Provider accepted. Job is now in progress!', 'success')
    return redirect(url_for('finder.view_post', post_id=post.id))


@finder_bp.route('/application/<int:app_id>/reject', methods=['POST'])
@login_required
def reject_application(app_id: int):
    application = db.session.get(JobApplication, app_id)
    if not application:
        flash('Not found.', 'danger')
        return redirect(url_for('finder.dashboard'))
    post = db.session.get(ServicePost, application.post_id)
    if post.finder_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    application.status = 'rejected'
    db.session.add(Notification(
        user_id=application.provider.user_id,
        message=f"Your application for '{post.title}' was not selected.",
        notif_type='application',
    ))
    db.session.commit()
    flash('Application rejected.', 'info')
    return redirect(url_for('finder.view_post', post_id=post.id))


@finder_bp.route('/post/<int:post_id>/complete', methods=['POST'])
@login_required
def mark_complete(post_id: int):
    post = db.session.get(ServicePost, post_id)
    if not post or post.finder_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    post.status = 'completed'
    db.session.commit()
    flash('Job marked as completed! Please leave a review.', 'success')
    return redirect(url_for('finder.leave_review', post_id=post_id))


# ── Review & Rating ───────────────────────────────────────────────────────────

@finder_bp.route('/post/<int:post_id>/review', methods=['GET', 'POST'])
@login_required
def leave_review(post_id: int):
    if current_user.role != 'finder':
        flash('Access denied.', 'danger')
        return redirect(url_for('core.dashboard'))
    post = db.session.get(ServicePost, post_id)
    if not post or post.finder_id != current_user.id or post.status != 'completed':
        flash('Cannot leave a review for this post.', 'warning')
        return redirect(url_for('finder.dashboard'))

    existing_review = db.session.execute(
        db.select(Review).where(Review.post_id == post_id, Review.finder_id == current_user.id)
    ).scalar_one_or_none()
    if existing_review:
        flash('You have already reviewed this job.', 'info')
        return redirect(url_for('finder.dashboard'))

    form = ReviewForm()
    if form.validate_on_submit():
        prov_id = post.accepted_provider_id
        if not prov_id:
            flash('No provider to review.', 'warning')
            return redirect(url_for('finder.dashboard'))
        review = Review(
            provider_id=prov_id,
            finder_id=current_user.id,
            post_id=post_id,
            rating=form.rating.data,
            comment=form.comment.data,
        )
        db.session.add(review)

        # Recalculate provider rating
        prov = db.session.get(Provider, prov_id)
        all_ratings = db.session.execute(
            db.select(Review.rating).where(Review.provider_id == prov_id)
        ).scalars().all()
        new_rating = sum(all_ratings + [form.rating.data]) / (len(all_ratings) + 1)
        prov.rating = round(new_rating, 1)

        db.session.add(Notification(
            user_id=prov.user_id,
            message=f"You received a {form.rating.data}★ review from {current_user.name}.",
            notif_type='review',
        ))
        db.session.commit()
        flash('Review submitted! Thank you.', 'success')
        return redirect(url_for('finder.dashboard'))

    return render_template('leave_review.html', form=form, post=post)
