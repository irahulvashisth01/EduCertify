"""
Admin user-management business logic.
"""

from database.database import db
from database.models import User


class UserServiceError(Exception):
    pass


def toggle_user_active(user_id: int) -> User:
    user = User.query.get(user_id)
    if not user:
        raise UserServiceError("User not found.")
    if user.Role == "Admin":
        raise UserServiceError("Admin accounts cannot be deactivated here.")
    user.IsActive = not user.IsActive
    db.session.commit()
    return user


def get_all_users(role: str = None):
    query = User.query
    if role:
        query = query.filter_by(Role=role)
    return query.order_by(User.CreatedAt.desc()).all()
