"""
Tests: registration, login, logout, invalid login, and role-based
authorization boundaries (spec section 45).
"""

from tests.conftest import register, login
from database.models import User


def test_registration_creates_user(client, db):
    resp = register(client, "Jane Doe", "jane@example.com", "Password123", role="Student")
    assert resp.status_code == 200
    user = User.query.filter_by(Email="jane@example.com").first()
    assert user is not None
    assert user.Role == "Student"
    # Password must never be stored in plain text
    assert user.PasswordHash != "Password123"


def test_registration_rejects_duplicate_email(client, db):
    register(client, "Jane Doe", "dupe@example.com", "Password123")
    client.get("/auth/logout")  # registering logs the user in; log out before retrying
    resp = register(client, "Someone Else", "dupe@example.com", "Password123")
    assert b"already exists" in resp.data


def test_registration_rejects_mismatched_passwords(client, db):
    resp = client.post(
        "/auth/register",
        data={
            "full_name": "Jane Doe",
            "email": "mismatch@example.com",
            "password": "Password123",
            "confirm_password": "Different123",
            "role": "Student",
        },
        follow_redirects=True,
    )
    assert b"do not match" in resp.data
    assert User.query.filter_by(Email="mismatch@example.com").first() is None


def test_registration_rejects_weak_password(client, db):
    resp = client.post(
        "/auth/register",
        data={
            "full_name": "Jane Doe",
            "email": "weakpw@example.com",
            "password": "abc",
            "confirm_password": "abc",
            "role": "Student",
        },
        follow_redirects=True,
    )
    assert User.query.filter_by(Email="weakpw@example.com").first() is None


def test_login_success(client, db):
    register(client, "Login Test", "login@example.com", "Password123")
    resp = login(client, "login@example.com", "Password123")
    assert resp.status_code == 200
    assert b"dashboard" in resp.request.path.encode() or "dashboard" in resp.request.path


def test_login_invalid_credentials(client, db):
    register(client, "Login Test 2", "login2@example.com", "Password123")
    client.get("/auth/logout")  # registering logs the user in; log out before retrying
    resp = login(client, "login2@example.com", "WrongPassword1")
    assert b"Invalid email or password" in resp.data


def test_login_nonexistent_user(client, db):
    resp = login(client, "doesnotexist@example.com", "Password123")
    assert b"Invalid email or password" in resp.data


def test_logout_clears_session(client, db):
    register(client, "Logout Test", "logout@example.com", "Password123")
    login(client, "logout@example.com", "Password123")
    resp = client.get("/auth/logout", follow_redirects=True)
    assert resp.status_code == 200
    # Protected route should now redirect to login
    resp2 = client.get("/student/dashboard", follow_redirects=True)
    assert "/auth/login" in resp2.request.path


def test_student_cannot_access_admin_routes(client, db):
    register(client, "Some Student", "stud1@example.com", "Password123", role="Student")
    login(client, "stud1@example.com", "Password123")
    resp = client.get("/admin/dashboard")
    assert resp.status_code == 403


def test_instructor_cannot_access_admin_routes(client, db):
    register(client, "Some Instructor", "inst1@example.com", "Password123", role="Instructor")
    login(client, "inst1@example.com", "Password123")
    resp = client.get("/admin/dashboard")
    assert resp.status_code == 403


def test_student_cannot_access_instructor_routes(client, db):
    register(client, "Some Student2", "stud2@example.com", "Password123", role="Student")
    login(client, "stud2@example.com", "Password123")
    resp = client.get("/instructor/dashboard")
    assert resp.status_code == 403


def test_anonymous_redirected_to_login(client, db):
    resp = client.get("/student/dashboard", follow_redirects=True)
    assert "/auth/login" in resp.request.path
