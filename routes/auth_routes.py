"""
EduCertify — Authentication Routes

Handles:
- User registration
- User login
- User logout
- Forgot password flow
- Reset password flow

Blueprint prefix:
    /auth
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.auth_service import (
    register_user,
    authenticate_user,
    AuthError,
)

from utils.decorators import guest_only


# ============================================================
# BLUEPRINT
# ============================================================

auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth",
)


# ============================================================
# ROLE DASHBOARDS
# ============================================================

ROLE_DASHBOARD = {
    "Student": "student.dashboard",
    "Instructor": "instructor.dashboard",
    "Admin": "admin.dashboard",
}


# ============================================================
# HELPER — CREATE LOGIN SESSION
# ============================================================

def _login_user_session(user):
    """
    Create a clean Flask session for the authenticated user.
    """

    session.clear()

    session["user_id"] = user.UserID
    session["user_name"] = user.FullName
    session["role"] = user.Role

    # Keep session active for the configured lifetime.
    session.permanent = True


# ============================================================
# REGISTER
# ============================================================

@auth_bp.route(
    "/register",
    methods=["GET", "POST"],
)
@guest_only
def register():
    """
    Register a new EduCertify user.

    GET:
        Display registration page.

    POST:
        Validate form and create account.
    """

    if request.method == "POST":

        full_name = (
            request.form.get("full_name")
            or ""
        ).strip()

        email = (
            request.form.get("email")
            or ""
        ).strip().lower()

        password = (
            request.form.get("password")
            or ""
        )

        confirm_password = (
            request.form.get("confirm_password")
            or ""
        )

        role = (
            request.form.get("role")
            or "Student"
        ).strip()

        # ----------------------------------------------------
        # Security: only allow supported public roles
        # ----------------------------------------------------

        allowed_roles = {
            "Student",
            "Instructor",
        }

        if role not in allowed_roles:
            role = "Student"

        # ----------------------------------------------------
        # Basic validation
        # ----------------------------------------------------

        if not full_name:
            flash(
                "Full name is required.",
                "error",
            )

            return render_template(
                "auth/register.html",
                form_data=request.form,
            )

        if not email:
            flash(
                "Email address is required.",
                "error",
            )

            return render_template(
                "auth/register.html",
                form_data=request.form,
            )

        if not password:
            flash(
                "Password is required.",
                "error",
            )

            return render_template(
                "auth/register.html",
                form_data=request.form,
            )

        if password != confirm_password:
            flash(
                "Passwords do not match.",
                "error",
            )

            return render_template(
                "auth/register.html",
                form_data=request.form,
            )

        # ----------------------------------------------------
        # Create account
        # ----------------------------------------------------

        try:

            user = register_user(
                full_name,
                email,
                password,
                confirm_password,
                role,
            )

        except AuthError as exc:

            flash(
                str(exc),
                "error",
            )

            return render_template(
                "auth/register.html",
                form_data=request.form,
            )

        except Exception:

            flash(
                "Registration failed. Please try again.",
                "error",
            )

            return render_template(
                "auth/register.html",
                form_data=request.form,
            )

        # ----------------------------------------------------
        # Login newly registered user
        # ----------------------------------------------------

        _login_user_session(user)

        flash(
            f"Welcome to EduCertify, {user.FullName}!",
            "success",
        )

        dashboard_endpoint = ROLE_DASHBOARD.get(
            user.Role,
            "public.home",
        )

        return redirect(
            url_for(dashboard_endpoint)
        )

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    return render_template(
        "auth/register.html",
        form_data={},
    )


# ============================================================
# LOGIN
# ============================================================

@auth_bp.route(
    "/login",
    methods=["GET", "POST"],
)
@guest_only
def login():
    """
    Authenticate an existing EduCertify user.
    """

    if request.method == "POST":

        email = (
            request.form.get("email")
            or ""
        ).strip().lower()

        password = (
            request.form.get("password")
            or ""
        )

        # ----------------------------------------------------
        # Basic validation
        # ----------------------------------------------------

        if not email or not password:

            flash(
                "Email and password are required.",
                "error",
            )

            return render_template(
                "auth/login.html",
                email=email,
            )

        # ----------------------------------------------------
        # Authenticate
        # ----------------------------------------------------

        try:

            user = authenticate_user(
                email,
                password,
            )

        except AuthError as exc:

            flash(
                str(exc),
                "error",
            )

            return render_template(
                "auth/login.html",
                email=email,
            )

        except Exception:

            flash(
                "Unable to log in. Please try again.",
                "error",
            )

            return render_template(
                "auth/login.html",
                email=email,
            )

        # ----------------------------------------------------
        # Create session
        # ----------------------------------------------------

        _login_user_session(user)

        flash(
            f"Welcome back, {user.FullName}!",
            "success",
        )

        # ----------------------------------------------------
        # Safe next URL
        # ----------------------------------------------------

        next_url = (
            request.args.get("next")
            or request.form.get("next")
        )

        if (
            next_url
            and next_url.startswith("/")
            and not next_url.startswith("//")
        ):
            return redirect(next_url)

        # ----------------------------------------------------
        # Role-based dashboard
        # ----------------------------------------------------

        dashboard_endpoint = ROLE_DASHBOARD.get(
            user.Role,
            "public.home",
        )

        return redirect(
            url_for(dashboard_endpoint)
        )

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    return render_template(
        "auth/login.html",
        email="",
    )


# ============================================================
# LOGOUT
# ============================================================

@auth_bp.route(
    "/logout",
    methods=["GET", "POST"],
)
def logout():
    """
    Log the current user out.
    """

    session.clear()

    flash(
        "You have been logged out.",
        "info",
    )

    return redirect(
        url_for("public.home")
    )


# ============================================================
# FORGOT PASSWORD
# ============================================================

@auth_bp.route(
    "/forgot-password",
    methods=["GET", "POST"],
)
@guest_only
def forgot_password():
    """
    Forgot-password flow.

    Email delivery is intentionally not connected yet.
    """

    if request.method == "POST":

        email = (
            request.form.get("email")
            or ""
        ).strip().lower()

        # Do not reveal whether an account exists.
        flash(
            "If an account with that email exists, "
            "a reset link has been sent.",
            "info",
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template(
        "auth/forgot_password.html"
    )


# ============================================================
# RESET PASSWORD
# ============================================================

@auth_bp.route(
    "/reset-password/<token>",
    methods=["GET", "POST"],
)
@guest_only
def reset_password(token):
    """
    Password-reset flow.

    Actual token validation and email delivery can be
    connected later.
    """

    if request.method == "POST":

        flash(
            "Password reset is not available "
            "in this demo build.",
            "info",
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template(
        "auth/reset_password.html",
        token=token,
    )