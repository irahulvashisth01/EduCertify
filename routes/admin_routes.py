"""
EduCertify — Admin Routes

Platform-wide administration:
- Dashboard statistics
- User management
- Course approval/rejection
- Category management
- Enrollment monitoring
- Certificate management
- Reviews
- Reports
- Platform settings
"""

from datetime import datetime, timedelta

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from database.database import db
from database.models import (
    User,
    Course,
    Category,
    Enrollment,
    Certificate,
    Review,
)

from utils.decorators import login_required, role_required

from services.user_service import (
    toggle_user_active,
    get_all_users,
    UserServiceError,
)

from services.category_service import (
    create_category,
    toggle_category_active,
    CategoryError,
)

from services.certificate_service import (
    revoke_certificate,
    CertificateError,
)


# ============================================================
# BLUEPRINT
# ============================================================

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
)


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@admin_bp.route("/dashboard")
@login_required
@role_required("Admin")
def dashboard():
    """Display administrator dashboard and platform statistics."""

    stats = {
        "total_users": User.query.count(),

        "students": User.query.filter_by(
            Role="Student"
        ).count(),

        "instructors": User.query.filter_by(
            Role="Instructor"
        ).count(),

        "published_courses": Course.query.filter_by(
            Status="Published"
        ).count(),

        "pending_courses": Course.query.filter_by(
            Status="Pending"
        ).count(),

        "enrollments": Enrollment.query.count(),

        "certificates": Certificate.query.count(),
    }

    recent_courses = (
        Course.query
        .order_by(Course.CreatedAt.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_courses=recent_courses,
    )


# ============================================================
# USER MANAGEMENT
# ============================================================

@admin_bp.route("/users")
@login_required
@role_required("Admin")
def users():
    """Display all users with optional role filtering."""

    role_filter = request.args.get("role", "").strip()

    user_list = get_all_users(
        role_filter if role_filter else None
    )

    return render_template(
        "admin/users.html",
        users=user_list,
        role_filter=role_filter,
    )


@admin_bp.route(
    "/users/<int:user_id>/toggle",
    methods=["POST"],
)
@login_required
@role_required("Admin")
def toggle_user(user_id):
    """Activate or deactivate a user."""

    try:
        user = toggle_user_active(user_id)

        status = (
            "activated"
            if user.IsActive
            else "deactivated"
        )

        flash(
            f"{user.FullName} has been {status}.",
            "success",
        )

    except UserServiceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("admin.users"))


# ============================================================
# COURSE MANAGEMENT
# ============================================================

@admin_bp.route("/courses")
@login_required
@role_required("Admin")
def courses():
    """Display courses with optional status filtering."""

    status_filter = request.args.get(
        "status",
        "",
    ).strip()

    query = Course.query

    if status_filter:
        query = query.filter_by(
            Status=status_filter
        )

    course_list = (
        query
        .order_by(Course.CreatedAt.desc())
        .all()
    )

    return render_template(
        "admin/courses.html",
        courses=course_list,
        status_filter=status_filter,
    )


@admin_bp.route(
    "/courses/<int:course_id>/approve",
    methods=["POST"],
)
@login_required
@role_required("Admin")
def approve_course(course_id):
    """Approve a course and publish it."""

    course = Course.query.get_or_404(course_id)

    course.Status = "Published"
    course.RejectionReason = None

    try:
        db.session.commit()

        flash(
            f"'{course.Title}' has been published.",
            "success",
        )

    except Exception:
        db.session.rollback()

        flash(
            "Unable to publish the course. Please try again.",
            "error",
        )

    return redirect(url_for("admin.courses"))


@admin_bp.route(
    "/courses/<int:course_id>/reject",
    methods=["POST"],
)
@login_required
@role_required("Admin")
def reject_course(course_id):
    """Reject a course and store administrator feedback."""

    course = Course.query.get_or_404(course_id)

    reason = (
        request.form.get("reason")
        or "Did not meet quality guidelines."
    ).strip()

    course.Status = "Rejected"
    course.RejectionReason = reason

    try:
        db.session.commit()

        flash(
            f"'{course.Title}' has been rejected.",
            "info",
        )

    except Exception:
        db.session.rollback()

        flash(
            "Unable to reject the course. Please try again.",
            "error",
        )

    return redirect(url_for("admin.courses"))


