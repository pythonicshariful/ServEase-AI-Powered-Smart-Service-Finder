"""Shared utility helpers and Jinja2 template filters."""
from __future__ import annotations

import json
import struct
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask


# ─── Template filters ─────────────────────────────────────────────────────────

def timeago(dt: datetime | str | None) -> str:
    """Return a human-friendly time difference (e.g. '3 days ago')."""
    if not dt:
        return ''
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return str(dt)
    now = datetime.utcnow()
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    diff = now - dt if now >= dt else dt - now
    seconds = diff.total_seconds()
    intervals = (
        ('year', 31536000), ('month', 2592000), ('week', 604800),
        ('day', 86400), ('hour', 3600), ('minute', 60), ('second', 1),
    )
    for name, count in intervals:
        value = int(seconds // count)
        if value:
            return f"{value} {name}{'s' if value > 1 else ''} ago"
    return 'just now'


def fromjson(s: str | None) -> dict:
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}


def register_filters(app: "Flask") -> None:
    app.template_filter('timeago')(timeago)
    app.template_filter('fromjson')(fromjson)


# ─── Image magic-byte validation ──────────────────────────────────────────────

_MAGIC: dict[bytes, str] = {
    b'\x89PNG':  'png',
    b'\xff\xd8': 'jpeg',
    b'GIF8':     'gif',
    b'RIFF':     'webp',   # RIFF....WEBP
}


def is_valid_image(stream) -> bool:
    """
    Read the first 12 bytes and check magic bytes.
    Resets the stream position afterwards.
    """
    header = stream.read(12)
    stream.seek(0)
    for magic, _ in _MAGIC.items():
        if header[:len(magic)] == magic:
            # Extra check: RIFF must also have 'WEBP' at bytes 8-12
            if magic == b'RIFF':
                return header[8:12] == b'WEBP'
            return True
    return False


# ─── Profile completion ───────────────────────────────────────────────────────

def profile_completion(user) -> int:
    """Return a 0-100 integer indicating how complete a user's profile is."""
    if user.role == 'provider':
        prov = user.provider
        if prov is None:
            return 0
        fields = [
            user.name,
            user.profile_image,
            prov.title,
            prov.description,
            prov.location,
            bool(prov.skills),
        ]
    else:
        finder = user.finder
        if finder is None:
            return 0
        fields = [
            user.name,
            user.profile_image,
            getattr(finder, 'bio', None),
            getattr(finder, 'location', None),
        ]
    filled = sum(1 for f in fields if f)
    return int(filled / len(fields) * 100)
