import pytest
from servease import create_app
from models import db, User, SystemSettings

from werkzeug.security import generate_password_hash

@pytest.fixture
def app():
    app = create_app('testing')
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_admin_access(client, app):
    with app.app_context():
        u = User(name='Admin', email='admin@test.com', password=generate_password_hash('pw'), role='admin')
        db.session.add(u)
        db.session.commit()
    
    # Login as admin
    client.post('/auth/login', data={'email': 'admin@test.com', 'password': 'pw'})
    
    # Access dashboard
    rv = client.get('/admin/dashboard', follow_redirects=True)
    assert rv.status_code == 200
    assert b'Headquarters Dashboard' in rv.data

def test_non_admin_forbidden(client, app):
    with app.app_context():
        u = User(name='User', email='user@test.com', password=generate_password_hash('pw'), role='finder')
        db.session.add(u)
        db.session.commit()
        
    client.post('/auth/login', data={'email': 'user@test.com', 'password': 'pw'})
    
    rv = client.get('/admin/dashboard')
    assert rv.status_code == 403

def test_maintenance_mode(client, app):
    with app.app_context():
        db.session.add(SystemSettings(key='maintenance_mode', value='True'))
        db.session.commit()
        
    # Unauthenticated user should get 503 maintenance page
    rv = client.get('/')
    assert rv.status_code == 503
    assert b"We'll be right back!" in rv.data
    
    # Admin should get 200
    with app.app_context():
        u = User(name='Admin', email='admin2@test.com', password=generate_password_hash('pw'), role='admin')
        db.session.add(u)
        db.session.commit()
    client.post('/auth/login', data={'email': 'admin2@test.com', 'password': 'pw'})

    
    rv = client.get('/')
    assert rv.status_code == 200