# ============================================================
# CATEGORY MANAGEMENT
# ============================================================

@admin_bp.route(
    "/categories",
    methods=["GET", "POST"],
)
@login_required
@role_required("Admin")
def categories():
    """Create and list course categories."""

    if request.method == "POST":

        name = (
            request.form.get("name")
            or ""
        ).strip()

        description = (
            request.form.get("description")
            or ""
        ).strip()

        try:
            create_category(
                name,
                description,
            )

            flash(
                "Category created successfully.",
                "success",
            )

        except CategoryError as exc:
            flash(
                str(exc),
                "error",
            )

        return redirect(
            url_for("admin.categories")
        )

    category_list = (
        Category.query
        .order_by(Category.Name.asc())
        .all()
    )

    return render_template(
        "admin/categories.html",
        categories=category_list,
    )


@admin_bp.route(
    "/categories/<int:category_id>/toggle",
    methods=["POST"],
)
@login_required
@role_required("Admin")
def toggle_category(category_id):
    """Activate or deactivate a category."""

    try:
        toggle_category_active(
            category_id
        )

        flash(
            "Category status updated.",
            "success",
        )

    except CategoryError as exc:
        flash(
            str(exc),
            "error",
        )

    return redirect(
        url_for("admin.categories")
    )


# ============================================================
# ENROLLMENT MANAGEMENT
# ============================================================

@admin_bp.route("/enrollments")
@login_required
@role_required("Admin")
def enrollments():
    """Display recent enrollments."""

    enrollment_list = (
        Enrollment.query
        .order_by(
            Enrollment.EnrollmentDate.desc()
        )
        .limit(200)
        .all()
    )

    return render_template(
        "admin/enrollments.html",
        enrollments=enrollment_list,
    )


# ============================================================
# CERTIFICATE MANAGEMENT
# ============================================================

@admin_bp.route("/certificates")
@login_required
@role_required("Admin")
def certificates():
    """Display issued certificates."""

    certificate_list = (
        Certificate.query
        .order_by(
            Certificate.IssueDate.desc()
        )
        .all()
    )

    return render_template(
        "admin/certificates.html",
        certificates=certificate_list,
    )


@admin_bp.route(
    "/certificates/<int:certificate_id>/revoke",
    methods=["POST"],
)
@login_required
@role_required("Admin")
def revoke_certificate_view(
    certificate_id,
):
    """Revoke an issued certificate."""

    try:
        certificate = revoke_certificate(
            certificate_id
        )

        flash(
            (
                f"Certificate "
                f"{certificate.CertificateNumber} "
                f"has been revoked."
            ),
            "info",
        )

    except CertificateError as exc:
        flash(
            str(exc),
            "error",
        )

    return redirect(
        url_for("admin.certificates")
    )


# ============================================================
# REVIEWS
# ============================================================

@admin_bp.route("/reviews")
@login_required
@role_required("Admin")
def reviews():
    """Display recent course reviews."""

    review_list = (
        Review.query
        .order_by(
            Review.CreatedAt.desc()
        )
        .limit(200)
        .all()
    )

    return render_template(
        "admin/reports.html",
        reviews=review_list,
    )


# ============================================================
# ADMIN REPORTS
# ============================================================

@admin_bp.route("/reports")
@login_required
@role_required("Admin")
def reports():
    """Display platform activity reports."""

    thirty_days_ago = (
        datetime.utcnow()
        - timedelta(days=30)
    )

    new_users_30d = (
        User.query
        .filter(
            User.CreatedAt >= thirty_days_ago
        )
        .count()
    )

    new_enrollments_30d = (
        Enrollment.query
        .filter(
            Enrollment.EnrollmentDate
            >= thirty_days_ago
        )
        .count()
    )

    new_certificates_30d = (
        Certificate.query
        .filter(
            Certificate.IssueDate
            >= thirty_days_ago
        )
        .count()
    )

    top_courses = (
        Course.query
        .filter_by(
            Status="Published"
        )
        .order_by(
            Course.CreatedAt.desc()
        )
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


# ============================================================
# ADMIN SETTINGS
# ============================================================

@admin_bp.route("/settings")
@login_required
@role_required("Admin")
def settings():
    """Display administrator settings."""

    return render_template(
        "admin/settings.html"
    )