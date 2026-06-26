"""
ServEase – Database Models
"""
from __future__ import annotations

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id                  = db.Column(db.Integer, primary_key=True)
    name                = db.Column(db.String(120))
    email               = db.Column(db.String(150), unique=True, nullable=False)
    password            = db.Column(db.String(200), nullable=False)
    role                = db.Column(db.String(20), nullable=False)   # 'provider' | 'finder'
    email_verified      = db.Column(db.Boolean, default=False)
    profile_image       = db.Column(db.String(200))
    cover_image         = db.Column(db.String(200))
    tagline             = db.Column(db.String(200))
    location            = db.Column(db.String(200))
    email_notifications = db.Column(db.Boolean, default=True)
    phone               = db.Column(db.String(20))
    website             = db.Column(db.String(200))
    social_links        = db.Column(db.Text)   # JSON
    is_suspended        = db.Column(db.Boolean, default=False)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_active(self):
        return not self.is_suspended

    provider      = db.relationship('Provider', back_populates='user', uselist=False)
    finder        = db.relationship('Finder',   back_populates='user', uselist=False)
    posts         = db.relationship('ServicePost', backref='finder',   lazy='dynamic')
    notifications = db.relationship('Notification', backref='user',    lazy='dynamic')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id',    backref='sender',    lazy='dynamic')
    recv_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy='dynamic')


class Provider(db.Model):
    __tablename__ = 'providers'
    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title             = db.Column(db.String(150))
    description       = db.Column(db.Text)
    location          = db.Column(db.String(200))
    verified          = db.Column(db.Boolean, default=False)
    rating            = db.Column(db.Float, default=0.0)
    profile_visible   = db.Column(db.Boolean, default=True)
    business_name     = db.Column(db.String(200))
    business_hours    = db.Column(db.Text)   # JSON
    experience_years  = db.Column(db.Integer)
    certificates      = db.Column(db.Text)   # JSON
    service_areas     = db.Column(db.Text)   # JSON
    languages         = db.Column(db.Text)   # JSON
    hourly_rate       = db.Column(db.Float)
    portfolio_images  = db.Column(db.Text)   # JSON
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    user              = db.relationship('User', back_populates='provider')
    skills            = db.relationship('ProviderSkill', backref='provider', lazy='select',
                                        cascade='all, delete-orphan')
    applications      = db.relationship('JobApplication', backref='provider', lazy='dynamic')
    reviews_received  = db.relationship('Review', backref='provider', lazy='dynamic')


class Finder(db.Model):
    __tablename__ = 'finders'
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bio              = db.Column(db.Text)
    location         = db.Column(db.String(200))
    preferences      = db.Column(db.Text)   # JSON
    favorite_providers = db.Column(db.Text) # JSON
    company_name     = db.Column(db.String(200))
    company_size     = db.Column(db.String(50))
    industry         = db.Column(db.String(100))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='finder')


class ProviderSkill(db.Model):
    __tablename__ = 'provider_skills'
    id              = db.Column(db.Integer, primary_key=True)
    provider_id     = db.Column(db.Integer, db.ForeignKey('providers.id'), nullable=False)
    skill           = db.Column(db.String(120), nullable=False)
    proficiency     = db.Column(db.String(20))     # beginner | intermediate | expert
    years_experience = db.Column(db.Integer)


class ServicePost(db.Model):
    __tablename__ = 'service_posts'
    id                   = db.Column(db.Integer, primary_key=True)
    finder_id            = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title                = db.Column(db.String(200))
    description          = db.Column(db.Text)
    location             = db.Column(db.String(200))
    budget_min           = db.Column(db.Integer)
    budget_max           = db.Column(db.Integer)
    status               = db.Column(db.String(20), default='open')
    accepted_provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'), nullable=True)
    is_hidden            = db.Column(db.Boolean, default=False)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship('JobApplication', backref='post', lazy='dynamic',
                                   cascade='all, delete-orphan')
    reviews      = db.relationship('Review', backref='post', lazy='dynamic')


class JobApplication(db.Model):
    """Provider applies to a ServicePost."""
    __tablename__ = 'job_applications'
    id          = db.Column(db.Integer, primary_key=True)
    post_id     = db.Column(db.Integer, db.ForeignKey('service_posts.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'),     nullable=False)
    status      = db.Column(db.String(20), default='pending')  # pending | accepted | rejected
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('post_id', 'provider_id', name='uq_application'),)


class Review(db.Model):
    """Post-job review from finder to provider."""
    __tablename__ = 'reviews'
    id          = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'), nullable=False)
    finder_id   = db.Column(db.Integer, db.ForeignKey('users.id'),     nullable=False)
    post_id     = db.Column(db.Integer, db.ForeignKey('service_posts.id'), nullable=False)
    rating      = db.Column(db.Float, nullable=False)
    comment     = db.Column(db.Text)
    is_hidden   = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    """Real-time notification for SSE."""
    __tablename__ = 'notifications'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message     = db.Column(db.String(500), nullable=False)
    notif_type  = db.Column(db.String(30), default='info')   # info | application | review | message
    read        = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class Conversation(db.Model):
    """A messaging thread between one finder and one provider."""
    __tablename__ = 'conversations'
    id               = db.Column(db.Integer, primary_key=True)
    finder_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    provider_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow)

    finder_user   = db.relationship('User', foreign_keys=[finder_id])
    provider_user = db.relationship('User', foreign_keys=[provider_user_id])
    messages      = db.relationship('Message', backref='conversation', lazy='dynamic',
                                    order_by='Message.created_at', cascade='all, delete-orphan')

    __table_args__ = (db.UniqueConstraint('finder_id', 'provider_user_id', name='uq_conversation'),)


class Message(db.Model):
    """Single message within a Conversation."""
    __tablename__ = 'messages'
    id              = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    sender_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content         = db.Column(db.Text, nullable=False)
    read            = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


class SystemSettings(db.Model):
    """Global system configuration (e.g. maintenance mode)."""
    __tablename__ = 'system_settings'
    key         = db.Column(db.String(100), primary_key=True)
    value       = db.Column(db.Text)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Announcement(db.Model):
    """Global broadcasts to all users."""
    __tablename__ = 'announcements'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    message     = db.Column(db.Text, nullable=False)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
