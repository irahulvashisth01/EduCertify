"""
Admin routes: platform-wide management (users, courses, categories,
enrollments, certificates, reviews, reports, settings).
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from database.database import db
from database.models import User, Course, Category, Enrollment, Certificate, Review
from utils.decorators import login_required, role_required
from services.user_service import toggle_user_active, get_all_users, UserServiceError
from services.category_service import create_category, toggle_category_active, CategoryError
from services.certificate_service import revoke_certificate, CertificateError

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@login_required
@role_required("Admin")
def dashboard():
    stats = {
        "total_users": User.query.count(),
        "students": User.query.filter_by(Role="Student").count(),
        "instructors": User.query.filter_by(Role="Instructor").count(),
        "published_courses": Course.query.filter_by(Status="Published").count(),
        "pending_courses": Course.query.filter_by(Status="Pending").count(),
        "enrollments": Enrollment.query.count(),
        "certificates": Certificate.query.count(),
    }
    recent_courses = Course.query.order_by(Course.CreatedAt.desc()).limit(5).all()
    return render_template("admin/dashboard.html", stats=stats, recent_courses=recent_courses)


@admin_bp.route("/users")
@login_required
@role_required("Admin")
def users():
    role_filter = request.args.get("role", "")
    user_list = get_all_users(role_filter or None)
    return render_template("admin/users.html", users=user_list, role_filter=role_filter)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@role_required("Admin")
def toggle_user(user_id):
    try:
        user = toggle_user_active(user_id)
        status = "activated" if user.IsActive else "deactivated"
        flash(f"{user.FullName} has been {status}.", "success")
    except UserServiceError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.users"))


@admin_bp.route("/courses")
@login_required
@role_required("Admin")
def courses():
    status_filter = request.args.get("status", "")
    query = Course.query
    if status_filter:
        query = query.filter_by(Status=status_filter)
    course_list = query.order_by(Course.CreatedAt.desc()).all()
    return render_template("admin/courses.html", courses=course_list, status_filter=status_filter)


@admin_bp.route("/courses/<int:course_id>/approve", methods=["POST"])
@login_required
@role_required("Admin")
def approve_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.Status = "Published"
    course.RejectionReason = None
    db.session.commit()
    flash(f"'{course.Title}' has been published.", "success")
    return redirect(url_for("admin.courses"))


@admin_bp.route("/courses/<int:course_id>/reject", methods=["POST"])
@login_required
@role_required("Admin")
def reject_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.Status = "Rejected"
    course.RejectionReason = request.form.get("reason", "Did not meet quality guidelines.")
    db.session.commit()
    flash(f"'{course.Title}' has been rejected.", "info")
    return redirect(url_for("admin.courses"))


@admin_bp.route("/categories", methods=["GET", "POST"])
@login_required
@role_required("Admin")
def categories():
    if request.method == "POST":
        try:
            create_category(request.form.get("name", ""), request.form.get("description", ""))
            flash("Category created.", "success")
        except CategoryError as e:
            flash(str(e), "error")
        return redirect(url_for("admin.categories"))

    category_list = Category.query.order_by(Category.Name.asc()).all()
    return render_template("admin/categories.html", categories=category_list)


@admin_bp.route("/categories/<int:category_id>/toggle", methods=["POST"])
@login_required
@role_required("Admin")
def toggle_category(category_id):
    try:
        toggle_category_active(category_id)
        flash("Category status updated.", "success")
    except CategoryError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.categories"))


@admin_bp.route("/enrollments")
@login_required
@role_required("Admin")
def enrollments():
    enrollment_list = Enrollment.query.order_by(Enrollment.EnrollmentDate.desc()).limit(200).all()
    return render_template("admin/enrollments.html", enrollments=enrollment_list)


@admin_bp.route("/certificates")
@login_required
@role_required("Admin")
def certificates():
    certificate_list = Certificate.query.order_by(Certificate.IssueDate.desc()).all()
    return render_template("admin/certificates.html", certificates=certificate_list)


@admin_bp.route("/certificates/<int:certificate_id>/revoke", methods=["POST"])
@login_required
@role_required("Admin")
def revoke_certificate_view(certificate_id):
    try:
        cert = revoke_certificate(certificate_id)
        flash(f"Certificate {cert.CertificateNumber} has been revoked.", "info")
    except CertificateError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.certificates"))


@admin_bp.route("/reviews")
@login_required
@role_required("Admin")
def reviews():
    review_list = Review.query.order_by(Review.CreatedAt.desc()).limit(200).all()
    return render_template("admin/reports.html", reviews=review_list)


@admin_bp.route("/reports")
@login_required
@role_required("Admin")
def reports():
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    new_users_30d = User.query.filter(User.CreatedAt >= thirty_days_ago).count()
    new_enrollments_30d = Enrollment.query.filter(Enrollment.EnrollmentDate >= thirty_days_ago).count()
    new_certificates_30d = Certificate.query.filter(Certificate.IssueDate >= thirty_days_ago).count()

    top_courses = (
        Course.query.filter_by(Status="Published")
        .order_by(Course.CreatedAt.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "admin/reports.html",
        new_users_30d=new_users_30d,
        new_enrollments_30d=new_enrollments_30d,
        new_certificates_30d=new_certificates_30d,
        top_courses=top_courses,
        reviews=None,
    )


@admin_bp.route("/settings")
@login_required
@role_required("Admin")
def settings():
    return render_template("admin/settings.html")
