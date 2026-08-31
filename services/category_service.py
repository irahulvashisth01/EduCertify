"""
EduCertify — Category Service

Business logic for category management.

Category creation and activation/deactivation are
restricted to administrators through the route layer.
"""

from database.database import db
from database.models import Category


# ============================================================
# CUSTOM EXCEPTION
# ============================================================

class CategoryError(Exception):
    """
    Raised when a category operation fails.
    """

    pass


# ============================================================
# CREATE CATEGORY
# ============================================================

def create_category(
    name: str,
    description: str = "",
) -> Category:
    """
    Create a new course category.

    Args:
        name: Category name.
        description: Optional category description.

    Returns:
        Category: Newly created category.

    Raises:
        CategoryError: If validation or database operation fails.
    """

    # --------------------------------------------------------
    # Normalize input
    # --------------------------------------------------------

    name = (
        name or ""
    ).strip()

    description = (
        description or ""
    ).strip()

    # --------------------------------------------------------
    # Validate name
    # --------------------------------------------------------

    if not name:
        raise CategoryError(
            "Category name is required."
        )

    if len(name) > 100:
        raise CategoryError(
            "Category name must not exceed 100 characters."
        )

    if len(description) > 500:
        raise CategoryError(
            "Category description must not exceed 500 characters."
        )

    # --------------------------------------------------------
    # Check duplicate category
    # --------------------------------------------------------

    existing = (
        Category.query
        .filter_by(
            Name=name
        )
        .first()
    )

    if existing:
        raise CategoryError(
            "A category with this name already exists."
        )

    # --------------------------------------------------------
    # Create category
    # --------------------------------------------------------

    category = Category(
        Name=name,
        Description=description,
        IsActive=True,
    )

    try:

        db.session.add(category)

        db.session.commit()

        # Make sure generated fields are available.
        db.session.refresh(category)

        return category

    except Exception as exc:

        db.session.rollback()

        raise CategoryError(
            "Unable to create the category. "
            "Please try again."
        ) from exc


# ============================================================
# TOGGLE CATEGORY STATUS
# ============================================================

def toggle_category_active(
    category_id: int,
) -> Category:
    """
    Activate or deactivate a category.

    Args:
        category_id: Database ID of the category.

    Returns:
        Category: Updated category.

    Raises:
        CategoryError: If the category doesn't exist
        or the database operation fails.
    """

    if not category_id:
        raise CategoryError(
            "Category ID is required."
        )

    # SQLAlchemy 2.x compatible lookup.
    category = db.session.get(
        Category,
        category_id,
    )

    if category is None:
        raise CategoryError(
            "Category not found."
        )

    # --------------------------------------------------------
    # Toggle status
    # --------------------------------------------------------

    category.IsActive = not bool(
        category.IsActive
    )

    try:

        db.session.commit()

        return category

    except Exception as exc:

        db.session.rollback()

        raise CategoryError(
            "Unable to update category status. "
            "Please try again."
        ) from exc