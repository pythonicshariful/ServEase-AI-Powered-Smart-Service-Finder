"""Auth blueprint – login, register, logout, email verification."""
from __future__ import annotations

import os
from datetime import datetime

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app)
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from models import db, User, Provider, Finder
from forms import RegisterForm, LoginForm
from servease import limiter

auth_bp = Blueprint('auth', __name__)


# ── Email verification helpers ────────────────────────────────────────────────

def _get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _send_verification_email(user: User) -> None:
    """Send verification email or print token in dev mode."""
    from flask_mail import Message as MailMessage
    from servease import mail

    token = _get_serializer().dumps(user.email, salt='email-confirm')
    verify_url = url_for('auth.verify_email', token=token, _external=True)

    mail_user = current_app.config.get('MAIL_USERNAME', '')
    if mail_user:
        try:
            msg = MailMessage(
                subject='Verify your Mistribhai email',
                recipients=[user.email],
                html=f"""
                <h2>Welcome to Mistribhai, {user.name}!</h2>
                <p>Click the link below to verify your email address:</p>
                <p><a href="{verify_url}" style="background:#7c3aed;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;">Verify Email</a></p>
                <p>This link expires in 24 hours.</p>
                """,
            )
            mail.send(msg)
            flash('A verification email has been sent. Please check your inbox.', 'info')
        except Exception as exc:
            current_app.logger.warning(f"Email send failed: {exc}")
            current_app.logger.info(f"[DEV] Verify URL: {verify_url}")
            flash('Account created! Email sending failed – check server logs for verify link.', 'warning')
    else:
        # Dev mode – print token to console
        current_app.logger.info(f"[DEV] Email verification URL for {user.email}: {verify_url}")
        flash(f'Account created! (Dev mode) Verify URL logged to console. You can log in now.', 'info')


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit('20 per hour')
def register():
    if current_user.is_authenticated:
        return redirect(url_for('core.dashboard'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))
        hashed = generate_password_hash(form.password.data)
        user = User(
            name=form.name.data,
            email=form.email.data,
            password=hashed,
            role=form.role.data,
            email_verified=False,
        )
        db.session.add(user)
        db.session.flush()          # get user.id before commit
        if user.role == 'provider':
            db.session.add(Provider(user_id=user.id, title='', description='', location=''))
        else:
            db.session.add(Finder(user_id=user.id, bio='', location=''))
        db.session.commit()
        _send_verification_email(user)
        return redirect(url_for('auth.login'))
    return render_template('register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('core.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('core.dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('core.home'))


@auth_bp.route('/verify/<token>')
def verify_email(token: str):
    try:
        email = _get_serializer().loads(token, salt='email-confirm', max_age=86400)
    except SignatureExpired:
        flash('Verification link has expired. Please register again.', 'danger')
        return redirect(url_for('auth.register'))
    except BadSignature:
        flash('Invalid verification link.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first_or_404()
    user.email_verified = True
    db.session.commit()
    flash('Email verified! You can now log in.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification')
@login_required
def resend_verification():
    if current_user.email_verified:
        flash('Your email is already verified.', 'info')
        return redirect(url_for('core.dashboard'))
    _send_verification_email(current_user)
    return redirect(url_for('core.dashboard'))
