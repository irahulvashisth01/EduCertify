"""
EduCertify — REST API Routes

JSON API endpoints consumed by frontend fetch() calls.

Every response follows the structure:

{
    "success": bool,
    "message": str,
    ...
}

API Prefix:
    /api
"""

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
    session,
)

from database.database import db

from database.models import (
    Lesson,
    Course,
    Quiz,
)

from utils.decorators import (
    login_required,
    role_required,
)

from utils.helpers import json_response

from services.progress_service import (
    mark_lesson_complete,
)

from services.quiz_service import (
    start_attempt,
    submit_attempt,
    get_quiz_for_taking,
    QuizError,
)

from services.certificate_service import (
    verify_certificate,
    issue_certificate_if_eligible,
    CertificateError,
)


# ============================================================
# BLUEPRINT
# ============================================================

api_bp = Blueprint(
    "api",
    __name__,
    url_prefix="/api",
)


# ============================================================
# COURSES API
# ============================================================

@api_bp.route(
    "/courses",
    methods=["GET"],
)
def api_courses():
    """
    Return all published courses.

    GET /api/courses
    """

    courses = (
        Course.query
        .filter_by(Status="Published")
        .order_by(Course.CourseID.desc())
        .limit(50)
        .all()
    )

    data = []

    for course in courses:

        data.append(
            {
                "CourseID": course.CourseID,
                "Title": course.Title,
                "Slug": course.Slug,
                "Level": course.Level,
                "Price": course.Price,
            }
        )

    return jsonify(
        json_response(
            True,
            "Courses retrieved successfully.",
            courses=data,
        )
    )


# ============================================================
# COURSE DETAIL API
# ============================================================

@api_bp.route(
    "/courses/<int:course_id>",
    methods=["GET"],
)
def api_course_detail(course_id):
    """
    Return details for a single course.

    GET /api/courses/<course_id>
    """

    course = db.session.get(
        Course,
        course_id,
    )

    if course is None:

        return (
            jsonify(
                json_response(
                    False,
                    "Course not found.",
                )
            ),
            404,
        )

    return jsonify(
        json_response(
            True,
            "Course retrieved successfully.",
            course={
                "CourseID": course.CourseID,
                "Title": course.Title,
                "Slug": course.Slug,
                "Level": course.Level,
                "Price": course.Price,
                "TotalLessons": course.total_lessons,
            },
        )
    )


# ============================================================
# LESSON PROGRESS API
# ============================================================

@api_bp.route(
    "/progress/<int:lesson_id>",
    methods=["POST"],
)
@login_required
@role_required("Student")
def api_mark_progress(lesson_id):
    """
    Mark a lesson as completed for the logged-in student.

    POST /api/progress/<lesson_id>
    """

    # --------------------------------------------------------
    # Find lesson
    # --------------------------------------------------------

    lesson = db.session.get(
        Lesson,
        lesson_id,
    )

    if lesson is None:

        return (
            jsonify(
                json_response(
                    False,
                    "Lesson not found.",
                )
            ),
            404,
        )

    # --------------------------------------------------------
    # Current student
    # --------------------------------------------------------

    user_id = session.get(
        "user_id"
    )

    if not user_id:

        return (
            jsonify(
                json_response(
                    False,
                    "User session not found.",
                )
            ),
            401,
        )

    # --------------------------------------------------------
    # Mark lesson completed
    # --------------------------------------------------------

    try:

        new_progress = mark_lesson_complete(
            user_id,
            lesson_id,
        )

        return jsonify(
            json_response(
                True,
                "Progress updated successfully.",
                progress=new_progress,
            )
        )

    except ValueError as exc:

        return (
            jsonify(
                json_response(
                    False,
                    str(exc),
                )
            ),
            400,
        )

    except Exception:

        db.session.rollback()

        return (
            jsonify(
                json_response(
                    False,
                    "Unable to update progress.",
                )
            ),
            500,
        )


# ============================================================
# START QUIZ API
# ============================================================

@api_bp.route(
    "/quizzes/<int:quiz_id>/start",
    methods=["POST"],
)
@login_required
@role_required("Student")
def api_start_quiz(quiz_id):
    """
    Start a quiz attempt.

    POST /api/quizzes/<quiz_id>/start
    """

    # --------------------------------------------------------
    # Current student
    # --------------------------------------------------------

    user_id = session.get(
        "user_id"
    )

    if not user_id:

        return (
            jsonify(
                json_response(
                    False,
                    "User session not found.",
                )
            ),
            401,
        )

    try:

        # ----------------------------------------------------
        # Start attempt
        # ----------------------------------------------------

        attempt = start_attempt(
            user_id,
            quiz_id,
        )

        # ----------------------------------------------------
        # Load quiz questions
        # ----------------------------------------------------

        quiz, questions = get_quiz_for_taking(
            quiz_id
        )

    except QuizError as exc:

        return (
            jsonify(
                json_response(
                    False,
                    str(exc),
                )
            ),
            400,
        )

    except Exception:

        db.session.rollback()

        return (
            jsonify(
                json_response(
                    False,
                    "Unable to start quiz.",
                )
            ),
            500,
        )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return jsonify(
        json_response(
            True,
            "Quiz started successfully.",
            attempt_id=attempt.AttemptID,
            time_limit=quiz.TimeLimit,
            questions=questions,
        )
    )


# ============================================================
# SUBMIT QUIZ API
# ============================================================

