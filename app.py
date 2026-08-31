"""
EduCertify — Application Entry Point

This module creates and configures the Flask application.

Responsibilities:
- Initialize Flask
- Load application configuration
- Configure templates and static files
- Create upload directories
- Initialize SQLAlchemy
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
    # Basic production configuration
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
    # Create required upload directories
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
    # Register routes / blueprints
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
    # Register security / request settings
    # --------------------------------------------------------

    register_security_settings(app)

    # --------------------------------------------------------
    # Application health check
    # --------------------------------------------------------

    register_health_check(app)

    return app


# ============================================================
# BLUEPRINT REGISTRATION
# ============================================================

def register_blueprints(app):
    """
    Register all EduCertify application blueprints.

    Keeping imports inside this function helps avoid circular
    imports during application initialization.
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
    # Public routes
    # --------------------------------------------------------

    app.register_blueprint(
        public_bp
    )

    # --------------------------------------------------------
    # Authentication routes
    # --------------------------------------------------------

    app.register_blueprint(
        auth_bp
    )

    # --------------------------------------------------------
    # Course discovery routes
    # --------------------------------------------------------

    app.register_blueprint(
        courses_bp
    )

    # --------------------------------------------------------
    # Student routes
    # --------------------------------------------------------

    app.register_blueprint(
        student_bp
    )

    # --------------------------------------------------------
    # Instructor routes
    # --------------------------------------------------------

    app.register_blueprint(
        instructor_bp
    )

    # --------------------------------------------------------
    # Admin routes
    # --------------------------------------------------------

    app.register_blueprint(
        admin_bp
    )

    # --------------------------------------------------------
    # Quiz routes
    # --------------------------------------------------------

    app.register_blueprint(
        quiz_bp
    )

    # --------------------------------------------------------
    # Certificate routes
    # --------------------------------------------------------

    app.register_blueprint(
        certificate_bp
    )

    # --------------------------------------------------------
    # REST API routes
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

    HTML pages are returned for normal browser requests.

    JSON responses are returned for /api/* requests.
    """

    @app.errorhandler(404)
    def not_found(error):
        """
        Handle 404 Not Found errors.
        """

        if request.path.startswith("/api/"):

            return jsonify(
                {
                    "success": False,
                    "message": "Resource not found.",
                }
            ), 404

        return (
            render_template(
                "errors/404.html"
            ),
            404,
        )

    @app.errorhandler(403)
    def forbidden(error):
        """
        Handle 403 Forbidden errors.
        """

        if request.path.startswith("/api/"):

            return jsonify(
                {
                    "success": False,
                    "message": "Access denied.",
                }
            ), 403

        return (
            render_template(
                "errors/403.html"
            ),
            403,
        )

    @app.errorhandler(500)
    def server_error(error):
        """
        Handle internal server errors.
        """

        # Important: rollback any failed database transaction.
        try:
            from database.database import db

            db.session.rollback()

        except Exception:
            pass

        if request.path.startswith("/api/"):

            return jsonify(
                {
                    "success": False,
                    "message": "Internal server error.",
                }
            ), 500

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
    Make common application information available
    inside all Jinja templates.
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
    Apply security-related Flask settings.

    Production settings are controlled primarily through
    config.py / environment variables.
    """

    # --------------------------------------------------------
    # Secure session cookies in production
    # --------------------------------------------------------

    if not app.debug:

        app.config.setdefault(
            "SESSION_COOKIE_HTTPONLY",
            True,
        )

        app.config.setdefault(
            "SESSION_COOKIE_SAMESITE",
            "Lax",
        )

        app.config.setdefault(
            "SESSION_COOKIE_SECURE",
            True,
        )

    # --------------------------------------------------------
    # Always protect session cookie from JavaScript
    # --------------------------------------------------------

    app.config["SESSION_COOKIE_HTTPONLY"] = True

    # --------------------------------------------------------
    # SameSite protection
    # --------------------------------------------------------

    app.config.setdefault(
        "SESSION_COOKIE_SAMESITE",
        "Lax",
    )


# ============================================================
# HEALTH CHECK
# ============================================================

def register_health_check(app):
    """
    Register a lightweight health endpoint.

    Render or external monitoring services can use:

        /health

    Expected response:

        {
            "status": "ok",
            "service": "EduCertify"
        }
    """

    @app.route("/health")
    def health_check():

        return jsonify(
            {
                "status": "ok",
                "service": "EduCertify",
            }
        ), 200


# ============================================================
# CREATE WSGI APPLICATION
# ============================================================

app = create_app()


# ============================================================
# LOCAL DEVELOPMENT SERVER
# ============================================================

if __name__ == "__main__":

    # Render supplies PORT as an environment variable.
    # For local development, use 5000.
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

    debug_mode = (
        app.config.get(
            "DEBUG",
            False,
        )
        and os.environ.get(
            "FLASK_ENV",
            "development",
        ).lower()
        == "development"
    )

    app.run(
        host=host,
        port=port,
        debug=debug_mode,
    )