"""
Model integrity tests.
"""
import pytest
from models import (db, User, Provider, Finder, ProviderSkill,
                    ServicePost, JobApplication, Review, Message, Conversation)
from werkzeug.security import generate_password_hash
from datetime import datetime


class TestModels:
    def test_create_user(self, app, db):
        with app.app_context():
            u = User(name='Test', email='model_test@ex.com',
                     password=generate_password_hash('pass'), role='finder')
            db.session.add(u)
            db.session.commit()
            found = User.query.filter_by(email='model_test@ex.com').first()
            assert found is not None
            assert found.name == 'Test'

    def test_unique_email_constraint(self, app, db):
        with app.app_context():
            u1 = User(name='A', email='dup@ex.com',
                      password='x', role='finder')
            u2 = User(name='B', email='dup@ex.com',
                      password='x', role='provider')
            db.session.add(u1)
            db.session.commit()
            db.session.add(u2)
            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()

    def test_job_application_unique_constraint(self, app, db):
        with app.app_context():
            u_f = User(name='Finder', email='f_model@ex.com', password='x', role='finder')
            u_p = User(name='Prov', email='p_model@ex.com', password='x', role='provider')
            db.session.add_all([u_f, u_p])
            db.session.flush()
            prov = Provider(user_id=u_p.id, title='P', location='X')
            db.session.add(prov)
            post = ServicePost(finder_id=u_f.id, title='Job', description='desc')
            db.session.add(post)
            db.session.flush()
            app1 = JobApplication(post_id=post.id, provider_id=prov.id)
            app2 = JobApplication(post_id=post.id, provider_id=prov.id)
            db.session.add(app1)
            db.session.commit()
            db.session.add(app2)
            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()

    def test_profile_completion_helper(self, app, db):
        with app.app_context():
            from servease.utils import profile_completion
            u = User(name='Alice', email='pc_test@ex.com',
                     password='x', role='provider', profile_image='img.jpg')
            db.session.add(u)
            db.session.flush()
            p = Provider(user_id=u.id, title='Pro', description='Desc',
                         location='Dhaka')
            db.session.add(p)
            db.session.flush()
            db.session.add(ProviderSkill(provider_id=p.id, skill='Plumbing'))
            db.session.commit()
            score = profile_completion(u)
            assert 0 <= score <= 100
            assert score > 0
