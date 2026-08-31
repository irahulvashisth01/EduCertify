"""
Public course discovery: browse, search/filter, and course details.
Enrollment action and the learning interface live in student_routes.py
since they require an authenticated student.
"""

from flask import Blueprint, render_template, request, session
from sqlalchemy import or_

from database.models import Course, Category, Enrollment

courses_bp = Blueprint("courses", __name__, url_prefix="/courses")

PER_PAGE = 9


@courses_bp.route("/")
def index():
    query = Course.query.filter_by(Status="Published")

    search = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)
    level = request.args.get("level", "")
    sort = request.args.get("sort", "newest")
    page = request.args.get("page", 1, type=int)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(Course.Title.ilike(like), Course.ShortDescription.ilike(like)))

    if category_id:
        query = query.filter(Course.CategoryID == category_id)

    if level:
        query = query.filter(Course.Level == level)

    if sort == "price_low":
        query = query.order_by(Course.Price.asc())
    elif sort == "price_high":
        query = query.order_by(Course.Price.desc())
    elif sort == "title":
        query = query.order_by(Course.Title.asc())
    else:
        query = query.order_by(Course.CreatedAt.desc())

    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    categories = Category.query.filter_by(IsActive=True).all()

    enrolled_course_ids = set()
    if session.get("user_id") and session.get("role") == "Student":
        enrolled_course_ids = {
            e.CourseID for e in Enrollment.query.filter_by(StudentID=session["user_id"]).all()
        }

    return render_template(
        "courses/index.html",
        courses=pagination.items,
        pagination=pagination,
        categories=categories,
        search=search,
        selected_category=category_id,
        selected_level=level,
        selected_sort=sort,
        enrolled_course_ids=enrolled_course_ids,
    )


@courses_bp.route("/<slug>")
def details(slug):
    course = Course.query.filter_by(Slug=slug).first_or_404()

    is_enrolled = False
    if session.get("user_id") and session.get("role") == "Student":
        is_enrolled = (
            Enrollment.query.filter_by(StudentID=session["user_id"], CourseID=course.CourseID).first()
            is not None
        )

    return render_template("courses/details.html", course=course, is_enrolled=is_enrolled)
