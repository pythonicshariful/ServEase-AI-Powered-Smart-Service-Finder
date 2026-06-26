"""AI matching helpers extracted from app.py."""
from __future__ import annotations

from models import Provider, ServicePost


# ─── Simple keyword-based fallback ────────────────────────────────────────────

def simple_match_score(post: ServicePost, provider: Provider) -> int:
    text = (post.title + ' ' + (post.description or '')).lower()
    score = 0
    for s in provider.skills:
        if s.skill.lower() in text:
            score += 2
        else:
            for token in s.skill.lower().split():
                if token in text:
                    score += 1
    score += int(provider.rating or 0)
    if provider.verified:
        score += 2
    return score


# ─── Gemini-powered provider matching ─────────────────────────────────────────

def gemini_match_providers(post: ServicePost, providers: list[Provider], gemini_model=None) -> list[tuple[int, Provider]]:
    """Rank providers for a given post. Falls back to simple scoring if AI unavailable."""
    if not gemini_model:
        scored = [(simple_match_score(post, p), p) for p in providers if p.user]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    try:
        provider_data = []
        for p in providers:
            if not p.user:
                continue
            skills = ', '.join(s.skill for s in p.skills)
            provider_data.append({
                'id': p.id,
                'name': p.user.name,
                'title': p.title or 'No title',
                'description': p.description or '',
                'skills': skills or 'No skills',
                'location': p.location or 'Not specified',
                'verified': p.verified,
                'rating': p.rating or 0,
            })

        if not provider_data:
            return []

        prompt = (
            "You are a service matching AI. Rank the following providers for the given job post by relevance (1-100). "
            "Return ONLY a comma-separated list of provider IDs, best match first.\n\n"
            f"Job: {post.title}\nDescription: {post.description or ''}\nLocation: {post.location or 'Any'}\n\n"
            "Providers:\n" +
            "\n".join(
                f"ID {p['id']}: {p['name']} - {p['title']}, Skills: {p['skills']}, "
                f"Location: {p['location']}, Verified: {p['verified']}, Rating: {p['rating']}"
                for p in provider_data
            )
        )

        response = gemini_model.generate_content(prompt)
        ranked_ids = [int(x.strip()) for x in response.text.split(',') if x.strip().isdigit()]

        prov_map = {p.id: p for p in providers if p.user}
        scored: list[tuple[int, Provider]] = []
        base = len(provider_data)
        for idx, pid in enumerate(ranked_ids):
            if pid in prov_map:
                s = base - idx + 10 + (5 if prov_map[pid].verified else 0)
                scored.append((s, prov_map[pid]))

        already = {pid for pid in ranked_ids}
        for p in providers:
            if p.user and p.id not in already:
                scored.append((simple_match_score(post, p), p))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    except Exception as exc:
        print(f"[AI matching error] {exc}")
        scored = [(simple_match_score(post, p), p) for p in providers if p.user]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored


# ─── Gemini-powered post matching ─────────────────────────────────────────────

def gemini_match_posts(provider: Provider, posts: list[ServicePost], gemini_model=None) -> list[tuple[int, ServicePost]]:
    """Rank open posts for a given provider. Falls back to simple scoring if AI unavailable."""
    open_posts = [p for p in posts if p.status == 'open']

    if not gemini_model:
        scored = [(simple_match_score(p, provider), p) for p in open_posts]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    try:
        post_data = [
            {'id': p.id, 'title': p.title, 'description': p.description or '',
             'location': p.location or 'Not specified',
             'budget': f"{p.budget_min or 0}-{p.budget_max or 0} BDT"}
            for p in open_posts
        ]

        if not post_data:
            return []

        skills = ', '.join(s.skill for s in provider.skills)
        prompt = (
            "You are a service matching AI. Rank the following job posts for this provider by relevance. "
            "Return ONLY a comma-separated list of post IDs, best match first.\n\n"
            f"Provider: {provider.user.name}\nTitle: {provider.title or ''}\n"
            f"Skills: {skills or 'None'}\nLocation: {provider.location or 'Any'}\n\n"
            "Posts:\n" +
            "\n".join(
                f"ID {p['id']}: {p['title']}, Budget: {p['budget']}, Location: {p['location']}"
                for p in post_data
            )
        )

        response = gemini_model.generate_content(prompt)
        ranked_ids = [int(x.strip()) for x in response.text.split(',') if x.strip().isdigit()]

        post_map = {p.id: p for p in open_posts}
        scored: list[tuple[int, ServicePost]] = []
        base = len(post_data)
        for idx, pid in enumerate(ranked_ids):
            if pid in post_map:
                scored.append((base - idx + 10, post_map[pid]))

        already = set(ranked_ids)
        for p in open_posts:
            if p.id not in already:
                scored.append((simple_match_score(p, provider), p))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    except Exception as exc:
        print(f"[AI matching error] {exc}")
        scored = [(simple_match_score(p, provider), p) for p in open_posts]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored
