"""
Server-side validation helpers. Client-side JS validation is a UX nicety
only — every rule here must ALSO be enforced server-side, since JS can be
bypassed.
"""

import re

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CERTIFICATE_ID_REGEX = re.compile(r"^EDC-\d{4}-\d{6}$")


def is_valid_email(email: str) -> bool:
    if not email or len(email) > 150:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def is_valid_password(password: str):
    """Returns (is_valid, message)."""
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    return True, ""


def is_valid_full_name(name: str) -> bool:
    if not name:
        return False
    name = name.strip()
    return 2 <= len(name) <= 150


def is_valid_certificate_number(cert_id: str) -> bool:
    if not cert_id:
        return False
    return bool(CERTIFICATE_ID_REGEX.match(cert_id.strip().upper()))


def is_valid_rating(rating) -> bool:
    try:
        value = int(rating)
        return 1 <= value <= 5
    except (TypeError, ValueError):
        return False


def is_non_empty(value: str, max_length: int = None) -> bool:
    if not value or not value.strip():
        return False
    if max_length and len(value) > max_length:
        return False
    return True


def is_valid_role(role: str) -> bool:
    return role in ("Student", "Instructor", "Admin")


def is_positive_int(value, allow_zero=True) -> bool:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return False
    return value >= 0 if allow_zero else value > 0
