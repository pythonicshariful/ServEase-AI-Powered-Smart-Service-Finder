"""
Feature integration tests – messaging, job workflow, reviews.
"""
import pytest
from werkzeug.security import generate_password_hash
from models import db, User, Provider, Finder, ServicePost, JobApplication, Review, Conversation


def _create_finder(db_session, suffix='a'):
    u = User(name=f'Finder{suffix}', email=f'finder{suffix}@test.com',
             password=generate_password_hash('pass123'), role='finder')
    db_session.add(u)
    db_session.flush()
    db_session.add(Finder(user_id=u.id, bio=''))
    db_session.flush()
    return u


def _create_provider(db_session, suffix='a'):
    u = User(name=f'Provider{suffix}', email=f'provider{suffix}@test.com',
             password=generate_password_hash('pass123'), role='provider')
    db_session.add(u)
    db_session.flush()
    p = Provider(user_id=u.id, title='Service Pro', location='Dhaka')
    db_session.add(p)
    db_session.flush()
    return u, p


class TestJobWorkflow:
    def test_application_created(self, app, db):
        with app.app_context():
            finder = _create_finder(db.session, 'jw1')
            prov_user, prov = _create_provider(db.session, 'jw1')
            post = ServicePost(finder_id=finder.id, title='Fix pipe',
                               description='Need plumber', status='open')
            db.session.add(post)
            db.session.flush()
            application = JobApplication(post_id=post.id, provider_id=prov.id, status='pending')
            db.session.add(application)
            db.session.commit()
            found = JobApplication.query.filter_by(post_id=post.id, provider_id=prov.id).first()
            assert found is not None
            assert found.status == 'pending'

    def test_post_status_transition(self, app, db):
        with app.app_context():
            finder = _create_finder(db.session, 'jw2')
            prov_user, prov = _create_provider(db.session, 'jw2')
            post = ServicePost(finder_id=finder.id, title='Job',
                               description='desc', status='open')
            db.session.add(post)
            db.session.flush()
            post.status = 'in_progress'
            post.accepted_provider_id = prov.id
            db.session.commit()
            refreshed = db.session.get(ServicePost, post.id)
            assert refreshed.status == 'in_progress'


class TestReviews:
    def test_review_created(self, app, db):
        with app.app_context():
            finder = _create_finder(db.session, 'rv1')
            prov_user, prov = _create_provider(db.session, 'rv1')
            post = ServicePost(finder_id=finder.id, title='Done job',
                               description='Completed', status='completed',
                               accepted_provider_id=prov.id)
            db.session.add(post)
            db.session.flush()
            review = Review(provider_id=prov.id, finder_id=finder.id,
                            post_id=post.id, rating=4.5, comment='Great work!')
            db.session.add(review)
            db.session.commit()
            found = Review.query.filter_by(post_id=post.id).first()
            assert found is not None
            assert found.rating == 4.5


class TestMessaging:
    def test_conversation_created(self, app, db):
        with app.app_context():
            finder = _create_finder(db.session, 'msg1')
            prov_user, prov = _create_provider(db.session, 'msg1')
            conv = Conversation(finder_id=finder.id, provider_user_id=prov_user.id)
            db.session.add(conv)
            db.session.commit()
            found = Conversation.query.filter_by(
                finder_id=finder.id, provider_user_id=prov_user.id
            ).first()
            assert found is not None
