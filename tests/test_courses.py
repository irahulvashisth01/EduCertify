"""
Tests: course creation, updating, enrollment, and duplicate-enrollment
prevention (spec section 45).
"""

from tests.conftest import register, login
from database.models import Category, Course, Enrollment


def _make_category(db, name="Test Category"):
    cat = Category(Name=name, IsActive=True)
    db.session.add(cat)
    db.session.commit()
    return cat


def _make_instructor_and_login(client, db, email="course_instructor@example.com"):
    register(client, "Course Instructor", email, "Password123", role="Instructor")
    login(client, email, "Password123")


def _make_student_and_login(client, db, email="course_student@example.com"):
    register(client, "Course Student", email, "Password123", role="Student")
    login(client, email, "Password123")


def test_instructor_can_create_course(client, db):
    category = _make_category(db)
    _make_instructor_and_login(client, db)

    resp = client.post(
        "/instructor/courses/create",
        data={
            "title": "Intro to Testing",
            "category_id": category.CategoryID,
            "short_description": "A short desc",
            "description": "Full desc",
            "level": "Beginner",
            "duration": "2 hours",
            "price": "0",
            "passing_score": "70",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    course = Course.query.filter_by(Title="Intro to Testing").first()
    assert course is not None
    assert course.Status == "Draft"


def test_instructor_can_update_own_course(client, db):
    category = _make_category(db)
    _make_instructor_and_login(client, db)
    client.post(
        "/instructor/courses/create",
        data={"title": "Original Title", "category_id": category.CategoryID, "price": "0", "passing_score": "70"},
        follow_redirects=True,
    )
    course = Course.query.filter_by(Title="Original Title").first()

    resp = client.post(
        f"/instructor/courses/{course.CourseID}/edit",
        data={
            "title": "Updated Title",
            "category_id": category.CategoryID,
            "short_description": "",
            "description": "",
            "level": "Intermediate",
            "duration": "5 hours",
            "price": "10",
            "passing_score": "80",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    updated = Course.query.get(course.CourseID)
    assert updated.Title == "Updated Title"
    assert updated.Level == "Intermediate"


def test_instructor_cannot_edit_other_instructor_course(client, db):
    category = _make_category(db)
    _make_instructor_and_login(client, db, email="owner@example.com")
    client.post(
        "/instructor/courses/create",
        data={"title": "Owned Course", "category_id": category.CategoryID, "price": "0", "passing_score": "70"},
        follow_redirects=True,
    )
    course = Course.query.filter_by(Title="Owned Course").first()
    client.get("/auth/logout")

    _make_instructor_and_login(client, db, email="intruder@example.com")
    resp = client.get(f"/instructor/courses/{course.CourseID}/edit", follow_redirects=True)
    assert b"do not have permission" in resp.data

    # Confirm the course was NOT modified
    unchanged = Course.query.get(course.CourseID)
    assert unchanged.Title == "Owned Course"


def _publish_course(db, category, instructor_email="pub_instructor@example.com"):
    from database.models import User
    from utils.security import hash_password
    from utils.helpers import slugify

    instructor = User.query.filter_by(Email=instructor_email).first()
    if not instructor:
        instructor = User(FullName="Pub Instructor", Email=instructor_email,
                           PasswordHash=hash_password("Password123"), Role="Instructor", IsActive=True)
        db.session.add(instructor)
        db.session.commit()

    course = Course(
        InstructorID=instructor.UserID, CategoryID=category.CategoryID,
        Title="Published Test Course", Slug=slugify("Published Test Course"),
        Status="Published", Level="Beginner", Price=0.0, PassingScore=70,
    )
    db.session.add(course)
    db.session.commit()
    return course


def test_student_can_enroll_in_published_course(client, db):
    category = _make_category(db)
    course = _publish_course(db, category)
    _make_student_and_login(client, db)

    resp = client.post(f"/student/courses/{course.CourseID}/enroll", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Enrollment successful" in resp.data

    enrollment = Enrollment.query.filter_by(CourseID=course.CourseID).first()
    assert enrollment is not None
    assert enrollment.Status == "Active"


def test_duplicate_enrollment_is_prevented(client, db):
    category = _make_category(db)
    course = _publish_course(db, category, instructor_email="dup_instructor@example.com")
    _make_student_and_login(client, db, email="dup_student@example.com")

    client.post(f"/student/courses/{course.CourseID}/enroll", follow_redirects=True)
    resp = client.post(f"/student/courses/{course.CourseID}/enroll", follow_redirects=True)

    assert b"already enrolled" in resp.data
    count = Enrollment.query.filter_by(CourseID=course.CourseID).count()
    assert count == 1


def test_cannot_enroll_in_unpublished_course(client, db):
    category = _make_category(db)
    from database.models import User
    from utils.security import hash_password
    from utils.helpers import slugify

    instructor = User(FullName="Draft Instructor", Email="draft_instructor@example.com",
                       PasswordHash=hash_password("Password123"), Role="Instructor", IsActive=True)
    db.session.add(instructor)
    db.session.commit()

    draft_course = Course(
        InstructorID=instructor.UserID, CategoryID=category.CategoryID,
        Title="Draft Course", Slug=slugify("Draft Course"),
        Status="Draft", Level="Beginner", Price=0.0, PassingScore=70,
    )
    db.session.add(draft_course)
    db.session.commit()

    _make_student_and_login(client, db, email="draft_student@example.com")
    resp = client.post(f"/student/courses/{draft_course.CourseID}/enroll", follow_redirects=True)
    assert b"not available for enrollment" in resp.data
    assert Enrollment.query.filter_by(CourseID=draft_course.CourseID).count() == 0
