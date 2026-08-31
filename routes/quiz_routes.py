"""
Quiz result page. Starting/submitting quizzes happens via the JSON API
(api_routes.py); this blueprint renders the human-facing result view.
"""

from flask import Blueprint, render_template, redirect, url_for, session, flash

from database.models import QuizAttempt
from utils.decorators import login_required, role_required

quiz_bp = Blueprint("quiz", __name__, url_prefix="/quiz")


@quiz_bp.route("/attempt/<int:attempt_id>/result")
@login_required
@role_required("Student")
def result(attempt_id):
    attempt = QuizAttempt.query.get_or_404(attempt_id)
    if attempt.StudentID != session["user_id"]:
        flash("You do not have access to this quiz attempt.", "error")
        return redirect(url_for("student.dashboard"))

    if attempt.CompletedAt is None:
        flash("This quiz attempt has not been submitted yet.", "warning")
        return redirect(url_for("student.quiz_page", quiz_id=attempt.QuizID))

    return render_template("student/quiz.html", quiz=attempt.quiz, result_attempt=attempt,
                            remaining_attempts=None, best_attempt=attempt)
