"""
EduCertify — Application Entry Point

Responsibilities:
- Initialize Flask
- Load application configuration
- Configure templates and static files
- Create upload directories
- Initialize SQLAlchemy
- Bootstrap the Admin account from environment variables
- Register application blueprints
- Register global error handlers
- Register template globals
- Provide a production-ready WSGI application

Production server:
    gunicorn app:app

Local development:
    python app.py
"""

import os

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
)

from config import get_config
from database.database import init_db


# ============================================================
# APPLICATION FACTORY
# ============================================================

def create_app(config_class=None):
    """
    Create and configure the EduCertify Flask application.

    Args:
        config_class:
            Optional Flask configuration class.

    Returns:
        Flask: Configured Flask application.
    """

    # --------------------------------------------------------
    # Create Flask application
    # --------------------------------------------------------

    app = Flask(
        __name__,
        static_folder="static",
        static_url_path="/static",
        template_folder="templates",
    )

    # --------------------------------------------------------
    # Load configuration
    # --------------------------------------------------------

    app.config.from_object(
        config_class or get_config()
    )

    # --------------------------------------------------------
    # Production defaults
    # --------------------------------------------------------

    app.config.setdefault(
        "JSON_SORT_KEYS",
        False,
    )

    app.config.setdefault(
        "MAX_CONTENT_LENGTH",
        10 * 1024 * 1024,
    )

    # --------------------------------------------------------
    # Create upload directories
    # --------------------------------------------------------

    upload_folders = (
        app.config.get("UPLOAD_FOLDER"),
        app.config.get("COURSE_UPLOAD_FOLDER"),
        app.config.get("LESSON_UPLOAD_FOLDER"),
        app.config.get("CERTIFICATE_UPLOAD_FOLDER"),
    )

    for folder in upload_folders:

        if folder:
            os.makedirs(
                folder,
                exist_ok=True,
            )

    # --------------------------------------------------------
    # Initialize database
    # --------------------------------------------------------

    init_db(app)

    # --------------------------------------------------------
    # Create Admin account if required
    # --------------------------------------------------------

    bootstrap_admin(app)

    # --------------------------------------------------------
    # Register application blueprints
    # --------------------------------------------------------

    register_blueprints(app)

    # --------------------------------------------------------
    # Register error handlers
    # --------------------------------------------------------

    register_error_handlers(app)

    # --------------------------------------------------------
    # Register template globals
    # --------------------------------------------------------

    register_template_globals(app)

    # --------------------------------------------------------
    # Register security settings
    # --------------------------------------------------------

    register_security_settings(app)

    # --------------------------------------------------------
    # Register health check
    # --------------------------------------------------------

    register_health_check(app)

    return app


# ============================================================
# ADMIN BOOTSTRAP
# ============================================================

def bootstrap_admin(app):
    """
    Create the initial Admin account using Render environment
    variables.

    Required environment variables:

        ADMIN_EMAIL
        ADMIN_PASSWORD

    Optional:

        ADMIN_NAME

    IMPORTANT:
    - Admin is created only when the email does not already exist.
    - Existing Admin passwords are NOT overwritten.
    - Existing accounts are upgraded to Admin only when their
      email matches ADMIN_EMAIL.
    - Admin accounts are automatically activated.
    """

    admin_email = os.environ.get(
        "ADMIN_EMAIL",
        "",
    ).strip().lower()

    admin_password = os.environ.get(
        "ADMIN_PASSWORD",
        "",
    )

    admin_name = os.environ.get(
        "ADMIN_NAME",
        "EduCertify Administrator",
    ).strip()

    # --------------------------------------------------------
    # Environment variables not configured
    # --------------------------------------------------------

    if not admin_email or not admin_password:

        print(
            "[EduCertify] Admin bootstrap skipped."
            " ADMIN_EMAIL or ADMIN_PASSWORD is missing."
        )

        return

    try:

        with app.app_context():

            from database.database import db
            from database.models import User
            from utils.security import hash_password

            # ------------------------------------------------
            # Find account by email
            # ------------------------------------------------

            user = (
                User.query
                .filter_by(Email=admin_email)
                .first()
            )

            # ------------------------------------------------
            # Create new Admin
            # ------------------------------------------------

            if user is None:

                user = User(
                    FullName=(
                        admin_name
                        or "EduCertify Administrator"
                    ),
                    Email=admin_email,
                    PasswordHash=hash_password(
                        admin_password
                    ),
                    Role="Admin",
                    IsActive=True,
                )

                db.session.add(user)
                db.session.commit()

                print(
                    "[EduCertify] Admin account created:"
                    f" {admin_email}"
                )

                return

            # ------------------------------------------------
            # Existing matching account
            # ------------------------------------------------

            changed = False

            if user.Role != "Admin":

                user.Role = "Admin"
                changed = True

            if not user.IsActive:

                user.IsActive = True
                changed = True

            if (
                not user.FullName
                and admin_name
            ):

                user.FullName = admin_name
                changed = True

            if changed:

                db.session.commit()

                print(
                    "[EduCertify] Existing Admin account "
                    "updated."
                )

            else:

                print(
                    "[EduCertify] Admin account already "
                    "exists."
                )

    except Exception as exc:

        try:

            from database.database import db

            db.session.rollback()

        except Exception:

            pass

        # ----------------------------------------------------
        # Do not stop the entire application if Admin
        # bootstrap fails.
        # ----------------------------------------------------

        print(
            "[EduCertify] Admin bootstrap warning:"
            f" {exc}"
        )


