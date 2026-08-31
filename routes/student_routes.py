"""
EduCertify — Student Routes

Student-facing functionality:

- Dashboard
- Enrolled courses
- Course enrollment
- Learning interface
- Lesson progress
- Quizzes
- Certificates
- Certificate downloads
- Student profile
"""

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from database.database import db
from database.models import (
    Certificate,
    Course,
    Enrollment,
    Lesson,
    Module,
    Notification,
    Quiz,
    QuizAttempt,
    User,
)

from utils.decorators import (
    login_required,
    role_required,
)

from services.enrollment_service import (
    enroll_student,
    get_enrollment,
    EnrollmentError,
)

from services.progress_service import (
    mark_lesson_complete,
    get_completed_lesson_ids,
    get_module_progress,
)

from services.certificate_service import (
    check_eligibility,
    issue_certificate,
    CertificateError,
)

from services.quiz_service import (
    get_remaining_attempts,
    get_best_attempt,
)


# ============================================================
# BLUEPRINT
# ============================================================

student_bp = Blueprint(
    "student",
    __name__,
    url_prefix="/student",
)


# ============================================================
# STUDENT DASHBOARD
# ============================================================

@student_bp.route("/dashboard")
@login_required
@role_required("Student")
def dashboard():
    """
    Display student dashboard statistics.
    """

    student_id = session.get("user_id")

    if not student_id:
        return redirect(
            url_for("auth.login")
        )

    # --------------------------------------------------------
    # Enrollments
    # --------------------------------------------------------

    enrollments = (
        Enrollment.query
        .filter_by(
            StudentID=student_id
        )
        .order_by(
            Enrollment.EnrollmentDate.desc()
        )
        .all()
    )

    completed = [
        enrollment
        for enrollment in enrollments
        if enrollment.Status == "Completed"
    ]

    active = [
        enrollment
        for enrollment in enrollments
        if enrollment.Status == "Active"
    ]

    # --------------------------------------------------------
    # Certificates
    # --------------------------------------------------------

    certificates = (
        Certificate.query
        .filter_by(
            StudentID=student_id
        )
        .order_by(
            Certificate.IssueDate.desc()
        )
        .all()
    )

    # --------------------------------------------------------
    # Completed quiz attempts
    # --------------------------------------------------------

    attempts = (
        QuizAttempt.query
        .filter_by(
            StudentID=student_id
        )
        .filter(
            QuizAttempt.CompletedAt.isnot(None)
        )
        .all()
    )

    percentages = [
        attempt.Percentage
        for attempt in attempts
        if attempt.Percentage is not None
    ]

    avg_quiz_score = (
        round(
            sum(percentages) / len(percentages),
            1,
        )
        if percentages
        else 0
    )

    # --------------------------------------------------------
    # Notifications
    # --------------------------------------------------------

    recent_notifications = (
        Notification.query
        .filter_by(
            UserID=student_id
        )
        .order_by(
            Notification.CreatedAt.desc()
        )
        .limit(5)
        .all()
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


# ============================================================
# MY COURSES
# ============================================================

@student_bp.route("/courses")
@login_required
@role_required("Student")
def courses():
    """
    Display courses enrolled by the current student.
    """

    student_id = session.get("user_id")

    status_filter = (
        request.args.get(
            "status",
            "all",
        )
        .strip()
        .lower()
    )

    query = (
        Enrollment.query
        .filter_by(
            StudentID=student_id
        )
    )

    allowed_statuses = {
        "active": "Active",
        "completed": "Completed",
        "cancelled": "Cancelled",
        "pending": "Pending",
    }

    if status_filter in allowed_statuses:

        query = query.filter_by(
            Status=allowed_statuses[
                status_filter
            ]
        )

    elif status_filter != "all":

        status_filter = "all"

    enrollments = (
        query
        .order_by(
            Enrollment.EnrollmentDate.desc()
        )
        .all()
    )

    return render_template(
        "student/courses.html",
        enrollments=enrollments,
        status_filter=status_filter,
    )


# ============================================================
# COURSE ENROLLMENT
# ============================================================

@student_bp.route(
    "/courses/<int:course_id>/enroll",
    methods=["POST"],
)
@login_required
@role_required("Student")
def enroll(course_id):
    """
    Enroll the current student in a course.
    """

    student_id = session.get("user_id")

    course = db.session.get(
        Course,
        course_id,
    )

    if course is None:
        flash(
            "Course not found.",
            "error",
        )

        return redirect(
            url_for("courses.index")
        )

    if course.Status != "Published":

        flash(
            "This course is not available for enrollment.",
            "error",
        )

        return redirect(
            url_for(
                "courses.details",
                slug=course.Slug,
            )
        )

    try:

        enroll_student(
            student_id,
            course_id,
        )

        flash(
            "Enrollment successful! Start learning now.",
            "success",
        )

    except EnrollmentError as exc:

        flash(
            str(exc),
            "error",
        )

    return redirect(
        url_for(
            "courses.details",
            slug=course.Slug,
        )
    )


# ============================================================
# LEARNING INTERFACE
# ============================================================

@student_bp.route(
    "/learn/<int:course_id>",
)
@student_bp.route(
    "/learn/<int:course_id>/lesson/<int:lesson_id>",
)
@login_required
@role_required("Student")
def learn(
    course_id,
    lesson_id=None,
):
    """
    Display the learning interface for an enrolled course.

    This route loads both lessons and quizzes for the course.
    Quizzes are fetched directly by Quiz.CourseID so that
    instructor-created quizzes are available on the student
    learning page.

    Template variables added for quiz support:
        course_quizzes:
            A list containing the quiz object, best attempt,
            remaining attempts, and question count.
    """

    student_id = session.get("user_id")

    # --------------------------------------------------------
    # Validate student session
    # --------------------------------------------------------

    if not student_id:
        return redirect(
            url_for("auth.login")
        )

    # --------------------------------------------------------
    # Find course
    # --------------------------------------------------------

    course = db.session.get(
        Course,
        course_id,
    )

    if course is None:

        flash(
            "Course not found.",
            "error",
        )

        return redirect(
            url_for("student.courses")
        )

    # --------------------------------------------------------
    # Verify enrollment
    # --------------------------------------------------------

    enrollment = get_enrollment(
        student_id,
        course_id,
    )

    if enrollment is None:

        flash(
            "You need to enroll in this course first.",
            "warning",
        )

        return redirect(
            url_for(
                "courses.details",
                slug=course.Slug,
            )
        )

    # --------------------------------------------------------
    # Collect all lessons
    # --------------------------------------------------------

    all_lessons = []

    for module in course.modules:

        for lesson in module.lessons:
            all_lessons.append(lesson)

    # --------------------------------------------------------
    # Collect ALL course quizzes
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # Instructor quizzes are linked to the course through
    # Quiz.CourseID. Do not depend on module.quizzes here.
    #
    # This also supports final assessments whose ModuleID may
    # be NULL.
    # --------------------------------------------------------

    course_quizzes = (
        Quiz.query
        .filter(
            Quiz.CourseID == course_id
        )
        .order_by(
            Quiz.IsFinalAssessment.asc(),
            Quiz.QuizID.asc(),
        )
        .all()
    )

    # --------------------------------------------------------
    # Build student-safe quiz information
    # --------------------------------------------------------

    quiz_data = []

    for quiz in course_quizzes:

        best_attempt = get_best_attempt(
            student_id,
            quiz.QuizID,
        )

        remaining_attempts = get_remaining_attempts(
            student_id,
            quiz.QuizID,
        )

        quiz_data.append(
            {
                "quiz": quiz,
                "best_attempt": best_attempt,
                "remaining": remaining_attempts,
                "question_count": len(
                    quiz.questions
                ),
            }
        )

    # --------------------------------------------------------
    # Current lesson
    # --------------------------------------------------------
    #
    # A course may contain quizzes even when there are no
    # lessons. Therefore, do NOT redirect just because
    # all_lessons is empty.
    # --------------------------------------------------------

    current_lesson = None

    if lesson_id is not None:

        for lesson in all_lessons:

            if lesson.LessonID == lesson_id:

                current_lesson = lesson
                break

        # Student attempted to access a lesson that
        # does not belong to this course.
        if current_lesson is None:

            flash(
                "The requested lesson was not found in this course.",
                "error",
            )

            return redirect(
                url_for(
                    "student.learn",
                    course_id=course_id,
                )
            )

    if current_lesson is None and all_lessons:

        current_lesson = all_lessons[0]

    # --------------------------------------------------------
    # Completed lessons
    # --------------------------------------------------------

    lesson_ids = [
        lesson.LessonID
        for lesson in all_lessons
    ]

    completed_ids = (
        get_completed_lesson_ids(
            student_id,
            lesson_ids,
        )
        if lesson_ids
        else set()
    )

    # --------------------------------------------------------
    # Previous / next lesson
    # --------------------------------------------------------

    previous_lesson = None
    next_lesson = None

    if current_lesson is not None:

        current_index = all_lessons.index(
            current_lesson
        )

        previous_lesson = (
            all_lessons[current_index - 1]
            if current_index > 0
            else None
        )

        next_lesson = (
            all_lessons[current_index + 1]
            if current_index < len(all_lessons) - 1
            else None
        )

    # --------------------------------------------------------
    # Module progress
    # --------------------------------------------------------

    module_progress = {
        module.ModuleID: get_module_progress(
            student_id,
            module,
        )
        for module in course.modules
    }

    # --------------------------------------------------------
    # Render learning interface
    # --------------------------------------------------------

    return render_template(
        "courses/learning.html",
        course=course,
        current_lesson=current_lesson,
        completed_ids=completed_ids,
        prev_lesson=previous_lesson,
        next_lesson=next_lesson,
        enrollment=enrollment,
        module_progress=module_progress,

        # ----------------------------------------------------
        # NEW:
        # Send instructor-created quizzes to the student page.
        # ----------------------------------------------------
        course_quizzes=quiz_data,
    )



# ============================================================
# PROGRESS
# ============================================================

@student_bp.route("/progress")
@login_required
@role_required("Student")
def progress():
    """
    Display learning progress.
    """

    student_id = session.get(
        "user_id"
    )

    enrollments = (
        Enrollment.query
        .filter_by(
            StudentID=student_id
        )
        .order_by(
            Enrollment.EnrollmentDate.desc()
        )
        .all()
    )

    return render_template(
        "student/progress.html",
        enrollments=enrollments,
    )


# ============================================================
# QUIZZES
# ============================================================

@student_bp.route("/quizzes")
@login_required
@role_required("Student")
def quizzes():
    """
    Display quizzes belonging to courses
    in which the student is enrolled.
    """

    student_id = session.get(
        "user_id"
    )

    enrollments = (
        Enrollment.query
        .filter_by(
            StudentID=student_id
        )
        .all()
    )

    course_ids = [
        enrollment.CourseID
        for enrollment in enrollments
    ]

    if not course_ids:

        return render_template(
            "student/quiz.html",
            quiz_list=[],
            quiz=None,
        )

    quiz_list = (
        Quiz.query
        .filter(
            Quiz.CourseID.in_(course_ids)
        )
        .order_by(
            Quiz.QuizID.desc()
        )
        .all()
    )

    quiz_data = []

    for quiz in quiz_list:

        best_attempt = get_best_attempt(
            student_id,
            quiz.QuizID,
        )

        remaining_attempts = (
            get_remaining_attempts(
                student_id,
                quiz.QuizID,
            )
        )

        quiz_data.append(
            {
                "quiz": quiz,
                "best_attempt": best_attempt,
                "remaining": remaining_attempts,
            }
        )

    return render_template(
        "student/quiz.html",
        quiz_list=quiz_data,
        quiz=None,
    )


# ============================================================
# QUIZ PAGE
# ============================================================

@student_bp.route(
    "/quiz/<int:quiz_id>",
)
@login_required
@role_required("Student")
def quiz_page(quiz_id):
    """
    Display a quiz for the enrolled student.
    """

    student_id = session.get(
        "user_id"
    )

    quiz = db.session.get(
        Quiz,
        quiz_id,
    )

    if quiz is None:

        flash(
            "Quiz not found.",
            "error",
        )

        return redirect(
            url_for("student.quizzes")
        )

    # --------------------------------------------------------
    # Verify enrollment
    # --------------------------------------------------------

    enrollment = get_enrollment(
        student_id,
        quiz.CourseID,
    )

    if enrollment is None:

        flash(
            "You need to be enrolled in this course to take the quiz.",
            "warning",
        )

        return redirect(
            url_for(
                "courses.details",
                slug=quiz.course.Slug,
            )
        )

    remaining = get_remaining_attempts(
        student_id,
        quiz_id,
    )

    best_attempt = get_best_attempt(
        student_id,
        quiz_id,
    )

    return render_template(
        "student/quiz.html",
        quiz=quiz,
        remaining_attempts=remaining,
        best_attempt=best_attempt,
    )


# ============================================================
# CERTIFICATES
# ============================================================

@student_bp.route("/certificates")
@login_required
@role_required("Student")
def certificates():
    """
    Display issued certificates and courses
    eligible for certificate generation.
    """

    student_id = session.get(
        "user_id"
    )

    certs = (
        Certificate.query
        .filter_by(
            StudentID=student_id
        )
        .order_by(
            Certificate.IssueDate.desc()
        )
        .all()
    )

    completed_enrollments = (
        Enrollment.query
        .filter_by(
            StudentID=student_id,
            Status="Completed",
        )
        .all()
    )

    issued_course_ids = {
        certificate.CourseID
        for certificate in certs
    }

    eligible_courses = []

    for enrollment in completed_enrollments:

        if enrollment.CourseID in issued_course_ids:
            continue

        try:

            eligibility = check_eligibility(
                student_id,
                enrollment.CourseID,
            )

            if eligibility.get(
                "eligible",
                False,
            ):

                if enrollment.course:
                    eligible_courses.append(
                        enrollment.course
                    )

        except CertificateError:
            continue

    return render_template(
        "student/certificates.html",
        certificates=certs,
        eligible_courses=eligible_courses,
    )


# ============================================================
# GENERATE CERTIFICATE
# ============================================================

@student_bp.route(
    "/certificates/<int:course_id>/generate",
    methods=["POST"],
)
@login_required
@role_required("Student")
def generate_certificate(course_id):
    """
    Generate a certificate for a completed course.
    """

    student_id = session.get(
        "user_id"
    )

    try:

        certificate = issue_certificate(
            student_id,
            course_id,
            current_app.config,
        )

        flash(
            (
                f"Certificate "
                f"{certificate.CertificateNumber} "
                f"generated successfully!"
            ),
            "success",
        )

    except CertificateError as exc:

        flash(
            str(exc),
            "error",
        )

    except Exception:

        db.session.rollback()

        flash(
            "Unable to generate certificate.",
            "error",
        )

    return redirect(
        url_for(
            "student.certificates"
        )
    )


# ============================================================
# DOWNLOAD CERTIFICATE
# ============================================================

@student_bp.route(
    "/certificates/<int:certificate_id>/download",
)
@login_required
@role_required("Student")
def download_certificate(certificate_id):
    """
    Download a certificate PDF belonging to the
    currently authenticated student.
    """

    student_id = session.get(
        "user_id"
    )

    certificate = db.session.get(
        Certificate,
        certificate_id,
    )

    if certificate is None:

        flash(
            "Certificate not found.",
            "error",
        )

        return redirect(
            url_for(
                "student.certificates"
            )
        )

    # --------------------------------------------------------
    # Ownership check
    # --------------------------------------------------------

    if certificate.StudentID != student_id:

        flash(
            "You do not have access to this certificate.",
            "error",
        )

        return redirect(
            url_for(
                "student.certificates"
            )
        )

    # --------------------------------------------------------
    # PDF availability
    # --------------------------------------------------------

    if not certificate.PDFPath:

        flash(
            "Certificate PDF is not available.",
            "error",
        )

        return redirect(
            url_for(
                "student.certificates"
            )
        )

    # --------------------------------------------------------
    # Prevent path traversal
    # --------------------------------------------------------

    filename = (
        certificate.PDFPath
        .replace("\\", "/")
        .split("/")[-1]
    )

    if not filename:

        flash(
            "Invalid certificate file.",
            "error",
        )

        return redirect(
            url_for(
                "student.certificates"
            )
        )

    return send_from_directory(
        current_app.config[
            "CERTIFICATE_UPLOAD_FOLDER"
        ],
        filename,
        as_attachment=True,
    )


# ============================================================
# STUDENT PROFILE
# ============================================================

@student_bp.route(
    "/profile",
    methods=["GET", "POST"],
)
@login_required
@role_required("Student")
def profile():
    """
    Display and update the student's profile.
    """

    student_id = session.get(
        "user_id"
    )

    user = db.session.get(
        User,
        student_id,
    )

    if user is None:

        session.clear()

        flash(
            "Your account could not be found.",
            "error",
        )

        return redirect(
            url_for("auth.login")
        )

    if request.method == "POST":

        full_name = (
            request.form.get(
                "full_name",
                "",
            )
            .strip()
        )

        if not full_name:

            flash(
                "Please enter your full name.",
                "error",
            )

        elif len(full_name) < 2:

            flash(
                "Name must contain at least 2 characters.",
                "error",
            )

        elif len(full_name) > 150:

            flash(
                "Name is too long.",
                "error",
            )

        else:

            try:

                user.FullName = full_name

                db.session.commit()

                session["user_name"] = (
                    full_name
                )

                flash(
                    "Profile updated successfully.",
                    "success",
                )

            except Exception:

                db.session.rollback()

                flash(
                    "Unable to update your profile.",
                    "error",
                )

        return redirect(
            url_for(
                "student.profile"
            )
        )

    return render_template(
        "student/profile.html",
        user=user,
    )