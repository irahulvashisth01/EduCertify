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

@student_bp.route("/learn/<int:course_id>")
@student_bp.route("/learn/<int:course_id>/lesson/<int:lesson_id>")
@login_required
@role_required("Student")
def learn(course_id, lesson_id=None):
    """
    Student learning interface.

    Loads:
        - Course
        - Enrollment
        - All lessons
        - Completed lessons
        - Previous/next lesson
        - Module progress
        - All quizzes belonging to the course
        - Best quiz attempt
        - Remaining quiz attempts
        - Question count

    Quizzes are loaded directly using Quiz.CourseID so that
    instructor-created quizzes are visible on the student
    learning page.
    """

    # --------------------------------------------------------
    # CURRENT STUDENT
    # --------------------------------------------------------

    student_id = session.get("user_id")

    if not student_id:
        return redirect(
            url_for("auth.login")
        )

    # --------------------------------------------------------
    # FIND COURSE
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
    # VERIFY ENROLLMENT
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

    # ========================================================
    # LESSONS
    # ========================================================

    all_lessons = []

    for module in course.modules:

        for lesson in module.lessons:
            all_lessons.append(lesson)

    # ========================================================
    # QUIZZES
    # ========================================================
    #
    # IMPORTANT:
    # Instructor-created quizzes are connected to the course
    # through Quiz.CourseID.
    #
    # Therefore we query Quiz directly instead of depending
    # on module.quizzes.
    #
    # This also supports final assessments whose ModuleID
    # can be NULL.
    # ========================================================

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
    # Prepare quiz information for template
    # --------------------------------------------------------

    quiz_data = []

    for quiz in course_quizzes:

        try:
            best_attempt = get_best_attempt(
                student_id,
                quiz.QuizID,
            )
        except Exception:
            best_attempt = None

        try:
            remaining_attempts = get_remaining_attempts(
                student_id,
                quiz.QuizID,
            )
        except Exception:
            remaining_attempts = 0

        # Safely count questions
        try:
            question_count = len(
                quiz.questions
            )
        except Exception:
            question_count = 0

        quiz_data.append(
            {
                "quiz": quiz,

                "best_attempt": best_attempt,

                "remaining": remaining_attempts,

                "question_count": question_count,

                "is_final": bool(
                    getattr(
                        quiz,
                        "IsFinalAssessment",
                        False,
                    )
                ),
            }
        )

    # ========================================================
    # CURRENT LESSON
    # ========================================================

    current_lesson = None

    if lesson_id is not None:

        for lesson in all_lessons:

            if lesson.LessonID == lesson_id:

                current_lesson = lesson
                break

        # ----------------------------------------------------
        # Invalid lesson for this course
        # ----------------------------------------------------

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

    # --------------------------------------------------------
    # Default lesson
    # --------------------------------------------------------

    if current_lesson is None and all_lessons:

        current_lesson = all_lessons[0]

    # ========================================================
    # COMPLETED LESSONS
    # ========================================================

    lesson_ids = [
        lesson.LessonID
        for lesson in all_lessons
    ]

    if lesson_ids:

        completed_ids = get_completed_lesson_ids(
            student_id,
            lesson_ids,
        )

    else:

        completed_ids = set()

    # ========================================================
    # PREVIOUS / NEXT LESSON
    # ========================================================

    previous_lesson = None
    next_lesson = None

    if current_lesson is not None:

        current_index = all_lessons.index(
            current_lesson
        )

        if current_index > 0:

            previous_lesson = (
                all_lessons[
                    current_index - 1
                ]
            )

        if current_index < len(all_lessons) - 1:

            next_lesson = (
                all_lessons[
                    current_index + 1
                ]
            )

    # ========================================================
    # MODULE PROGRESS
    # ========================================================

    module_progress = {}

    for module in course.modules:

        module_progress[
            module.ModuleID
        ] = get_module_progress(
            student_id,
            module,
        )

    # ========================================================
    # OVERALL COURSE PROGRESS
    # ========================================================

    total_lessons = len(
        all_lessons
    )

    completed_lessons = len(
        completed_ids
    )

    if total_lessons > 0:

        course_progress = round(
            (
                completed_lessons
                / total_lessons
            )
            * 100,
            1,
        )

    else:

        course_progress = 0.0

    # ========================================================
    # CHECK WHETHER ALL QUIZZES ARE PASSED
    # ========================================================

    passed_quizzes = 0

    for item in quiz_data:

        best_attempt = item.get(
            "best_attempt"
        )

        if (
            best_attempt is not None
            and getattr(
                best_attempt,
                "Passed",
                False,
            )
        ):

            passed_quizzes += 1

    total_quizzes = len(
        quiz_data
    )

    all_quizzes_passed = (
        total_quizzes > 0
        and passed_quizzes == total_quizzes
    )

    # ========================================================
    # FINAL ASSESSMENT
    # ========================================================

    final_assessments = [
        item
        for item in quiz_data
        if item.get("is_final")
    ]

    final_assessment = (
        final_assessments[0]
        if final_assessments
        else None
    )

    # ========================================================
    # CERTIFICATE STATUS
    # ========================================================

    certificate_eligible = False

    try:

        eligibility = check_eligibility(
            student_id,
            course_id,
        )

        certificate_eligible = bool(
            eligibility.get(
                "eligible",
                False,
            )
        )

    except CertificateError:

        certificate_eligible = False

    except Exception:

        certificate_eligible = False

    # ========================================================
    # RENDER
    # ========================================================

    return render_template(
        "courses/learning.html",

        # Course
        course=course,

        # Enrollment
        enrollment=enrollment,

        # Lessons
        current_lesson=current_lesson,
        completed_ids=completed_ids,
        prev_lesson=previous_lesson,
        next_lesson=next_lesson,

        # Progress
        module_progress=module_progress,
        course_progress=course_progress,
        total_lessons=total_lessons,
        completed_lessons=completed_lessons,

        # ====================================================
        # QUIZZES
        # ====================================================

        course_quizzes=quiz_data,

        # Aliases make the template easier to upgrade
        quizzes=quiz_data,
        quiz_list=quiz_data,

        # Quiz statistics
        total_quizzes=total_quizzes,
        passed_quizzes=passed_quizzes,
        all_quizzes_passed=all_quizzes_passed,

        # Final assessment
        final_assessment=final_assessment,
        final_assessments=final_assessments,

        # Certificate
        certificate_eligible=certificate_eligible,
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
    methods=["GET"],
)
@login_required
@role_required("Student")
def download_certificate(certificate_id):
    """
    Securely download a student's certificate PDF.

    Security:
        - Requires Student login.
        - Allows access only to the certificate owner.
        - Strips directory components from PDFPath.
        - Verifies that the physical PDF exists before download.
        - Logs useful server-side diagnostics without exposing
          filesystem paths to the user.
    """

    student_id = session.get("user_id")

    if not student_id:
        return redirect(
            url_for("auth.login")
        )

    # --------------------------------------------------------
    # Find certificate
    # --------------------------------------------------------

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
            url_for("student.certificates")
        )

    # --------------------------------------------------------
    # Security: certificate ownership
    # --------------------------------------------------------

    if certificate.StudentID != student_id:
        flash(
            "You do not have access to this certificate.",
            "error",
        )

        return redirect(
            url_for("student.certificates")
        )

    # --------------------------------------------------------
    # Certificate storage directory
    # --------------------------------------------------------

    certificate_folder = current_app.config.get(
        "CERTIFICATE_UPLOAD_FOLDER"
    )

    # Safe fallback for development/demo deployments.
    if not certificate_folder:
        certificate_folder = os.path.join(
            current_app.root_path,
            "uploads",
            "certificates",
        )

    certificate_folder = os.path.abspath(
        os.fspath(certificate_folder)
    )

    # --------------------------------------------------------
    # Determine PDF filename
    # --------------------------------------------------------

    stored_pdf_path = getattr(
        certificate,
        "PDFPath",
        None,
    )

    certificate_number = getattr(
        certificate,
        "CertificateNumber",
        None,
    )

    filename = (
        stored_pdf_path
        or (
            f"{certificate_number}.pdf"
            if certificate_number
            else None
        )
    )

    if not filename:
        current_app.logger.error(
            "Certificate %s has no PDF filename.",
            certificate_id,
        )

        flash(
            "Certificate PDF is not available.",
            "error",
        )

        return redirect(
            url_for("student.certificates")
        )

    # Normalize Windows paths and prevent path traversal.
    filename = os.path.basename(
        str(filename)
        .replace("\\", "/")
    )

    # Ensure the final file is a PDF.
    if (
        not filename
        or not filename.lower().endswith(".pdf")
    ):
        current_app.logger.error(
            "Invalid certificate PDF filename for "
            "certificate %s.",
            certificate_id,
        )

        flash(
            "Invalid certificate PDF.",
            "error",
        )

        return redirect(
            url_for("student.certificates")
        )

    # --------------------------------------------------------
    # Verify physical PDF exists
    # --------------------------------------------------------

    pdf_path = os.path.join(
        certificate_folder,
        filename,
    )

    if not os.path.isfile(pdf_path):
        current_app.logger.error(
            "Certificate PDF missing. "
            "CertificateID=%s, Filename=%s, Folder=%s",
            certificate_id,
            filename,
            certificate_folder,
        )

        flash(
            "Certificate PDF was not found on the server. "
            "Please generate the certificate again.",
            "error",
        )

        return redirect(
            url_for("student.certificates")
        )

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    try:
        return send_from_directory(
            certificate_folder,
            filename,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf",
        )

    except Exception:
        current_app.logger.exception(
            "Certificate PDF download failed. "
            "CertificateID=%s",
            certificate_id,
        )

        flash(
            "Unable to download the certificate right now.",
            "error",
        )

        return redirect(
            url_for("student.certificates")
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