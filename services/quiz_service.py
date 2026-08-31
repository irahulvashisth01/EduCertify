"""
EduCertify — Quiz Service

Business logic for:
- Loading quizzes for students
- Starting quiz attempts
- Submitting quiz answers
- Calculating scores
- Determining pass/fail status
- Finding the best attempt
- Checking whether a student has passed
- Calculating remaining attempts

Correct answers are NEVER exposed while a student is taking a quiz.
"""

from datetime import datetime, timezone

from database.database import db
from database.models import (
    Quiz,
    Question,
    QuizAttempt,
    QuizAnswer,
)


# ============================================================
# CUSTOM EXCEPTION
# ============================================================

class QuizError(Exception):
    """
    Raised when a quiz operation cannot be completed.
    """

    pass


# ============================================================
# GET QUIZ FOR TAKING
# ============================================================

def get_quiz_for_taking(
    quiz_id: int,
):
    """
    Return a quiz and its questions without exposing
    correct answers.

    Returns:
        tuple:
            (Quiz, list[dict])

    Raises:
        QuizError:
            If the quiz does not exist.
    """

    if not quiz_id:
        raise QuizError(
            "Quiz ID is required."
        )

    quiz = db.session.get(
        Quiz,
        quiz_id,
    )

    if quiz is None:
        raise QuizError(
            "Quiz not found."
        )

    questions = [
        question.to_public_dict()
        for question in quiz.questions
    ]

    return quiz, questions


# ============================================================
# START QUIZ ATTEMPT
# ============================================================

def start_attempt(
    student_id: int,
    quiz_id: int,
) -> QuizAttempt:
    """
    Start a new quiz attempt for a student.

    The number of attempts is limited by the quiz's
    AttemptsAllowed field.
    """

    if not student_id:
        raise QuizError(
            "Student ID is required."
        )

    if not quiz_id:
        raise QuizError(
            "Quiz ID is required."
        )

    quiz = db.session.get(
        Quiz,
        quiz_id,
    )

    if quiz is None:
        raise QuizError(
            "Quiz not found."
        )

    # --------------------------------------------------------
    # Validate attempt limit
    # --------------------------------------------------------

    attempts_allowed = (
        quiz.AttemptsAllowed
        if quiz.AttemptsAllowed is not None
        else 3
    )

    previous_attempts = (
        QuizAttempt.query
        .filter_by(
            StudentID=student_id,
            QuizID=quiz_id,
        )
        .count()
    )

    if previous_attempts >= attempts_allowed:

        raise QuizError(
            f"You have used all "
            f"{attempts_allowed} allowed attempts "
            f"for this quiz."
        )

    # --------------------------------------------------------
    # Create attempt
    # --------------------------------------------------------

    attempt = QuizAttempt(
        QuizID=quiz_id,
        StudentID=student_id,
        AttemptNumber=previous_attempts + 1,
        StartedAt=datetime.now(timezone.utc),
    )

    try:

        db.session.add(attempt)

        db.session.commit()

        db.session.refresh(attempt)

    except Exception as exc:

        db.session.rollback()

        raise QuizError(
            "Unable to start the quiz. "
            "Please try again."
        ) from exc

    return attempt


# ============================================================
# SUBMIT QUIZ ATTEMPT
# ============================================================

