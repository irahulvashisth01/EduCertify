"""
EduCertify — Public Routes
==========================

Public-facing pages of the EduCertify platform.

Routes:
    /
        EduCertify homepage

    /about
        About EduCertify

    /contact
        Contact EduCertify

Course discovery:
    routes/course_routes.py

Certificate verification:
    routes/certificate_routes.py

Authentication:
    routes/auth_routes.py
"""

# ============================================================
# FLASK
# ============================================================

from flask import (
    Blueprint,
    render_template,
)


# ============================================================
# DATABASE MODELS
# ============================================================

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

@public_bp.route(
    "/",
    methods=["GET"],
)
def home():
    """
    Render the EduCertify homepage.

    Provides:

    - Featured published courses
    - Active categories
    - Platform statistics
    - SEO metadata
    """

    # --------------------------------------------------------
    # FEATURED COURSES
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
    # ACTIVE CATEGORIES
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
    # TOTAL PUBLISHED COURSES
    # --------------------------------------------------------

    courses_count = (
        Course.query
        .filter_by(
            Status="Published"
        )
        .count()
    )

    # --------------------------------------------------------
    # TOTAL ACTIVE CATEGORIES
    # --------------------------------------------------------

    categories_count = (
        Category.query
        .filter_by(
            IsActive=True
        )
        .count()
    )

    # --------------------------------------------------------
    # PLATFORM STATISTICS
    # --------------------------------------------------------

    stats = {
        "courses": courses_count,
        "categories": categories_count,
    }

    # --------------------------------------------------------
    # PAGE INFORMATION
    # --------------------------------------------------------

    page_name = "Home"

    page_title = (
        "EduCertify — Learn • Certify • Succeed"
    )

    page_description = (
        "EduCertify is a modern learning and "
        "certification platform where students "
        "can learn new skills, complete courses "
        "and earn certificates."
    )

    # --------------------------------------------------------
    # RENDER
    # --------------------------------------------------------

    return render_template(
        "index.html",

        featured_courses=featured_courses,

        categories=categories,

        stats=stats,

        page_name=page_name,

        page_title=page_title,

        page_description=page_description,
    )


# ============================================================
# ABOUT
# ============================================================

@public_bp.route(
    "/about",
    methods=["GET"],
)
def about():
    """
    Render the EduCertify About page.
    """

    return render_template(
        "public_about.html",

        page_name="About",

        page_title=(
            "About EduCertify"
        ),

        page_description=(
            "Learn more about EduCertify, "
            "our learning platform and "
            "certification ecosystem."
        ),
    )


# ============================================================
# CONTACT
# ============================================================

@public_bp.route(
    "/contact",
    methods=["GET"],
)
def contact():
    """
    Render the EduCertify Contact page.
    """

    return render_template(
        "public_contact.html",

        page_name="Contact",

        page_title=(
            "Contact EduCertify"
        ),

        page_description=(
            "Contact EduCertify for support, "
            "questions, feedback and platform "
            "information."
        ),
    )


# ============================================================
# END OF PUBLIC ROUTES
# ============================================================