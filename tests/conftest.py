"""
pytest fixtures for ServEase test suite.
"""
import pytest
from servease import create_app
from models import db as _db


@pytest.fixture(scope='session')
def app():
    """Create application for the test session."""
    app = create_app('testing')
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture(scope='function')
def db(app):
    """Database session that rolls back after each test."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        yield _db
        transaction.rollback()
        connection.close()
