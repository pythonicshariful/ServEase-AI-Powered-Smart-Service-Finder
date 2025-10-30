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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    provider = db.relationship('Provider', backref='user', uselist=False)
    posts = db.relationship('ServicePost', backref='finder', lazy=True)

class Provider(db.Model):
    __tablename__ = 'providers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150))
    description = db.Column(db.Text)
    verified = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    skills = db.relationship('ProviderSkill', backref='provider', lazy=True)

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
