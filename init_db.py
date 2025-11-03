from app import app, db
from models import User, Provider, Finder
from werkzeug.security import generate_password_hash

with app.app_context():
    # Create all tables if they don't exist
    db.create_all()
    
    # create demo users (if not exists)
    if not User.query.filter_by(email='prov@example.com').first():
        u = User(name='Provider One', email='prov@example.com', password=generate_password_hash('1234'), role='provider')
        db.session.add(u)
        db.session.commit()
        p = Provider(user_id=u.id, title='Professional Plumber', description='Experienced plumber specializing in residential and commercial plumbing repairs, installations, and maintenance.', location='Dhaka, Bangladesh')
        db.session.add(p)
    
    if not User.query.filter_by(email='finder@example.com').first():
        f = User(name='Finder One', email='finder@example.com', password=generate_password_hash('1234'), role='finder')
        db.session.add(f)
        db.session.commit()
        finder = Finder(user_id=f.id, bio='Looking for reliable service providers', location='Dhaka, Bangladesh')
        db.session.add(finder)
    
    db.session.commit()
    print("DB initialized with demo users.")
