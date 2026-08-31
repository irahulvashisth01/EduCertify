"""
Public-facing marketing pages: home, about, contact.
Course discovery lives in course_routes.py; certificate verification
lives in certificate_routes.py.
"""

from flask import Blueprint, render_template
from database.models import Course, Category

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    featured_courses = (
        Course.query.filter_by(Status="Published")
        .order_by(Course.CreatedAt.desc())
        .limit(6)
        .all()
    )
    categories = Category.query.filter_by(IsActive=True).limit(8).all()
    stats = {
        "courses": Course.query.filter_by(Status="Published").count(),
        "categories": Category.query.filter_by(IsActive=True).count(),
    }
    return render_template(
        "index.html",
        featured_courses=featured_courses,
        categories=categories,
        stats=stats,
    )


@public_bp.route("/about")
def about():
    return render_template("public_about.html")


@public_bp.route("/contact")
def contact():
    return render_template("public_contact.html")