# ============================================================
# BLUEPRINT REGISTRATION
# ============================================================

def register_blueprints(app):
    """
    Register all EduCertify application blueprints.

    Imports are intentionally inside this function to reduce
    circular-import problems during application startup.
    """

    from routes.public_routes import public_bp
    from routes.auth_routes import auth_bp
    from routes.course_routes import courses_bp
    from routes.student_routes import student_bp
    from routes.instructor_routes import instructor_bp
    from routes.admin_routes import admin_bp
    from routes.quiz_routes import quiz_bp
    from routes.certificate_routes import certificate_bp
    from routes.api_routes import api_bp

    # --------------------------------------------------------
    # Public
    # --------------------------------------------------------

    app.register_blueprint(
        public_bp
    )

    # --------------------------------------------------------
    # Authentication
    # --------------------------------------------------------

    app.register_blueprint(
        auth_bp
    )

    # --------------------------------------------------------
    # Course discovery
    # --------------------------------------------------------

    app.register_blueprint(
        courses_bp
    )

    # --------------------------------------------------------
    # Student
    # --------------------------------------------------------

    app.register_blueprint(
        student_bp
    )

    # --------------------------------------------------------
    # Instructor
    # --------------------------------------------------------

    app.register_blueprint(
        instructor_bp
    )

    # --------------------------------------------------------
    # Admin
    # --------------------------------------------------------

    app.register_blueprint(
        admin_bp
    )

    # --------------------------------------------------------
    # Quiz
    # --------------------------------------------------------

    app.register_blueprint(
        quiz_bp
    )

    # --------------------------------------------------------
    # Certificate
    # --------------------------------------------------------

    app.register_blueprint(
        certificate_bp
    )

    # --------------------------------------------------------
    # REST API
    # --------------------------------------------------------

    app.register_blueprint(
        api_bp
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

def register_error_handlers(app):
    """
    Register global HTTP error handlers.

    Browser requests receive HTML error pages.

    /api/* requests receive JSON responses.
    """

    # --------------------------------------------------------
    # 404
    # --------------------------------------------------------

    @app.errorhandler(404)
    def not_found(error):

        if request.path.startswith("/api/"):

            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Resource not found.",
                    }
                ),
                404,
            )

        return (
            render_template(
                "errors/404.html"
            ),
            404,
        )

    # --------------------------------------------------------
    # 403
    # --------------------------------------------------------

    @app.errorhandler(403)
    def forbidden(error):

        if request.path.startswith("/api/"):

            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Access denied.",
                    }
                ),
                403,
            )

        return (
            render_template(
                "errors/403.html"
            ),
            403,
        )

    # --------------------------------------------------------
    # 500
    # --------------------------------------------------------

    @app.errorhandler(500)
    def server_error(error):

        # ----------------------------------------------------
        # Roll back failed database transaction.
        # ----------------------------------------------------

        try:

            from database.database import db

            db.session.rollback()

        except Exception:

            pass

        if request.path.startswith("/api/"):

            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Internal server error.",
                    }
                ),
                500,
            )

        return (
            render_template(
                "errors/500.html"
            ),
            500,
        )


# ============================================================
# TEMPLATE GLOBALS
# ============================================================

def register_template_globals(app):
    """
    Make common application information available inside
    every Jinja template.
    """

    @app.context_processor
    def inject_globals():

        return {
            "app_name": "EduCertify",
        }


# ============================================================
# SECURITY SETTINGS
# ============================================================

def register_security_settings(app):
    """
    Configure secure Flask session cookies.

    These settings are especially important for the deployed
    HTTPS version on Render.
    """

    # --------------------------------------------------------
    # Always protect cookies from JavaScript
    # --------------------------------------------------------

    app.config["SESSION_COOKIE_HTTPONLY"] = True

    # --------------------------------------------------------
    # Prevent cross-site cookie sending in most situations
    # --------------------------------------------------------

    app.config.setdefault(
        "SESSION_COOKIE_SAMESITE",
        "Lax",
    )

    # --------------------------------------------------------
    # HTTPS production environment
    # --------------------------------------------------------

    if not app.debug:

        app.config["SESSION_COOKIE_SECURE"] = True


# ============================================================
# HEALTH CHECK
# ============================================================

def register_health_check(app):
    """
    Lightweight endpoint used to verify that the application
    is running correctly.

    URL:
        /health
    """

    @app.route("/health")
    def health_check():

        return (
            jsonify(
                {
                    "status": "ok",
                    "service": "EduCertify",
                }
            ),
            200,
        )


# ============================================================
# CREATE WSGI APPLICATION
# ============================================================

app = create_app()


# ============================================================
# LOCAL DEVELOPMENT SERVER
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # Render provides PORT automatically.
    # Local development defaults to 5000.
    # --------------------------------------------------------

    port = int(
        os.environ.get(
            "PORT",
            5000,
        )
    )

    host = os.environ.get(
        "HOST",
        "0.0.0.0",
    )

    # --------------------------------------------------------
    # Only enable debug during local development.
    # --------------------------------------------------------

    flask_env = os.environ.get(
        "FLASK_ENV",
        "production",
    ).lower()

    debug_mode = (
        app.config.get(
            "DEBUG",
            False,
        )
        and flask_env == "development"
    )

    app.run(
        host=host,
        port=port,
        debug=debug_mode,
    )