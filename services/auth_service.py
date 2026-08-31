"""
EduCertify — Authentication Service

Business logic for:
- User registration
- User authentication
- Password changes

This service does not directly access Flask request/session objects,
which keeps it reusable and testable.
"""

from database.database import db
from database.models import User

from utils.security import (
    hash_password,
    verify_password,
)

from utils.validators import (
    is_valid_email,
    is_valid_password,
    is_valid_full_name,
    is_valid_role,
)


# ============================================================
# CUSTOM EXCEPTION
# ============================================================

class AuthError(Exception):
    """
    Raised when an authentication operation fails.

    The message is safe to display to the user.
    """

    pass


# ============================================================
# REGISTER USER
# ============================================================

def register_user(
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
    role: str = "Student",
) -> User:
    """
    Register a new Student or Instructor.

    Admin accounts must be provisioned separately.

    Returns:
        User: newly created user

    Raises:
        AuthError: when validation or database operation fails
    """

    # --------------------------------------------------------
    # Normalize input
    # --------------------------------------------------------

    full_name = (
        full_name or ""
    ).strip()

    email = (
        email or ""
    ).strip().lower()

    role = (
        role or "Student"
    ).strip()

    # --------------------------------------------------------
    # Validate full name
    # --------------------------------------------------------

    if not is_valid_full_name(
        full_name
    ):
        raise AuthError(
            "Please enter a valid full name "
            "(2-150 characters)."
        )

    # --------------------------------------------------------
    # Validate email
    # --------------------------------------------------------

    if not is_valid_email(
        email
    ):
        raise AuthError(
            "Please enter a valid email address."
        )

    # --------------------------------------------------------
    # Validate password confirmation
    # --------------------------------------------------------

    if password != confirm_password:
        raise AuthError(
            "Passwords do not match."
        )

    # --------------------------------------------------------
    # Validate password strength
    # --------------------------------------------------------

    valid_password, password_message = (
        is_valid_password(password)
    )

    if not valid_password:
        raise AuthError(
            password_message
        )

    # --------------------------------------------------------
    # Validate role
    # --------------------------------------------------------

    # Public registration is restricted to these roles.
    allowed_roles = {
        "Student",
        "Instructor",
    }

    if role not in allowed_roles:
        raise AuthError(
            "Invalid account type selected."
        )

    if not is_valid_role(role):
        raise AuthError(
            "Invalid role."
        )

    # --------------------------------------------------------
    # Check existing account
    # --------------------------------------------------------

    existing_user = (
        User.query
        .filter_by(
            Email=email
        )
        .first()
    )

    if existing_user:
        raise AuthError(
            "An account with this email already exists."
        )

    # --------------------------------------------------------
    # Create user
    # --------------------------------------------------------

    user = User(
        FullName=full_name,
        Email=email,
        PasswordHash=hash_password(
            password
        ),
        Role=role,
        IsActive=True,
    )

    try:

        db.session.add(user)

        db.session.commit()

        # Refresh generated database values such as
        # UserID before returning the object.
        db.session.refresh(user)

        return user

    except Exception as exc:

        db.session.rollback()

        # Log the actual exception server-side if logging
        # is configured, but don't expose database details
        # to the user.
        raise AuthError(
            "Unable to create your account. "
            "Please try again."
        ) from exc


# ============================================================
# AUTHENTICATE USER
# ============================================================

def authenticate_user(
    email: str,
    password: str,
) -> User:
    """
    Authenticate a user using email and password.

    Raises:
        AuthError: when authentication fails
    """

    email = (
        email or ""
    ).strip().lower()

    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    if not email or not password:
        raise AuthError(
            "Please enter both email and password."
        )

    # --------------------------------------------------------
    # Find user
    # --------------------------------------------------------

    user = (
        User.query
        .filter_by(
            Email=email
        )
        .first()
    )

    # --------------------------------------------------------
    # Authentication failure
    # --------------------------------------------------------

    if (
        user is None
        or not verify_password(
            user.PasswordHash,
            password,
        )
    ):
        raise AuthError(
            "Invalid email or password."
        )

    # --------------------------------------------------------
    # Account status
    # --------------------------------------------------------

    if not user.IsActive:
        raise AuthError(
            "Your account has been deactivated. "
            "Please contact support."
        )

    return user


# ============================================================
# CHANGE PASSWORD
# ============================================================

def change_password(
    user: User,
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> None:
    """
    Change an authenticated user's password.

    Raises:
        AuthError: when validation fails.
    """

    # --------------------------------------------------------
    # Validate current password
    # --------------------------------------------------------

    if not current_password:
        raise AuthError(
            "Please enter your current password."
        )

    if not verify_password(
        user.PasswordHash,
        current_password,
    ):
        raise AuthError(
            "Current password is incorrect."
        )

    # --------------------------------------------------------
    # Confirm new password
    # --------------------------------------------------------

    if new_password != confirm_password:
        raise AuthError(
            "New passwords do not match."
        )

    # --------------------------------------------------------
    # Validate new password
    # --------------------------------------------------------

    valid_password, password_message = (
        is_valid_password(
            new_password
        )
    )

    if not valid_password:
        raise AuthError(
            password_message
        )

    # --------------------------------------------------------
    # Prevent same password
    # --------------------------------------------------------

    if verify_password(
        user.PasswordHash,
        new_password,
    ):
        raise AuthError(
            "New password must be different "
            "from your current password."
        )

    # --------------------------------------------------------
    # Update password
    # --------------------------------------------------------

    user.PasswordHash = hash_password(
        new_password
    )

    try:

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        raise AuthError(
            "Unable to change your password. "
            "Please try again."
        ) from exc