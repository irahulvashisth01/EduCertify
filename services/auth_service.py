"""
Authentication business logic: registration and login.
Routes call into this service; the service never touches Flask's
request/session objects directly (keeps it testable).
"""

from database.database import db
from database.models import User
from utils.security import hash_password, verify_password
from utils.validators import is_valid_email, is_valid_password, is_valid_full_name, is_valid_role


class AuthError(Exception):
    """Raised for any registration/login failure with a user-facing message."""
    pass


def register_user(full_name: str, email: str, password: str, confirm_password: str, role: str) -> User:
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    role = role or "Student"

    if not is_valid_full_name(full_name):
        raise AuthError("Please enter a valid full name (2-150 characters).")

    if not is_valid_email(email):
        raise AuthError("Please enter a valid email address.")

    if password != confirm_password:
        raise AuthError("Passwords do not match.")

    valid_pw, pw_message = is_valid_password(password)
    if not valid_pw:
        raise AuthError(pw_message)

    # Only allow self-registration as Student or Instructor; Admin accounts
    # are provisioned separately (seed data / by an existing admin).
    if role not in ("Student", "Instructor"):
        raise AuthError("Invalid account type selected.")

    if not is_valid_role(role):
        raise AuthError("Invalid role.")

    existing = User.query.filter_by(Email=email).first()
    if existing:
        raise AuthError("An account with this email already exists.")

    user = User(
        FullName=full_name,
        Email=email,
        PasswordHash=hash_password(password),
        Role=role,
        IsActive=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_user(email: str, password: str) -> User:
    email = (email or "").strip().lower()

    if not email or not password:
        raise AuthError("Please enter both email and password.")

    user = User.query.filter_by(Email=email).first()
    if not user or not verify_password(user.PasswordHash, password):
        raise AuthError("Invalid email or password.")

    if not user.IsActive:
        raise AuthError("Your account has been deactivated. Please contact support.")

    return user


def change_password(user: User, current_password: str, new_password: str, confirm_password: str):
    if not verify_password(user.PasswordHash, current_password):
        raise AuthError("Current password is incorrect.")

    if new_password != confirm_password:
        raise AuthError("New passwords do not match.")

    valid_pw, pw_message = is_valid_password(new_password)
    if not valid_pw:
        raise AuthError(pw_message)

    user.PasswordHash = hash_password(new_password)
    db.session.commit()