@api_bp.route(
    "/quizzes/<int:quiz_id>/submit",
    methods=["POST"],
)
@login_required
@role_required("Student")
def api_submit_quiz(quiz_id):
    """
    Submit a quiz attempt.

    Expected JSON:

    {
        "attempt_id": 1,
        "answers": {
            "1": "A",
            "2": "B"
        }
    }

    POST /api/quizzes/<quiz_id>/submit

    After a successful quiz submission, the API checks whether
    the student has now satisfied all certificate requirements.

    Certificate eligibility itself is handled by the certificate
    service.
    """

    # --------------------------------------------------------
    # Read JSON payload
    # --------------------------------------------------------

    payload = request.get_json(
        silent=True
    ) or {}

    attempt_id = payload.get(
        "attempt_id"
    )

    answers = payload.get(
        "answers",
        {},
    )

    # --------------------------------------------------------
    # Validate attempt ID
    # --------------------------------------------------------

    if not attempt_id:

        return (
            jsonify(
                json_response(
                    False,
                    "Missing attempt_id.",
                )
            ),
            400,
        )

    # --------------------------------------------------------
    # Validate answers
    # --------------------------------------------------------

    if not isinstance(
        answers,
        dict,
    ):

        return (
            jsonify(
                json_response(
                    False,
                    "Answers must be provided as a JSON object.",
                )
            ),
            400,
        )

    # --------------------------------------------------------
    # Current student
    # --------------------------------------------------------

    user_id = session.get(
        "user_id"
    )

    if not user_id:

        return (
            jsonify(
                json_response(
                    False,
                    "User session not found.",
                )
            ),
            401,
        )

    try:

        # ----------------------------------------------------
        # Submit and score quiz
        # ----------------------------------------------------

        attempt = submit_attempt(
            user_id,
            attempt_id,
            answers,
        )

        # ----------------------------------------------------
        # Make sure the submitted attempt belongs to the
        # requested quiz.
        # ----------------------------------------------------

        if attempt.QuizID != quiz_id:

            return (
                jsonify(
                    json_response(
                        False,
                        "Quiz attempt does not belong to this quiz.",
                    )
                ),
                400,
            )

        # ----------------------------------------------------
        # Certificate
        # ----------------------------------------------------

        certificate = None

        if attempt.Passed:

            # ------------------------------------------------
            # Get quiz
            # ------------------------------------------------

            quiz = db.session.get(
                Quiz,
                quiz_id,
            )

            if quiz is not None:

                try:

                    certificate = (
                        issue_certificate_if_eligible(
                            user_id,
                            quiz.CourseID,
                            current_app.config,
                        )
                    )

                except CertificateError:
                    """
                    This does not necessarily mean that something
                    is broken.

                    The student may have passed this quiz but
                    still have:

                    - incomplete lessons
                    - another failed module quiz
                    - an unpassed final assessment

                    Therefore certificate generation is simply
                    skipped until all requirements are satisfied.
                    """

                    certificate = None

        # ----------------------------------------------------
        # Prepare response
        # ----------------------------------------------------

        response_data = {
            "score": attempt.Score,
            "percentage": attempt.Percentage,
            "passed": attempt.Passed,
            "certificate": {
                "generated": False,
            },
        }

        # ----------------------------------------------------
        # Certificate generated
        # ----------------------------------------------------

        if certificate is not None:

            response_data["certificate"] = {
                "generated": True,
                "certificate_id": (
                    certificate.CertificateID
                ),
                "certificate_number": (
                    certificate.CertificateNumber
                ),
            }

        # ----------------------------------------------------
        # Return result
        # ----------------------------------------------------

        return jsonify(
            json_response(
                True,
                "Quiz submitted successfully.",
                **response_data,
            )
        )

    except QuizError as exc:

        return (
            jsonify(
                json_response(
                    False,
                    str(exc),
                )
            ),
            400,
        )

    except Exception:

        db.session.rollback()

        return (
            jsonify(
                json_response(
                    False,
                    "Unable to submit quiz.",
                )
            ),
            500,
        )


# ============================================================
# CERTIFICATE VERIFICATION API
# ============================================================

@api_bp.route(
    "/certificates/verify/<certificate_id>",
    methods=["GET"],
)
def api_verify_certificate(certificate_id):
    """
    Verify a certificate.

    GET /api/certificates/verify/<certificate_id>
    """

    try:

        certificate = verify_certificate(
            certificate_id
        )

    except Exception:

        db.session.rollback()

        return (
            jsonify(
                json_response(
                    False,
                    "Unable to verify certificate.",
                    valid=False,
                )
            ),
            500,
        )

    # --------------------------------------------------------
    # Certificate not found
    # --------------------------------------------------------

    if certificate is None:

        return (
            jsonify(
                json_response(
                    False,
                    "Certificate not found.",
                    valid=False,
                )
            ),
            404,
        )

    # --------------------------------------------------------
    # Issue date
    # --------------------------------------------------------

    issue_date = certificate.IssueDate

    formatted_issue_date = (
        issue_date.strftime(
            "%d %B %Y"
        )
        if issue_date
        else None
    )

    # --------------------------------------------------------
    # Student
    # --------------------------------------------------------

    student_name = (
        certificate.student.FullName
        if certificate.student
        else "Unknown Student"
    )

    # --------------------------------------------------------
    # Course
    # --------------------------------------------------------

    course_title = (
        certificate.course.Title
        if certificate.course
        else "Unknown Course"
    )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return jsonify(
        json_response(
            True,
            "Certificate found.",
            valid=(
                certificate.Status == "Valid"
            ),
            certificate={
                "CertificateNumber": (
                    certificate.CertificateNumber
                ),
                "StudentName": student_name,
                "CourseTitle": course_title,
                "FinalScore": certificate.FinalScore,
                "IssueDate": formatted_issue_date,
                "Status": certificate.Status,
            },
        )
    )