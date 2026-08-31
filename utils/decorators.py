"""
Authentication and authorization decorators.

Usage:
    @login_required
    def some_view(): ...

    @role_required("Instructor")
    def instructor_only_view(): ...

    @role_required("Admin", "Instructor")
    def multi_role_view(): ...
"""

from functools import wraps
from flask import session, redirect, url_for, flash, abort, request


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def role_required(*allowed_roles):
    """Restrict a view to one or more roles. Must be used with @login_required
    above it, or it will redirect to login itself if no session exists."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login", next=request.path))
            if session.get("role") not in allowed_roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def guest_only(view_func):
    """Prevent already-logged-in users from viewing login/register pages."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" in session:
            role = session.get("role")
            return redirect(_dashboard_for_role(role))
        return view_func(*args, **kwargs)
    return wrapped


def _dashboard_for_role(role):
    mapping = {
        "Student": "student.dashboard",
        "Instructor": "instructor.dashboard",
        "Admin": "admin.dashboard",
    }
    return url_for(mapping.get(role, "public.home"))
