"""
Authentication routes: register, login, logout.
Forgot/reset password included as functional stubs (no email backend wired
by default) so the templates exist and the flow is demonstrable.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from services.auth_service import register_user, authenticate_user, AuthError
from utils.decorators import guest_only

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

ROLE_DASHBOARD = {
    "Student": "student.dashboard",
    "Instructor": "instructor.dashboard",
    "Admin": "admin.dashboard",
}


@auth_bp.route("/register", methods=["GET", "POST"])
@guest_only
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "Student")

        try:
            user = register_user(full_name, email, password, confirm_password, role)
        except AuthError as e:
            flash(str(e), "error")
            return render_template("auth/register.html", form_data=request.form)

        session.clear()
        session["user_id"] = user.UserID
        session["user_name"] = user.FullName
        session["role"] = user.Role
        flash(f"Welcome to EduCertify, {user.FullName}!", "success")
        return redirect(url_for(ROLE_DASHBOARD[user.Role]))

    return render_template("auth/register.html", form_data={})


@auth_bp.route("/login", methods=["GET", "POST"])
@guest_only
def login():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        try:
            user = authenticate_user(email, password)
        except AuthError as e:
            flash(str(e), "error")
            return render_template("auth/login.html", email=email)

        session.clear()
        session["user_id"] = user.UserID
        session["user_name"] = user.FullName
        session["role"] = user.Role
        flash(f"Welcome back, {user.FullName}!", "success")

        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for(ROLE_DASHBOARD[user.Role]))

    return render_template("auth/login.html", email="")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("public.home"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@guest_only
def forgot_password():
    if request.method == "POST":
        # Email delivery is not wired up in this build; acknowledge the
        # request without confirming whether the email exists (avoids
        # leaking account existence).
        flash("If an account with that email exists, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@guest_only
def reset_password(token):
    if request.method == "POST":
        flash("Password reset is not available in this demo build.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", token=token)
