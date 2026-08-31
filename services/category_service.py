"""
Category management business logic (admin only).
"""

from database.database import db
from database.models import Category


class CategoryError(Exception):
    pass


def create_category(name: str, description: str = "") -> Category:
    if not name or not name.strip():
        raise CategoryError("Category name is required.")

    existing = Category.query.filter_by(Name=name.strip()).first()
    if existing:
        raise CategoryError("A category with this name already exists.")

    category = Category(Name=name.strip(), Description=description, IsActive=True)
    db.session.add(category)
    db.session.commit()
    return category


def toggle_category_active(category_id: int) -> Category:
    category = Category.query.get(category_id)
    if not category:
        raise CategoryError("Category not found.")
    category.IsActive = not category.IsActive
    db.session.commit()
    return category
