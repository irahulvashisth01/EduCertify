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
    jsonify,
    request,
    session,
)

from database.database import db
from database.models import (
    Lesson,
    Course,
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

@api_bp.route("/courses", methods=["GET"])
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

    user_id = session.get("user_id")

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

    user_id = session.get("user_id")

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

        attempt = start_attempt(
            user_id,
            quiz_id,
        )

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
    """

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

    if not isinstance(answers, dict):
        return (
            jsonify(
                json_response(
                    False,
                    "Answers must be provided as a JSON object.",
                )
            ),
            400,
        )

    user_id = session.get("user_id")

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

        attempt = submit_attempt(
            user_id,
            attempt_id,
            answers,
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

    return jsonify(
        json_response(
            True,
            "Quiz submitted successfully.",
            score=attempt.Score,
            percentage=attempt.Percentage,
            passed=attempt.Passed,
        )
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

    issue_date = certificate.IssueDate

    formatted_issue_date = (
        issue_date.strftime("%d %B %Y")
        if issue_date
        else None
    )

    student_name = (
        certificate.student.FullName
        if certificate.student
        else "Unknown Student"
    )

    course_title = (
        certificate.course.Title
        if certificate.course
        else "Unknown Course"
    )

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