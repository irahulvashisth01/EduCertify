"""
EduCertify — Quiz Result Routes

The JSON API handles:
- Starting quizzes
- Submitting quizzes
- Scoring attempts

This blueprint handles the human-facing result page.

Route:
    GET /quiz/attempt/<attempt_id>/result
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    session,
    url_for,
)

from database.database import db
from database.models import QuizAttempt

from utils.decorators import (
    login_required,
    role_required,
)


# ============================================================
# BLUEPRINT
# ============================================================

quiz_bp = Blueprint(
    "quiz",
    __name__,
    url_prefix="/quiz",
)


# ============================================================
# QUIZ RESULT
# ============================================================

@quiz_bp.route(
    "/attempt/<int:attempt_id>/result",
    methods=["GET"],
)
@login_required
@role_required("Student")
def result(attempt_id):
    """
    Display the result of a completed quiz attempt.

    Students may only view their own attempts.

    URL:
        /quiz/attempt/<attempt_id>/result
    """

    # --------------------------------------------------------
    # Find attempt
    # --------------------------------------------------------

    attempt = db.session.get(
        QuizAttempt,
        attempt_id,
    )

    if attempt is None:
        flash(
            "Quiz attempt not found.",
            "error",
        )

        return redirect(
            url_for("student.dashboard")
        )

    # --------------------------------------------------------
    # Ownership check
    # --------------------------------------------------------

    current_user_id = session.get(
        "user_id"
    )

    if attempt.StudentID != current_user_id:

        flash(
            "You do not have access to this quiz attempt.",
            "error",
        )

        return redirect(
            url_for("student.dashboard")
        )

    # --------------------------------------------------------
    # Check submission status
    # --------------------------------------------------------

    if attempt.CompletedAt is None:

        flash(
            "This quiz attempt has not been submitted yet.",
            "warning",
        )

        return redirect(
            url_for(
                "student.quiz_page",
                quiz_id=attempt.QuizID,
            )
        )

    # --------------------------------------------------------
    # Render result
    # --------------------------------------------------------

    return render_template(
        "student/quiz.html",
        quiz=attempt.quiz,
        result_attempt=attempt,
        remaining_attempts=None,
        best_attempt=attempt,
    )