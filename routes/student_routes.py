"""
Student-facing routes: dashboard, my courses, learning interface,
quiz taking, certificates, profile.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, send_from_directory

from database.database import db
from database.models import Course, Enrollment, Lesson, Module, Quiz, Certificate, User, Notification
from utils.decorators import login_required, role_required
from services.enrollment_service import enroll_student, get_enrollment, EnrollmentError
from services.progress_service import mark_lesson_complete, get_completed_lesson_ids, get_module_progress
from services.certificate_service import check_eligibility, issue_certificate, CertificateError
from services.quiz_service import get_remaining_attempts, get_best_attempt

student_bp = Blueprint("student", __name__, url_prefix="/student")


@student_bp.route("/dashboard")
@login_required
@role_required("Student")
def dashboard():
    student_id = session["user_id"]
    enrollments = Enrollment.query.filter_by(StudentID=student_id).all()
    certificates = Certificate.query.filter_by(StudentID=student_id).all()

    completed = [e for e in enrollments if e.Status == "Completed"]
    active = [e for e in enrollments if e.Status == "Active"]

    from database.models import QuizAttempt
    attempts = QuizAttempt.query.filter_by(StudentID=student_id).filter(QuizAttempt.CompletedAt.isnot(None)).all()
    avg_quiz_score = round(sum(a.Percentage for a in attempts) / len(attempts), 1) if attempts else 0

    recent_notifications = (
        Notification.query.filter_by(UserID=student_id).order_by(Notification.CreatedAt.desc()).limit(5).all()
    )

    return render_template(
        "student/dashboard.html",
        enrollments=enrollments,
        completed_count=len(completed),
        active_count=len(active),
        certificate_count=len(certificates),
        avg_quiz_score=avg_quiz_score,
        recent_notifications=recent_notifications,
    )


@student_bp.route("/courses")
@login_required
@role_required("Student")
def courses():
    student_id = session["user_id"]
    status_filter = request.args.get("status", "all")
    query = Enrollment.query.filter_by(StudentID=student_id)
    if status_filter != "all":
        query = query.filter_by(Status=status_filter.capitalize())
    enrollments = query.order_by(Enrollment.EnrollmentDate.desc()).all()
    return render_template("student/courses.html", enrollments=enrollments, status_filter=status_filter)


@student_bp.route("/courses/<int:course_id>/enroll", methods=["POST"])
@login_required
@role_required("Student")
def enroll(course_id):
    try:
        enroll_student(session["user_id"], course_id)
        flash("Enrollment successful! Start learning now.", "success")
    except EnrollmentError as e:
        flash(str(e), "error")

    course = Course.query.get_or_404(course_id)
    return redirect(url_for("courses.details", slug=course.Slug))


@student_bp.route("/learn/<int:course_id>")
@student_bp.route("/learn/<int:course_id>/lesson/<int:lesson_id>")
@login_required
@role_required("Student")
def learn(course_id, lesson_id=None):
    student_id = session["user_id"]
    course = Course.query.get_or_404(course_id)
    enrollment = get_enrollment(student_id, course_id)

    if not enrollment:
        flash("You need to enroll in this course first.", "warning")
        return redirect(url_for("courses.details", slug=course.Slug))

    all_lessons = [lesson for module in course.modules for lesson in module.lessons]
    if not all_lessons:
        flash("This course doesn't have any lessons yet.", "info")
        return redirect(url_for("student.courses"))

    current_lesson = None
    if lesson_id:
        current_lesson = Lesson.query.get(lesson_id)
    if not current_lesson:
        current_lesson = all_lessons[0]

    lesson_ids = [l.LessonID for l in all_lessons]
    completed_ids = get_completed_lesson_ids(student_id, lesson_ids)

    # Determine previous/next lesson for navigation
    current_index = all_lessons.index(current_lesson) if current_lesson in all_lessons else 0
    prev_lesson = all_lessons[current_index - 1] if current_index > 0 else None
    next_lesson = all_lessons[current_index + 1] if current_index < len(all_lessons) - 1 else None

    module_progress = {m.ModuleID: get_module_progress(student_id, m) for m in course.modules}

    return render_template(
        "courses/learning.html",
        course=course,
        current_lesson=current_lesson,
        completed_ids=completed_ids,
        prev_lesson=prev_lesson,
        next_lesson=next_lesson,
        enrollment=enrollment,
        module_progress=module_progress,
    )


@student_bp.route("/progress")
@login_required
@role_required("Student")
def progress():
    student_id = session["user_id"]
    enrollments = Enrollment.query.filter_by(StudentID=student_id).all()
    return render_template("student/progress.html", enrollments=enrollments)


@student_bp.route("/quizzes")
@login_required
@role_required("Student")
def quizzes():
    student_id = session["user_id"]
    enrollments = Enrollment.query.filter_by(StudentID=student_id).all()
    course_ids = [e.CourseID for e in enrollments]

    quiz_list = Quiz.query.filter(Quiz.CourseID.in_(course_ids)).all() if course_ids else []

    quiz_data = []
    for quiz in quiz_list:
        best = get_best_attempt(student_id, quiz.QuizID)
        remaining = get_remaining_attempts(student_id, quiz.QuizID)
        quiz_data.append({"quiz": quiz, "best_attempt": best, "remaining": remaining})

    return render_template("student/quiz.html", quiz_list=quiz_data, quiz=None)


@student_bp.route("/quiz/<int:quiz_id>")
@login_required
@role_required("Student")
def quiz_page(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    student_id = session["user_id"]

    enrollment = get_enrollment(student_id, quiz.CourseID)
    if not enrollment:
        flash("You need to be enrolled in this course to take the quiz.", "warning")
        return redirect(url_for("courses.details", slug=quiz.course.Slug))

    remaining = get_remaining_attempts(student_id, quiz_id)
    best_attempt = get_best_attempt(student_id, quiz_id)

    return render_template(
        "student/quiz.html",
        quiz=quiz,
        remaining_attempts=remaining,
        best_attempt=best_attempt,
    )


@student_bp.route("/certificates")
@login_required
@role_required("Student")
def certificates():
    student_id = session["user_id"]
    certs = Certificate.query.filter_by(StudentID=student_id).order_by(Certificate.IssueDate.desc()).all()

    # Also show courses that are eligible but not yet issued
    eligible_courses = []
    completed_enrollments = Enrollment.query.filter_by(StudentID=student_id, Status="Completed").all()
    issued_course_ids = {c.CourseID for c in certs}
    for enrollment in completed_enrollments:
        if enrollment.CourseID not in issued_course_ids:
            try:
                elig = check_eligibility(student_id, enrollment.CourseID)
                if elig["eligible"]:
                    eligible_courses.append(enrollment.course)
            except CertificateError:
                pass

    return render_template("student/certificates.html", certificates=certs, eligible_courses=eligible_courses)


@student_bp.route("/certificates/<int:course_id>/generate", methods=["POST"])
@login_required
@role_required("Student")
def generate_certificate(course_id):
    student_id = session["user_id"]
    try:
        cert = issue_certificate(student_id, course_id, current_app.config)
        flash(f"Certificate {cert.CertificateNumber} generated successfully!", "success")
    except CertificateError as e:
        flash(str(e), "error")
    return redirect(url_for("student.certificates"))


@student_bp.route("/certificates/<int:certificate_id>/download")
@login_required
@role_required("Student")
def download_certificate(certificate_id):
    cert = Certificate.query.get_or_404(certificate_id)
    if cert.StudentID != session["user_id"]:
        flash("You do not have access to this certificate.", "error")
        return redirect(url_for("student.certificates"))
    if not cert.PDFPath:
        flash("Certificate PDF is not available.", "error")
        return redirect(url_for("student.certificates"))
    return send_from_directory(current_app.config["CERTIFICATE_UPLOAD_FOLDER"], cert.PDFPath, as_attachment=True)


@student_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("Student")
def profile():
    user = User.query.get(session["user_id"])
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        if full_name and len(full_name) >= 2:
            user.FullName = full_name
            session["user_name"] = full_name
            db.session.commit()
            flash("Profile updated successfully.", "success")
        else:
            flash("Please enter a valid name.", "error")
        return redirect(url_for("student.profile"))
    return render_template("student/profile.html", user=user)
