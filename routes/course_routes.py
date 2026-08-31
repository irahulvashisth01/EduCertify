"""
EduCertify — Public Course Routes

Public course discovery:
- Browse published courses
- Search courses
- Filter by category
- Filter by level
- Sort courses
- Paginate results
- View course details

Enrollment and learning actions are handled separately
in student_routes.py because they require authentication.
"""

from flask import (
    Blueprint,
    render_template,
    request,
    session,
)

from sqlalchemy import or_

from database.database import db
from database.models import (
    Course,
    Category,
    Enrollment,
)


# ============================================================
# BLUEPRINT
# ============================================================

courses_bp = Blueprint(
    "courses",
    __name__,
    url_prefix="/courses",
)


# ============================================================
# CONFIGURATION
# ============================================================

PER_PAGE = 9
MAX_PAGE = 100000


# ============================================================
# COURSE LIST / DISCOVERY
# ============================================================

@courses_bp.route("/")
def index():
    """
    Display published courses.

    Supported query parameters:

        q          Search keyword
        category   Category ID
        level      Course level
        sort       newest / price_low / price_high / title
        page       Page number

    Example:

        /courses/
        /courses/?q=python
        /courses/?category=2
        /courses/?level=Beginner
        /courses/?sort=price_low
        /courses/?page=2
    """

    # --------------------------------------------------------
    # Base query
    # --------------------------------------------------------

    query = (
        Course.query
        .filter_by(Status="Published")
    )

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    search = (
        request.args.get("q", "")
        .strip()
    )

    if search:

        like = f"%{search}%"

        query = query.filter(
            or_(
                Course.Title.ilike(like),
                Course.ShortDescription.ilike(like),
            )
        )

    # --------------------------------------------------------
    # Category filter
    # --------------------------------------------------------

    category_id = request.args.get(
        "category",
        default=None,
        type=int,
    )

    if category_id:

        query = query.filter(
            Course.CategoryID == category_id
        )

    # --------------------------------------------------------
    # Level filter
    # --------------------------------------------------------

    level = (
        request.args.get(
            "level",
            "",
        )
        .strip()
    )

    if level:

        query = query.filter(
            Course.Level == level
        )

    # --------------------------------------------------------
    # Sorting
    # --------------------------------------------------------

    sort = (
        request.args.get(
            "sort",
            "newest",
        )
        .strip()
    )

    if sort == "price_low":

        query = query.order_by(
            Course.Price.asc(),
            Course.CourseID.desc(),
        )

    elif sort == "price_high":

        query = query.order_by(
            Course.Price.desc(),
            Course.CourseID.desc(),
        )

    elif sort == "title":

        query = query.order_by(
            Course.Title.asc(),
            Course.CourseID.desc(),
        )

    else:

        # Default: newest courses first.
        sort = "newest"

        query = query.order_by(
            Course.CreatedAt.desc(),
            Course.CourseID.desc(),
        )

    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    page = request.args.get(
        "page",
        default=1,
        type=int,
    )

    if page is None or page < 1:
        page = 1

    if page > MAX_PAGE:
        page = MAX_PAGE

    pagination = query.paginate(
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )

    # --------------------------------------------------------
    # Active categories
    # --------------------------------------------------------

    categories = (
        Category.query
        .filter_by(IsActive=True)
        .order_by(
            Category.Name.asc()
        )
        .all()
    )

    # --------------------------------------------------------
    # Student enrollment information
    # --------------------------------------------------------

    enrolled_course_ids = set()

    user_id = session.get(
        "user_id"
    )

    user_role = session.get(
        "role"
    )

    if user_id and user_role == "Student":

        enrollments = (
            Enrollment.query
            .filter_by(
                StudentID=user_id
            )
            .all()
        )

        enrolled_course_ids = {
            enrollment.CourseID
            for enrollment in enrollments
        }

    # --------------------------------------------------------
    # Render
    # --------------------------------------------------------

    return render_template(
        "courses/index.html",

        courses=pagination.items,

        pagination=pagination,

        categories=categories,

        search=search,

        selected_category=category_id,

        selected_level=level,

        selected_sort=sort,

        enrolled_course_ids=(
            enrolled_course_ids
        ),
    )


# ============================================================
# COURSE DETAILS
# ============================================================

@courses_bp.route(
    "/<slug>",
)
def details(slug):
    """
    Display a public course details page.

    Example:

        /courses/python-for-beginners
    """

    slug = (
        slug
        .strip()
    )

    course = (
        Course.query
        .filter_by(
            Slug=slug,
            Status="Published",
        )
        .first_or_404()
    )

    # --------------------------------------------------------
    # Enrollment status
    # --------------------------------------------------------

    is_enrolled = False

    user_id = session.get(
        "user_id"
    )

    user_role = session.get(
        "role"
    )

    if user_id and user_role == "Student":

        enrollment = (
            Enrollment.query
            .filter_by(
                StudentID=user_id,
                CourseID=course.CourseID,
            )
            .first()
        )

        is_enrolled = (
            enrollment is not None
        )

    # --------------------------------------------------------
    # Render
    # --------------------------------------------------------

    return render_template(
        "courses/details.html",
        course=course,
        is_enrolled=is_enrolled,
    )