"""
Tests: quiz score calculation, pass/fail determination, attempt limits
(spec section 45).
"""

import pytest
from tests.conftest import register, login
from database.models import Category, Course, User, Module, Quiz, Question, Enrollment
from services.quiz_service import start_attempt, submit_attempt, QuizError
from utils.security import hash_password
from utils.helpers import slugify


def _build_course_with_quiz(db, passing_score=70, attempts_allowed=2):
    category = Category(Name="Quiz Category", IsActive=True)
    instructor = User(FullName="Quiz Instructor", Email="quiz_instructor@example.com",
                       PasswordHash=hash_password("Password123"), Role="Instructor", IsActive=True)
    db.session.add_all([category, instructor])
    db.session.commit()

    course = Course(
        InstructorID=instructor.UserID, CategoryID=category.CategoryID,
        Title="Quiz Course", Slug=slugify("Quiz Course"),
        Status="Published", Level="Beginner", Price=0.0, PassingScore=70,
    )
    db.session.add(course)
    db.session.commit()

    quiz = Quiz(CourseID=course.CourseID, Title="Sample Quiz",
                PassingScore=passing_score, AttemptsAllowed=attempts_allowed)
    db.session.add(quiz)
    db.session.commit()

    q1 = Question(QuizID=quiz.QuizID, QuestionText="2+2?", OptionA="3", OptionB="4",
                  OptionC="5", OptionD="6", CorrectOption="B", Marks=1)
    q2 = Question(QuizID=quiz.QuizID, QuestionText="Capital of France?", OptionA="Berlin",
                  OptionB="Madrid", OptionC="Paris", OptionD="Rome", CorrectOption="C", Marks=1)
    db.session.add_all([q1, q2])
    db.session.commit()

    return course, quiz, [q1, q2]


def test_quiz_scoring_all_correct(app, db):
    course, quiz, questions = _build_course_with_quiz(db)
    student = User(FullName="S1", Email="s1@example.com", PasswordHash=hash_password("Password123"),
                    Role="Student", IsActive=True)
    db.session.add(student)
    db.session.commit()

    attempt = start_attempt(student.UserID, quiz.QuizID)
    answers = {str(q.QuestionID): q.CorrectOption for q in questions}
    result = submit_attempt(student.UserID, attempt.AttemptID, answers)

    assert result.Score == 2
    assert result.Percentage == 100.0
    assert result.Passed is True


def test_quiz_scoring_partial_correct_fails_below_passing_score(app, db):
    course, quiz, questions = _build_course_with_quiz(db, passing_score=70)
    student = User(FullName="S2", Email="s2@example.com", PasswordHash=hash_password("Password123"),
                    Role="Student", IsActive=True)
    db.session.add(student)
    db.session.commit()

    attempt = start_attempt(student.UserID, quiz.QuizID)
    # Only answer the first question correctly -> 50%, below 70% passing score
    answers = {str(questions[0].QuestionID): questions[0].CorrectOption}
    result = submit_attempt(student.UserID, attempt.AttemptID, answers)

    assert result.Score == 1
    assert result.Percentage == 50.0
    assert result.Passed is False


def test_quiz_correct_answers_never_exposed_before_submission(app, db):
    from services.quiz_service import get_quiz_for_taking
    course, quiz, questions = _build_course_with_quiz(db)

    _, public_questions = get_quiz_for_taking(quiz.QuizID)
    for q in public_questions:
        assert "CorrectOption" not in q


def test_quiz_attempt_limit_enforced(app, db):
    course, quiz, questions = _build_course_with_quiz(db, attempts_allowed=2)
    student = User(FullName="S3", Email="s3@example.com", PasswordHash=hash_password("Password123"),
                    Role="Student", IsActive=True)
    db.session.add(student)
    db.session.commit()

    # Use up both allowed attempts
    for _ in range(2):
        attempt = start_attempt(student.UserID, quiz.QuizID)
        submit_attempt(student.UserID, attempt.AttemptID, {})

    with pytest.raises(QuizError):
        start_attempt(student.UserID, quiz.QuizID)


def test_cannot_submit_same_attempt_twice(app, db):
    course, quiz, questions = _build_course_with_quiz(db)
    student = User(FullName="S4", Email="s4@example.com", PasswordHash=hash_password("Password123"),
                    Role="Student", IsActive=True)
    db.session.add(student)
    db.session.commit()

    attempt = start_attempt(student.UserID, quiz.QuizID)
    submit_attempt(student.UserID, attempt.AttemptID, {})

    with pytest.raises(QuizError):
        submit_attempt(student.UserID, attempt.AttemptID, {})