def submit_attempt(
    student_id: int,
    attempt_id: int,
    answers: dict,
) -> QuizAttempt:
    """
    Submit a student's quiz attempt.

    Args:
        student_id:
            ID of the student submitting the quiz.

        attempt_id:
            QuizAttempt ID.

        answers:
            Dictionary mapping question IDs to selected
            options.

            Example:

                {
                    "1": "A",
                    "2": "C",
                    "3": "B"
                }

    Correct answers are read internally from the database
    and are never returned to the client.
    """

    if not student_id:
        raise QuizError(
            "Student ID is required."
        )

    if not attempt_id:
        raise QuizError(
            "Attempt ID is required."
        )

    if not isinstance(answers, dict):
        raise QuizError(
            "Invalid answers format."
        )

    # --------------------------------------------------------
    # Find attempt
    # --------------------------------------------------------

    attempt = db.session.get(
        QuizAttempt,
        attempt_id,
    )

    if (
        attempt is None
        or attempt.StudentID != student_id
    ):

        raise QuizError(
            "Attempt not found."
        )

    # --------------------------------------------------------
    # Prevent duplicate submission
    # --------------------------------------------------------

    if attempt.CompletedAt is not None:

        raise QuizError(
            "This attempt has already been submitted."
        )

    # --------------------------------------------------------
    # Find quiz
    # --------------------------------------------------------

    quiz = db.session.get(
        Quiz,
        attempt.QuizID,
    )

    if quiz is None:

        raise QuizError(
            "Quiz not found."
        )

    questions = {
        question.QuestionID: question
        for question in quiz.questions
    }

    if not questions:

        raise QuizError(
            "This quiz does not contain any questions."
        )

    # --------------------------------------------------------
    # Calculate total marks
    # --------------------------------------------------------

    total_marks_possible = sum(
        question.Marks or 0
        for question in questions.values()
    )

    if total_marks_possible <= 0:

        total_marks_possible = 1

    total_marks_obtained = 0

    allowed_options = {
        "A",
        "B",
        "C",
        "D",
    }

    # --------------------------------------------------------
    # Process answers
    # --------------------------------------------------------

    try:

        for question_id, question in questions.items():

            selected = (
                answers.get(str(question_id))
                if str(question_id) in answers
                else answers.get(question_id)
            )

            if selected is not None:

                selected = str(
                    selected
                ).strip().upper()

            # Invalid option = unanswered
            if selected not in allowed_options:

                selected = None

            is_correct = (
                selected is not None
                and selected
                == str(
                    question.CorrectOption
                ).strip().upper()
            )

            marks = (
                question.Marks or 0
                if is_correct
                else 0
            )

            total_marks_obtained += marks

            answer_record = QuizAnswer(
                AttemptID=attempt.AttemptID,
                QuestionID=question_id,
                SelectedOption=selected,
                IsCorrect=is_correct,
                MarksObtained=marks,
            )

            db.session.add(
                answer_record
            )

        # ----------------------------------------------------
        # Calculate result
        # ----------------------------------------------------

        percentage = round(
            (
                total_marks_obtained
                / total_marks_possible
            )
            * 100,
            1,
        )

        passing_score = (
            quiz.PassingScore
            if quiz.PassingScore is not None
            else 70
        )

        passed = (
            percentage >= passing_score
        )

        # ----------------------------------------------------
        # Update attempt
        # ----------------------------------------------------

        attempt.Score = (
            total_marks_obtained
        )

        attempt.Percentage = percentage

        attempt.Passed = passed

        attempt.CompletedAt = (
            datetime.now(timezone.utc)
        )

        db.session.commit()

        db.session.refresh(
            attempt
        )

    except QuizError:

        db.session.rollback()

        raise

    except Exception as exc:

        db.session.rollback()

        raise QuizError(
            "Unable to submit the quiz. "
            "Please try again."
        ) from exc

    return attempt


# ============================================================
# GET BEST ATTEMPT
# ============================================================

def get_best_attempt(
    student_id: int,
    quiz_id: int,
):
    """
    Return the student's highest-scoring completed attempt.

    Returns:
        QuizAttempt | None
    """

    if not student_id or not quiz_id:

        return None

    return (
        QuizAttempt.query
        .filter_by(
            StudentID=student_id,
            QuizID=quiz_id,
        )
        .filter(
            QuizAttempt.CompletedAt.isnot(None)
        )
        .order_by(
            QuizAttempt.Percentage.desc()
        )
        .first()
    )


# ============================================================
# CHECK PASSED QUIZ
# ============================================================

def has_passed_quiz(
    student_id: int,
    quiz_id: int,
) -> bool:
    """
    Return True if the student has at least one
    completed passing attempt.
    """

    if not student_id or not quiz_id:

        return False

    attempt = (
        QuizAttempt.query
        .filter_by(
            StudentID=student_id,
            QuizID=quiz_id,
            Passed=True,
        )
        .filter(
            QuizAttempt.CompletedAt.isnot(None)
        )
        .first()
    )

    return attempt is not None


# ============================================================
# GET REMAINING ATTEMPTS
# ============================================================

def get_remaining_attempts(
    student_id: int,
    quiz_id: int,
) -> int:
    """
    Calculate how many attempts the student has remaining.

    Returns:
        int
    """

    if not student_id or not quiz_id:

        return 0

    quiz = db.session.get(
        Quiz,
        quiz_id,
    )

    if quiz is None:

        return 0

    attempts_allowed = (
        quiz.AttemptsAllowed
        if quiz.AttemptsAllowed is not None
        else 3
    )

    used = (
        QuizAttempt.query
        .filter_by(
            StudentID=student_id,
            QuizID=quiz_id,
        )
        .count()
    )

    return max(
        0,
        attempts_allowed - used,
    )