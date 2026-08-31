"""
Tests: certificate eligibility, generation, unique ID, verification,
and invalid-certificate handling (spec section 45).
"""

import pytest
from database.models import Category, Course, User, Module, Lesson, Quiz, Question, Enrollment, LessonProgress
from services.certificate_service import (
    check_eligibility, issue_certificate, verify_certificate, CertificateError
)
from services.progress_service import mark_lesson_complete
from services.quiz_service import start_attempt, submit_attempt
from utils.security import hash_password
from utils.helpers import slugify


def _build_full_course(db):
    """Course with 1 module, 2 lessons, and a final assessment quiz."""
    category = Category(Name="Cert Category", IsActive=True)
    instructor = User(FullName="Cert Instructor", Email="cert_instructor@example.com",
                       PasswordHash=hash_password("Password123"), Role="Instructor", IsActive=True)
    db.session.add_all([category, instructor])
    db.session.commit()

    course = Course(
        InstructorID=instructor.UserID, CategoryID=category.CategoryID,
        Title="Certificate Course", Slug=slugify("Certificate Course"),
        Status="Published", Level="Beginner", Price=0.0, PassingScore=70,
    )
    db.session.add(course)
    db.session.commit()

    module = Module(CourseID=course.CourseID, Title="Module 1", DisplayOrder=1)
    db.session.add(module)
    db.session.commit()

    lesson1 = Lesson(ModuleID=module.ModuleID, Title="Lesson 1", DisplayOrder=1)
    lesson2 = Lesson(ModuleID=module.ModuleID, Title="Lesson 2", DisplayOrder=2)
    db.session.add_all([lesson1, lesson2])
    db.session.commit()

    final_quiz = Quiz(CourseID=course.CourseID, Title="Final Assessment",
                       PassingScore=70, AttemptsAllowed=3, IsFinalAssessment=True)
    db.session.add(final_quiz)
    db.session.commit()

    question = Question(QuizID=final_quiz.QuizID, QuestionText="1+1?", OptionA="1", OptionB="2",
                         OptionC="3", OptionD="4", CorrectOption="B", Marks=1)
    db.session.add(question)
    db.session.commit()

    return course, module, [lesson1, lesson2], final_quiz, question


def _make_student(db, email="cert_student@example.com"):
    student = User(FullName="Cert Student", Email=email, PasswordHash=hash_password("Password123"),
                    Role="Student", IsActive=True)
    db.session.add(student)
    db.session.commit()
    return student


def _enroll(db, student, course):
    enrollment = Enrollment(StudentID=student.UserID, CourseID=course.CourseID, Status="Active", ProgressPercentage=0.0)
    db.session.add(enrollment)
    db.session.commit()
    return enrollment


def test_not_eligible_before_completing_requirements(app, db):
    course, module, lessons, quiz, question = _build_full_course(db)
    student = _make_student(db)
    _enroll(db, student, course)

    eligibility = check_eligibility(student.UserID, course.CourseID)
    assert eligibility["eligible"] is False
    assert eligibility["lessons_done"] is False


def test_eligible_after_completing_lessons_and_passing_final(app, db):
    course, module, lessons, quiz, question = _build_full_course(db)
    student = _make_student(db)
    _enroll(db, student, course)

    for lesson in lessons:
        mark_lesson_complete(student.UserID, lesson.LessonID)

    attempt = start_attempt(student.UserID, quiz.QuizID)
    submit_attempt(student.UserID, attempt.AttemptID, {str(question.QuestionID): "B"})

    eligibility = check_eligibility(student.UserID, course.CourseID)
    assert eligibility["eligible"] is True


def test_certificate_generation_produces_unique_number(app, db):
    course, module, lessons, quiz, question = _build_full_course(db)
    student = _make_student(db)
    _enroll(db, student, course)

    for lesson in lessons:
        mark_lesson_complete(student.UserID, lesson.LessonID)
    attempt = start_attempt(student.UserID, quiz.QuizID)
    submit_attempt(student.UserID, attempt.AttemptID, {str(question.QuestionID): "B"})

    cert = issue_certificate(student.UserID, course.CourseID, app.config)
    assert cert.CertificateNumber.startswith("EDC-")
    assert cert.Status == "Valid"
    assert cert.FinalScore == 100.0


def test_certificate_generation_fails_when_not_eligible(app, db):
    course, module, lessons, quiz, question = _build_full_course(db)
    student = _make_student(db)
    _enroll(db, student, course)

    with pytest.raises(CertificateError):
        issue_certificate(student.UserID, course.CourseID, app.config)


def test_certificate_verification_finds_valid_certificate(app, db):
    course, module, lessons, quiz, question = _build_full_course(db)
    student = _make_student(db)
    _enroll(db, student, course)

    for lesson in lessons:
        mark_lesson_complete(student.UserID, lesson.LessonID)
    attempt = start_attempt(student.UserID, quiz.QuizID)
    submit_attempt(student.UserID, attempt.AttemptID, {str(question.QuestionID): "B"})
    cert = issue_certificate(student.UserID, course.CourseID, app.config)

    found = verify_certificate(cert.CertificateNumber)
    assert found is not None
    assert found.CertificateID == cert.CertificateID


def test_certificate_verification_invalid_id_returns_none(app, db):
    result = verify_certificate("EDC-2026-000000")
    assert result is None


def test_certificate_verification_via_public_route(app, db, client):
    course, module, lessons, quiz, question = _build_full_course(db)
    student = _make_student(db)
    _enroll(db, student, course)

    for lesson in lessons:
        mark_lesson_complete(student.UserID, lesson.LessonID)
    attempt = start_attempt(student.UserID, quiz.QuizID)
    submit_attempt(student.UserID, attempt.AttemptID, {str(question.QuestionID): "B"})
    cert = issue_certificate(student.UserID, course.CourseID, app.config)

    # No login required for verification
    resp = client.get(f"/certificates/verify/{cert.CertificateNumber}")
    assert resp.status_code == 200
    assert b"CERTIFICATE VERIFIED" in resp.data

    resp_invalid = client.get("/certificates/verify/EDC-2026-999999")
    assert b"INVALID CERTIFICATE" in resp_invalid.data
