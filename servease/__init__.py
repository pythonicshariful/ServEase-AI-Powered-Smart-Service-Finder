"""
Mistribhai – Application Factory
================================
Creates and configures the Flask app with all extensions and blueprints.
"""
from __future__ import annotations

import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_migrate import Migrate
from flask_mail import Mail
from flask_login import current_user
from flask import render_template, request

# ── Extension singletons (initialised without app) ───────────────────────────
from models import db              # SQLAlchemy instance lives in models.py
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
cache = Cache()
migrate = Migrate()
mail = Mail()


def create_app(config_name: str | None = None) -> Flask:
    """Application factory – creates and returns a fully configured Flask app."""
    from config import config as config_map
    from dotenv import load_dotenv
    load_dotenv()

    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
        static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'),
    )
    app.config.from_object(config_map[config_name])

    # ── Create upload dirs & instance dir ─────────────────────────────────────
    os.makedirs(app.instance_path, exist_ok=True)
    for sub in ('profiles', 'covers', 'portfolio'):
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], sub), exist_ok=True)

    # ── Init extensions ───────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'           # type: ignore[assignment]
    login_manager.login_message_category = 'info'

    # ── User loader ───────────────────────────────────────────────────────────
    from models import User

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id))

    # ── Template filters ──────────────────────────────────────────────────────
    from servease.utils import register_filters
    register_filters(app)

    # ── Register blueprints ───────────────────────────────────────────────────
    from servease.core.routes   import core_bp
    from servease.auth.routes   import auth_bp
    from servease.provider.routes import provider_bp
    from servease.finder.routes import finder_bp
    from servease.messages.routes import messages_bp
    from servease.admin.routes import admin_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(provider_bp, url_prefix='/provider')
    app.register_blueprint(finder_bp,   url_prefix='/finder')
    app.register_blueprint(messages_bp, url_prefix='/messages')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    @app.before_request
    def check_maintenance_mode():
        if request.path.startswith('/static/') or request.path.startswith('/admin'):
            return None
        
        from models import SystemSettings
        try:
            setting = db.session.get(SystemSettings, 'maintenance_mode')
            if setting and setting.value == 'True':
                if not current_user.is_authenticated or current_user.role != 'admin':
                    return render_template('maintenance.html'), 503
        except Exception:
            pass

    return app
