"""
EduCertify — User Management Service

Admin-only business logic for managing platform users.

Responsibilities:
- Activate/deactivate users
- Prevent administrators from being deactivated
- Retrieve users
- Filter users by role
- Safely handle database transactions

Routes should call this service instead of directly modifying
User records.
"""

from database.database import db
from database.models import User


# ============================================================
# CUSTOM EXCEPTION
# ============================================================

class UserServiceError(Exception):
    """
    Raised when a user-management operation fails.
    """

    pass


# ============================================================
# TOGGLE USER ACTIVE STATUS
# ============================================================

def toggle_user_active(
    user_id: int,
) -> User:
    """
    Activate or deactivate a user.

    Administrator accounts cannot be deactivated through
    this function.

    Returns:
        User: Updated user object.

    Raises:
        UserServiceError:
            If the user does not exist or is an Admin.
    """

    if not user_id:
        raise UserServiceError(
            "User ID is required."
        )

    # --------------------------------------------------------
    # Find user
    # --------------------------------------------------------

    user = db.session.get(
        User,
        user_id,
    )

    if user is None:
        raise UserServiceError(
            "User not found."
        )

    # --------------------------------------------------------
    # Protect administrator accounts
    # --------------------------------------------------------

    if user.Role == "Admin":
        raise UserServiceError(
            "Admin accounts cannot be deactivated here."
        )

    # --------------------------------------------------------
    # Toggle status
    # --------------------------------------------------------

    user.IsActive = not bool(
        user.IsActive
    )

    try:

        db.session.commit()

        db.session.refresh(user)

    except Exception as exc:

        db.session.rollback()

        raise UserServiceError(
            "Unable to update user status. "
            "Please try again."
        ) from exc

    return user


# ============================================================
# GET ALL USERS
# ============================================================

def get_all_users(
    role: str = None,
):
    """
    Retrieve users from the database.

    Args:
        role:
            Optional role filter.

            Examples:
                "Student"
                "Instructor"
                "Admin"

    Returns:
        list[User]
    """

    query = User.query

    # --------------------------------------------------------
    # Optional role filter
    # --------------------------------------------------------

    if role:

        role = str(
            role
        ).strip()

        allowed_roles = {
            "Student",
            "Instructor",
            "Admin",
        }

        if role not in allowed_roles:
            raise UserServiceError(
                "Invalid user role."
            )

        query = query.filter_by(
            Role=role
        )

    # --------------------------------------------------------
    # Latest users first
    # --------------------------------------------------------

    return (
        query
        .order_by(
            User.CreatedAt.desc()
        )
        .all()
    )