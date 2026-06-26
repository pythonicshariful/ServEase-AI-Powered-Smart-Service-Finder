"""
AI matching tests – verifies fallback behavior and scoring logic.
"""
import pytest
from unittest.mock import MagicMock, patch
from models import Provider, ProviderSkill, ServicePost, User, Finder


def _make_user(db, name='Test', email=None, role='provider'):
    user = User(
        name=name, email=email or f'{name.lower()}@test.com',
        password='hashed', role=role,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _make_provider(db, user, title='Plumber', skills=None):
    prov = Provider(user_id=user.id, title=title, description=title, location='Dhaka')
    db.session.add(prov)
    db.session.flush()
    for s in (skills or []):
        db.session.add(ProviderSkill(provider_id=prov.id, skill=s))
    db.session.flush()
    return prov


def _make_post(db, finder, title='Fix leaking pipe', description='Need a plumber urgently'):
    post = ServicePost(
        finder_id=finder.id, title=title, description=description,
        location='Dhaka', budget_min=500, budget_max=2000,
    )
    db.session.add(post)
    db.session.flush()
    return post


class TestSimpleMatching:
    def test_keyword_match_increases_score(self, app, db):
        with app.app_context():
            from servease.ai.matching import simple_match_score
            u = _make_user(db, name='Alice', email='alice@test.com', role='provider')
            p = _make_provider(db, u, title='Plumber', skills=['plumbing', 'pipe repair'])
            post = _make_post(db, _make_user(db, name='Bob', email='bob@test.com', role='finder'))
            score = simple_match_score(post, p)
            assert score > 0

    def test_unrelated_provider_gets_low_score(self, app, db):
        with app.app_context():
            from servease.ai.matching import simple_match_score
            u = _make_user(db, name='Carol', email='carol@test.com', role='provider')
            p = _make_provider(db, u, title='Painter', skills=['painting', 'wall art'])
            post = _make_post(db, _make_user(db, name='Dave', email='dave@test.com', role='finder'))
            score = simple_match_score(post, p)
            assert score < 5


class TestGeminiMatchingFallback:
    def test_fallback_when_no_model(self, app, db):
        with app.app_context():
            from servease.ai.matching import gemini_match_providers
            u = _make_user(db, name='Eve', email='eve@test.com', role='provider')
            p = _make_provider(db, u, title='Electrician', skills=['electrical'])
            finder_u = _make_user(db, name='Frank', email='frank@test.com', role='finder')
            post = _make_post(db, finder_u, title='Fix wiring', description='electrical work needed')
            scored = gemini_match_providers(post, [p], gemini_model=None)
            assert isinstance(scored, list)
            assert len(scored) == 1
            assert scored[0][0] > 0

    def test_gemini_error_falls_back(self, app, db):
        with app.app_context():
            from servease.ai.matching import gemini_match_providers
            u = _make_user(db, name='Grace', email='grace@test.com', role='provider')
            p = _make_provider(db, u, title='Cleaner', skills=['cleaning'])
            finder_u = _make_user(db, name='Heidi', email='heidi@test.com', role='finder')
            post = _make_post(db, finder_u, title='House cleaning', description='cleaning service')
            # Mock a model that raises an exception
            bad_model = MagicMock()
            bad_model.generate_content.side_effect = Exception("API error")
            scored = gemini_match_providers(post, [p], gemini_model=bad_model)
            assert isinstance(scored, list)
