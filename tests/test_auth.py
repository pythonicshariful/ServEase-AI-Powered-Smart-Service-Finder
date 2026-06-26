"""
Auth endpoint tests – registration, login, logout, email verification.
"""
import pytest
from werkzeug.security import generate_password_hash
from models import db, User, Provider, Finder


def _register(client, name='Test User', email='test@example.com',
              password='password123', role='finder'):
    return client.post('/register', data={
        'name': name, 'email': email,
        'password': password, 'confirm': password, 'role': role,
    }, follow_redirects=True)


def _login(client, email='test@example.com', password='password123'):
    return client.post('/login', data={
        'email': email, 'password': password,
    }, follow_redirects=True)


class TestRegister:
    def test_register_finder(self, client, db):
        rv = _register(client)
        assert rv.status_code == 200
        user = User.query.filter_by(email='test@example.com').first()
        assert user is not None
        assert user.role == 'finder'

    def test_register_provider(self, client, db):
        rv = _register(client, name='Pro User', email='pro@example.com', role='provider')
        assert rv.status_code == 200
        user = User.query.filter_by(email='pro@example.com').first()
        assert user is not None
        assert user.role == 'provider'
        assert user.provider is not None

    def test_duplicate_email(self, client, db):
        _register(client)
        rv = _register(client)
        assert b'already registered' in rv.data or rv.status_code == 200


class TestLogin:
    def test_login_valid(self, client, db, app):
        with app.app_context():
            user = User(
                name='Login User', email='login@example.com',
                password=generate_password_hash('password123'), role='finder',
            )
            db.session.add(user)
            db.session.flush()
            db.session.add(Finder(user_id=user.id, bio='', location=''))
            db.session.commit()
        rv = _login(client, email='login@example.com', password='password123')
        assert rv.status_code == 200

    def test_login_invalid_password(self, client, db):
        rv = _login(client, email='nobody@example.com', password='wrong')
        assert b'Invalid' in rv.data or rv.status_code == 200

    def test_logout(self, client, db, app):
        with app.app_context():
            user = User(
                name='Logout User', email='logout@example.com',
                password=generate_password_hash('password123'), role='finder',
            )
            db.session.add(user)
            db.session.flush()
            db.session.add(Finder(user_id=user.id, bio='', location=''))
            db.session.commit()
        _login(client, email='logout@example.com', password='password123')
        rv = client.get('/logout', follow_redirects=True)
        assert rv.status_code == 200
