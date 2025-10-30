from app import app, db
from models import User, Provider
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()
    # create demo users (if not exists)
    if not User.query.filter_by(email='prov@example.com').first():
        u = User(name='Provider One', email='prov@example.com', password=generate_password_hash('1234'), role='provider')
        db.session.add(u); db.session.commit()
        p = Provider(user_id=u.id, title='Plumber', description='I fix pipes')
        db.session.add(p)
    if not User.query.filter_by(email='finder@example.com').first():
        f = User(name='Finder One', email='finder@example.com', password=generate_password_hash('1234'), role='finder')
        db.session.add(f)
    db.session.commit()
    print("DB initialized with demo users.")
