"""
EduCertify — Public Routes

Public-facing marketing pages:

- Home
- About
- Contact

Course discovery is handled by:
    routes/course_routes.py

Certificate verification is handled by:
    routes/certificate_routes.py
"""

from flask import (
    Blueprint,
    render_template,
)

from database.models import (
    Course,
    Category,
)


# ============================================================
# BLUEPRINT
# ============================================================

public_bp = Blueprint(
    "public",
    __name__,
)


# ============================================================
# HOME
# ============================================================

@public_bp.route("/")
def home():
    """
    Render the EduCertify homepage.

    Displays:
    - Featured published courses
    - Active categories
    - Platform statistics
    """

    # --------------------------------------------------------
    # Featured courses
    # --------------------------------------------------------

    featured_courses = (
        Course.query
        .filter_by(
            Status="Published"
        )
        .order_by(
            Course.CreatedAt.desc(),
            Course.CourseID.desc(),
        )
        .limit(6)
        .all()
    )

    # --------------------------------------------------------
    # Active categories
    # --------------------------------------------------------

    categories = (
        Category.query
        .filter_by(
            IsActive=True
        )
        .order_by(
            Category.Name.asc()
        )
        .limit(8)
        .all()
    )

    # --------------------------------------------------------
    # Platform statistics
    # --------------------------------------------------------

    stats = {
        "courses": (
            Course.query
            .filter_by(
                Status="Published"
            )
            .count()
        ),

        "categories": (
            Category.query
            .filter_by(
                IsActive=True
            )
            .count()
        ),
    }

    return render_template(
        "index.html",
        featured_courses=featured_courses,
        categories=categories,
        stats=stats,
    )


# ============================================================
# ABOUT
# ============================================================

@public_bp.route("/about")
def about():
    """
    Render the EduCertify About page.
    """

    return render_template(
        "public_about.html"
    )


# ============================================================
# CONTACT
# ============================================================

@public_bp.route("/contact")
def contact():
    """
    Render the EduCertify Contact page.
    """

    return render_template(
        "public_contact.html"
    )