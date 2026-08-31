"""
General-purpose helper functions used across services and routes.
"""

import re
import random
import string
from datetime import datetime


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "course"


def unique_slug(base_slug: str, exists_fn) -> str:
    """Append a numeric suffix until exists_fn(slug) returns False.
    exists_fn should be a callable that checks the DB for a slug collision."""
    slug = base_slug
    counter = 2
    while exists_fn(slug):
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def generate_certificate_number(year: int = None) -> str:
    """Generate a certificate number in the form EDC-2026-000125.
    The numeric part is randomized here; the service layer re-checks
    uniqueness against the database before committing."""
    year = year or datetime.utcnow().year
    suffix = "".join(random.choices(string.digits, k=6))
    return f"EDC-{year}-{suffix}"


def json_response(success: bool, message: str = "", **extra):
    """Build a consistent JSON response payload."""
    payload = {"success": success, "message": message}
    payload.update(extra)
    return payload


def calculate_percentage(part: float, whole: float) -> float:
    if not whole:
        return 0.0
    return round((part / whole) * 100, 1)


def truncate(text: str, length: int = 150) -> str:
    if not text:
        return ""
    return text if len(text) <= length else text[:length].rstrip() + "..."
