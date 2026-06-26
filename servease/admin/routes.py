"""Admin Blueprint - System Headquarters"""
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from models import db, User, Provider, ServicePost, Review, SystemSettings, Announcement, Message

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    active_posts = ServicePost.query.filter_by(status='open', is_hidden=False).count()
    completed_posts = ServicePost.query.filter_by(status='completed').count()
    total_messages = Message.query.count()
    maintenance_setting = SystemSettings.query.get('maintenance_mode')
    maintenance_mode = maintenance_setting.value == 'True' if maintenance_setting else False

    return render_template('admin/dashboard.html', 
                           total_users=total_users, 
                           active_posts=active_posts,
                           completed_posts=completed_posts,
                           total_messages=total_messages,
                           maintenance_mode=maintenance_mode)

@admin_bp.route('/system/maintenance', methods=['POST'])
@login_required
@admin_required
def toggle_maintenance():
    setting = SystemSettings.query.get('maintenance_mode')
    if not setting:
        setting = SystemSettings(key='maintenance_mode', value='False')
        db.session.add(setting)
    
    # Toggle logic
    new_status = 'False' if setting.value == 'True' else 'True'
    setting.value = new_status
    db.session.commit()
    
    status_text = "ON" if new_status == 'True' else "OFF"
    flash(f'Maintenance mode turned {status_text}.', 'success' if new_status == 'True' else 'info')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    all_users = User.query.all()
    return render_template('admin/users.html', users=all_users)

@admin_bp.route('/users/<int:user_id>/suspend', methods=['POST'])
@login_required
@admin_required
def toggle_suspend(user_id):
    user = db.session.get(User, user_id)
    if user:
        if user.role == 'admin' and user.id == current_user.id:
            flash("You cannot suspend yourself.", "danger")
        else:
            user.is_suspended = not user.is_suspended
            db.session.commit()
            status = "suspended" if user.is_suspended else "unsuspended"
            flash(f"User {user.email} has been {status}.", "success")
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user:
        if user.role == 'admin' and user.id == current_user.id:
            flash("You cannot delete yourself.", "danger")
        else:
            # For a true full delete, we'd need to clean up dependencies, but let's just use SQLAlchemy cascades if set up, or manual delete.
            # Simplified for now.
            db.session.delete(user)
            db.session.commit()
            flash(f"User {user.email} has been permanently deleted.", "success")
    return redirect(url_for('admin.users'))

@admin_bp.route('/providers')
@login_required
@admin_required
def providers():
    all_providers = Provider.query.all()
    return render_template('admin/providers.html', providers=all_providers)

@admin_bp.route('/providers/<int:provider_id>/verify', methods=['POST'])
@login_required
@admin_required
def toggle_verify(provider_id):
    provider = db.session.get(Provider, provider_id)
    if provider:
        provider.verified = not provider.verified
        db.session.commit()
        status = "verified" if provider.verified else "unverified"
        flash(f"Provider {provider.user.email} is now {status}.", "success")
    return redirect(url_for('admin.providers'))

@admin_bp.route('/moderation')
@login_required
@admin_required
def moderation():
    posts = ServicePost.query.all()
    reviews = Review.query.all()
    return render_template('admin/moderation.html', posts=posts, reviews=reviews)

@admin_bp.route('/posts/<int:post_id>/toggle-visibility', methods=['POST'])
@login_required
@admin_required
def toggle_post_visibility(post_id):
    post = db.session.get(ServicePost, post_id)
    if post:
        post.is_hidden = not post.is_hidden
        db.session.commit()
        flash(f"Post '{post.title}' visibility toggled.", "success")
    return redirect(url_for('admin.moderation'))

@admin_bp.route('/reviews/<int:review_id>/toggle-visibility', methods=['POST'])
@login_required
@admin_required
def toggle_review_visibility(review_id):
    review = db.session.get(Review, review_id)
    if review:
        review.is_hidden = not review.is_hidden
        db.session.commit()
        flash("Review visibility toggled.", "success")
    return redirect(url_for('admin.moderation'))

@admin_bp.route('/broadcast', methods=['GET', 'POST'])
@login_required
@admin_required
def broadcast():
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        if title and message:
            announcement = Announcement(title=title, message=message, created_by=current_user.id)
            db.session.add(announcement)
            db.session.commit()
            flash("Announcement broadcasted successfully!", "success")
            return redirect(url_for('admin.broadcast'))
    
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('admin/broadcast.html', announcements=announcements)
