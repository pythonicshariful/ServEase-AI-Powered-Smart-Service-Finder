"""
ServEase – Config Classes
Environment-based configuration with dev / prod / test profiles.
"""
import os
import secrets

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration – shared across all environments."""
    # Security
    SECRET_KEY: str = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    WTF_CSRF_ENABLED: bool = True

    # Database
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(basedir, 'instance', 'instantfix.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # File uploads
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024          # 16 MB
    UPLOAD_FOLDER: str = os.path.join(basedir, 'static', 'uploads')
    ALLOWED_EXTENSIONS: set = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # AI
    GEMINI_API_KEY: str = os.environ.get('GEMINI_API_KEY', '')
    GEMINI_MODEL: str = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')

    # Cache (SimpleCache for dev, Redis for prod)
    CACHE_TYPE: str = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT: int = 300  # 5 minutes

    # Rate limiting
    RATELIMIT_STORAGE_URL: str = 'memory://'
    RATELIMIT_DEFAULT: str = '200 per day;50 per hour'

    # Email (flask-mail)
    MAIL_SERVER: str = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT: int = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS: bool = True
    MAIL_USERNAME: str = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD: str = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER: str = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@servease.app')


class DevelopmentConfig(Config):
    DEBUG: bool = True
    TESTING: bool = False


class TestingConfig(Config):
    DEBUG: bool = True
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED: bool = False
    MAIL_SUPPRESS_SEND: bool = True


class ProductionConfig(Config):
    DEBUG: bool = False
    TESTING: bool = False
    CACHE_TYPE: str = os.environ.get('CACHE_TYPE', 'SimpleCache')


# Map string names to config objects
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}