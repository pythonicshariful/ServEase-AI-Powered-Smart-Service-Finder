from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # store hashed
    role = db.Column(db.String(20), nullable=False)  # 'provider' or 'finder'
    profile_image = db.Column(db.String(200))  # Path to profile image
    cover_image = db.Column(db.String(200))  # Path to cover image
    tagline = db.Column(db.String(200))  # Professional tagline
    location = db.Column(db.String(200))  # User-level location (optional)
    email_notifications = db.Column(db.Boolean, default=True)
    phone = db.Column(db.String(20))  # Contact phone number
    website = db.Column(db.String(200))  # Personal/Business website
    social_links = db.Column(db.Text)  # JSON string for social media links
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    provider = db.relationship('Provider', backref='user', uselist=False)
    finder = db.relationship('Finder', backref='user', uselist=False)
    posts = db.relationship('ServicePost', backref='finder', lazy=True)

class Provider(db.Model):
    __tablename__ = 'providers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150))
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    verified = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Float, default=0.0)
    profile_visible = db.Column(db.Boolean, default=True)
    business_name = db.Column(db.String(200))
    business_hours = db.Column(db.Text)  # JSON string for business hours
    experience_years = db.Column(db.Integer)
    certificates = db.Column(db.Text)  # JSON string for certificates/qualifications
    service_areas = db.Column(db.Text)  # JSON string for service coverage areas
    languages = db.Column(db.Text)  # JSON string for languages spoken
    hourly_rate = db.Column(db.Float)  # Hourly rate in BDT
    portfolio_images = db.Column(db.Text)  # JSON string for portfolio image paths
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    skills = db.relationship('ProviderSkill', backref='provider', lazy=True)

class Finder(db.Model):
    __tablename__ = 'finders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bio = db.Column(db.Text)
    location = db.Column(db.String(200))
    preferences = db.Column(db.Text)  # JSON string for service preferences
    favorite_providers = db.Column(db.Text)  # JSON string for favorite provider IDs
    company_name = db.Column(db.String(200))  # For business clients
    company_size = db.Column(db.String(50))  # Company size range
    industry = db.Column(db.String(100))  # Industry sector
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProviderSkill(db.Model):
    __tablename__ = 'provider_skills'
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'), nullable=False)
    skill = db.Column(db.String(120), nullable=False)

class ServicePost(db.Model):
    __tablename__ = 'service_posts'
    id = db.Column(db.Integer, primary_key=True)
    finder_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    budget_min = db.Column(db.Integer)
    budget_max = db.Column(db.Integer)
    status = db.Column(db.String(20), default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # matches relationship will be computed on the fly for MVP
