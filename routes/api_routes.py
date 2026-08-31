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

Main responsibilities:
    - Course APIs
    - Lesson progress API
    - Quiz start API
    - Quiz submission API
    - Certificate verification API
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

    Returns:

    {
        "success": true,
        "message": "Quiz started successfully.",
        "attempt_id": 1,
        "time_limit": 30,
        "questions": [
            {
                "QuestionID": 1,
                "QuestionText": "...",
                "OptionA": "...",
                "OptionB": "...",
                "OptionC": "...",
                "OptionD": "...",
                "Marks": 1
            }
        ]
    }

    IMPORTANT:
    CorrectOption is NEVER sent to the browser.
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
        # Validate / start quiz attempt
        # ----------------------------------------------------

        attempt = start_attempt(
            user_id,
            quiz_id,
        )

        # ----------------------------------------------------
        # Load quiz and questions
        # ----------------------------------------------------

        quiz, questions = get_quiz_for_taking(
            quiz_id
        )

        # ----------------------------------------------------
        # Verify quiz exists
        # ----------------------------------------------------

        if quiz is None:

            db.session.rollback()

            return (
                jsonify(
                    json_response(
                        False,
                        "Quiz not found.",
                    )
                ),
                404,
            )

        # ----------------------------------------------------
        # Convert SQLAlchemy questions to JSON-safe data
        # ----------------------------------------------------
        #
        # DO NOT return SQLAlchemy Question objects directly.
        #
        # The Question model provides to_public_dict(),
        # which exposes:
        #
        #   QuestionID
        #   QuestionText
        #   OptionA
        #   OptionB
        #   OptionC
        #   OptionD
        #   Marks
        #
        # and intentionally does NOT expose CorrectOption.
        #
        # ----------------------------------------------------

        questions_data = []

        for question in questions:

            if hasattr(
                question,
                "to_public_dict",
            ):

                question_data = (
                    question.to_public_dict()
                )

                questions_data.append(
                    question_data
                )

            elif isinstance(
                question,
                dict,
            ):

                # ------------------------------------------------
                # If the service already returned dictionaries,
                # normalize them without exposing CorrectOption.
                # ------------------------------------------------

                questions_data.append(
                    {
                        "QuestionID": (
                            question.get(
                                "QuestionID"
                            )
                            or question.get(
                                "question_id"
                            )
                            or question.get(
                                "id"
                            )
                        ),

                        "QuestionText": (
                            question.get(
                                "QuestionText"
                            )
                            or question.get(
                                "question_text"
                            )
                            or question.get(
                                "text"
                            )
                            or ""
                        ),

                        "OptionA": (
                            question.get(
                                "OptionA"
                            )
                            or question.get(
                                "option_a"
                            )
                            or ""
                        ),

                        "OptionB": (
                            question.get(
                                "OptionB"
                            )
                            or question.get(
                                "option_b"
                            )
                            or ""
                        ),

                        "OptionC": (
                            question.get(
                                "OptionC"
                            )
                            or question.get(
                                "option_c"
                            )
                            or ""
                        ),

                        "OptionD": (
                            question.get(
                                "OptionD"
                            )
                            or question.get(
                                "option_d"
                            )
                            or ""
                        ),

                        "Marks": (
                            question.get(
                                "Marks"
                            )
                            or question.get(
                                "marks"
                            )
                            or 1
                        ),
                    }
                )

    except QuizError as exc:

        db.session.rollback()

        return (
            jsonify(
                json_response(
                    False,
                    str(exc),
                )
            ),
            400,
        )

    except Exception as exc:

        db.session.rollback()

        current_app.logger.exception(
            "Unable to start quiz %s: %s",
            quiz_id,
            exc,
        )

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
    # Make sure questions exist
    # --------------------------------------------------------

    if not questions_data:

        return (
            jsonify(
                json_response(
                    False,
                    "This quiz does not contain any questions.",
                )
            ),
            400,
        )

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    return jsonify(
        json_response(
            True,
            "Quiz started successfully.",
            attempt_id=attempt.AttemptID,
            time_limit=quiz.TimeLimit,
            questions=questions_data,
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

    POST /api/quizzes/<quiz_id>/submit

    Expected JSON:

    {
        "attempt_id": 1,
        "answers": {
            "1": "A",
            "2": "B",
            "3": "C"
        }
    }

    The server performs the actual scoring.

    After a successful submission:

        Quiz Score
             ↓
        Pass / Fail
             ↓
        Certificate Eligibility
             ↓
        Certificate Generation
    """

    # --------------------------------------------------------
    # Read JSON payload
    # --------------------------------------------------------

    payload = request.get_json(
        silent=True
    ) or {}

    # --------------------------------------------------------
    # Attempt ID
    # --------------------------------------------------------

    attempt_id = payload.get(
        "attempt_id"
    )

    # --------------------------------------------------------
    # Answers
    # --------------------------------------------------------

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
    # Validate answers object
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
    # Normalize answer values
    # --------------------------------------------------------
    #
    # Only A/B/C/D are accepted.
    #
    # This prevents invalid values from reaching
    # the scoring service.
    #
    # --------------------------------------------------------

    normalized_answers = {}

    for question_id, answer in answers.items():

        if answer is None:
            continue

        answer_value = str(
            answer
        ).strip().upper()

        if answer_value in {
            "A",
            "B",
            "C",
            "D",
        }:

            normalized_answers[
                str(question_id)
            ] = answer_value

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
            normalized_answers,
        )

        # ----------------------------------------------------
        # Security check:
        # submitted attempt must belong to this quiz.
        # ----------------------------------------------------

        if attempt.QuizID != quiz_id:

            db.session.rollback()

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
                    Passing one quiz does not necessarily mean
                    the student has completed every certificate
                    requirement.

                    Certificate generation may still require:

                    - All lessons completed
                    - Required module quizzes passed
                    - Final assessment passed
                    - Other course requirements

                    Therefore certificate generation is simply
                    skipped until all requirements are satisfied.
                    """

                    certificate = None

        # ----------------------------------------------------
        # Prepare response
        # ----------------------------------------------------

        response_data = {

            "score":
                attempt.Score,

            "percentage":
                attempt.Percentage,

            "passed":
                attempt.Passed,

            "certificate": {

                "generated":
                    False
            }
        }

        # ----------------------------------------------------
        # Certificate generated
        # ----------------------------------------------------

        if certificate is not None:

            response_data[
                "certificate"
            ] = {

                "generated":
                    True,

                "certificate_id":
                    certificate.CertificateID,

                "certificate_number":
                    certificate.CertificateNumber,
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

        db.session.rollback()

        return (
            jsonify(
                json_response(
                    False,
                    str(exc),
                )
            ),
            400,
        )

    except Exception as exc:

        db.session.rollback()

        current_app.logger.exception(
            "Unable to submit quiz %s: %s",
            quiz_id,
        )

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

    Public endpoint.
    No login required.
    """

    # --------------------------------------------------------
    # Verify certificate
    # --------------------------------------------------------

    try:

        certificate = verify_certificate(
            certificate_id
        )

    except Exception as exc:

        db.session.rollback()

        current_app.logger.exception(
            "Unable to verify certificate %s: %s",
            certificate_id,
            exc,
        )

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

    issue_date = (
        certificate.IssueDate
    )

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
    # Return certificate information
    # --------------------------------------------------------

    return jsonify(
        json_response(
            True,
            "Certificate found.",

            valid=(
                certificate.Status ==
                "Valid"
            ),

            certificate={

                "CertificateNumber":
                    certificate.CertificateNumber,

                "StudentName":
                    student_name,

                "CourseTitle":
                    course_title,

                "FinalScore":
                    certificate.FinalScore,

                "IssueDate":
                    formatted_issue_date,

                "Status":
                    certificate.Status,
            },
        )
    )