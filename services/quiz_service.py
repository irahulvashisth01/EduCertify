"""
Quiz engine business logic: attempts, scoring, pass/fail determination.
Correct answers are never exposed to the caller until after submission.
"""

from datetime import datetime, timezone
from database.database import db
from database.models import Quiz, Question, QuizAttempt, QuizAnswer


class QuizError(Exception):
    pass


def get_quiz_for_taking(quiz_id: int):
    """Return the quiz plus questions serialized WITHOUT correct answers."""
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        raise QuizError("Quiz not found.")
    questions = [q.to_public_dict() for q in quiz.questions]
    return quiz, questions


def start_attempt(student_id: int, quiz_id: int) -> QuizAttempt:
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        raise QuizError("Quiz not found.")

    previous_attempts = QuizAttempt.query.filter_by(StudentID=student_id, QuizID=quiz_id).count()
    if previous_attempts >= quiz.AttemptsAllowed:
        raise QuizError(f"You have used all {quiz.AttemptsAllowed} allowed attempts for this quiz.")

    attempt = QuizAttempt(
        QuizID=quiz_id,
        StudentID=student_id,
        AttemptNumber=previous_attempts + 1,
        StartedAt=datetime.now(timezone.utc),
    )
    db.session.add(attempt)
    db.session.commit()
    return attempt


def submit_attempt(student_id: int, attempt_id: int, answers: dict) -> QuizAttempt:
    """
    answers: dict mapping question_id (str or int) -> selected_option ('A'/'B'/'C'/'D')
    """
    attempt = QuizAttempt.query.get(attempt_id)
    if not attempt or attempt.StudentID != student_id:
        raise QuizError("Attempt not found.")

    if attempt.CompletedAt is not None:
        raise QuizError("This attempt has already been submitted.")

    quiz = Quiz.query.get(attempt.QuizID)
    questions = {q.QuestionID: q for q in quiz.questions}

    total_marks_possible = sum(q.Marks for q in questions.values()) or 1
    total_marks_obtained = 0

    for question_id, question in questions.items():
        selected = answers.get(str(question_id)) or answers.get(question_id)
        is_correct = bool(selected) and selected.strip().upper() == question.CorrectOption.upper()
        marks = question.Marks if is_correct else 0
        total_marks_obtained += marks

        answer_record = QuizAnswer(
            AttemptID=attempt.AttemptID,
            QuestionID=question_id,
            SelectedOption=(selected or "").upper() if selected else None,
            IsCorrect=is_correct,
            MarksObtained=marks,
        )
        db.session.add(answer_record)

    percentage = round((total_marks_obtained / total_marks_possible) * 100, 1)
    passed = percentage >= quiz.PassingScore

    attempt.Score = total_marks_obtained
    attempt.Percentage = percentage
    attempt.Passed = passed
    attempt.CompletedAt = datetime.now(timezone.utc)

    db.session.commit()
    return attempt


def get_best_attempt(student_id: int, quiz_id: int):
    return (
        QuizAttempt.query.filter_by(StudentID=student_id, QuizID=quiz_id)
        .order_by(QuizAttempt.Percentage.desc())
        .first()
    )


def has_passed_quiz(student_id: int, quiz_id: int) -> bool:
    attempt = QuizAttempt.query.filter_by(StudentID=student_id, QuizID=quiz_id, Passed=True).first()
    return attempt is not None


def get_remaining_attempts(student_id: int, quiz_id: int) -> int:
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        return 0
    used = QuizAttempt.query.filter_by(StudentID=student_id, QuizID=quiz_id).count()
    return max(0, quiz.AttemptsAllowed - used)
