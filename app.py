"""
EduCertify — Application Entry Point
=====================================

Full-stack Learning & Certification Platform

Responsibilities:
- Initialize Flask
- Load application configuration
- Configure templates and static files
- Create upload directories
- Initialize SQLAlchemy
- Bootstrap Admin account
- Register application blueprints
- Provide safe public-route fallback
- Register global error handlers
- Register template globals
- Configure secure cookies
- Provide PWA service-worker endpoint
- Provide health-check endpoint
- Provide production-ready WSGI application

Local:
    python app.py

Production:
    gunicorn app:app
"""

# ============================================================
# STANDARD LIBRARY
# ============================================================

import os


# ============================================================
# FLASK
# ============================================================

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_from_directory,
)


# ============================================================
# PROJECT IMPORTS
# ============================================================

from config import get_config
from database.database import init_db


# ============================================================
# APPLICATION FACTORY
# ============================================================

def create_app(config_class=None):
    """
    Create and configure the EduCertify Flask application.

    Parameters
    ----------
    config_class : optional
        Custom Flask configuration class.

    Returns
    -------
    Flask
        Fully configured EduCertify application.
    """

    # --------------------------------------------------------
    # CREATE FLASK APPLICATION
    # --------------------------------------------------------

    app = Flask(
        __name__,
        static_folder="static",
        static_url_path="/static",
        template_folder="templates",
    )

    # --------------------------------------------------------
    # LOAD CONFIGURATION
    # --------------------------------------------------------

    app.config.from_object(
        config_class or get_config()
    )

    # --------------------------------------------------------
    # APPLICATION DEFAULTS
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
    # APPLICATION INFORMATION
    # --------------------------------------------------------

    app.config.setdefault(
        "APP_NAME",
        "EduCertify",
    )

    app.config.setdefault(
        "APP_VERSION",
        "2.0.0",
    )

    # --------------------------------------------------------
    # CREATE REQUIRED DIRECTORIES
    # --------------------------------------------------------

    create_upload_directories(app)

    # --------------------------------------------------------
    # INITIALIZE DATABASE
    # --------------------------------------------------------

    init_db(app)

    # --------------------------------------------------------
    # BOOTSTRAP ADMIN
    # --------------------------------------------------------

    bootstrap_admin(app)

    # --------------------------------------------------------
    # REGISTER BLUEPRINTS
    # --------------------------------------------------------

    register_blueprints(app)

    # --------------------------------------------------------
    # PUBLIC HOME FALLBACK
    #
    # This prevents a blank 404 at "/" if public_routes.py
    # does not currently expose public.home.
    # --------------------------------------------------------

    register_public_fallback(app)

    # --------------------------------------------------------
    # PWA ROUTES
    # --------------------------------------------------------

    register_pwa_routes(app)

    # --------------------------------------------------------
    # PWA DIAGNOSTICS
    # --------------------------------------------------------

    register_pwa_diagnostics(app)

    # --------------------------------------------------------
    # ERROR HANDLERS
    # --------------------------------------------------------

    register_error_handlers(app)

    # --------------------------------------------------------
    # TEMPLATE GLOBALS
    # --------------------------------------------------------

    register_template_globals(app)

    # --------------------------------------------------------
    # SECURITY SETTINGS
    # --------------------------------------------------------

    register_security_settings(app)

    # --------------------------------------------------------
    # HEALTH CHECK
    # --------------------------------------------------------

    register_health_check(app)

    # --------------------------------------------------------
    # APPLICATION STARTUP MESSAGE
    # --------------------------------------------------------

    print_startup_information(app)

    return app


# ============================================================
# DIRECTORY SETUP
# ============================================================

def create_upload_directories(app):
    """
    Create all configured upload directories.
    """

    upload_folders = (
        app.config.get("UPLOAD_FOLDER"),
        app.config.get("COURSE_UPLOAD_FOLDER"),
        app.config.get("LESSON_UPLOAD_FOLDER"),
        app.config.get("CERTIFICATE_UPLOAD_FOLDER"),
    )

    for folder in upload_folders:

        if not folder:
            continue

        try:

            os.makedirs(
                folder,
                exist_ok=True,
            )

        except OSError as exc:

            print(
                "[EduCertify] Warning: "
                f"Could not create upload directory: {folder}"
            )

            print(
                f"[EduCertify] Directory error: {exc}"
            )


# ============================================================
# ADMIN BOOTSTRAP
# ============================================================

def bootstrap_admin(app):
    """
    Create or activate the initial Admin account.

    Environment variables:

        ADMIN_EMAIL
        ADMIN_PASSWORD
        ADMIN_NAME

    Rules:
    - Creates Admin only if email does not exist.
    - Never overwrites an existing password.
    - Converts the matching account to Admin.
    - Activates the Admin account.
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
    # ADMIN CONFIGURATION MISSING
    # --------------------------------------------------------

    if not admin_email or not admin_password:

        print(
            "[EduCertify] Admin bootstrap skipped. "
            "ADMIN_EMAIL or ADMIN_PASSWORD is missing."
        )

        return

    try:

        with app.app_context():

            from database.database import db
            from database.models import User
            from utils.security import hash_password

            # ------------------------------------------------
            # FIND USER
            # ------------------------------------------------

            user = (
                User.query
                .filter_by(
                    Email=admin_email
                )
                .first()
            )

            # ------------------------------------------------
            # CREATE ADMIN
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
                    "[EduCertify] Admin account created: "
                    f"{admin_email}"
                )

                return

            # ------------------------------------------------
            # UPDATE EXISTING ACCOUNT
            # ------------------------------------------------

            changed = False

            if user.Role != "Admin":

                user.Role = "Admin"
                changed = True

            if not user.IsActive:

                user.IsActive = True
                changed = True

            if not user.FullName and admin_name:

                user.FullName = admin_name
                changed = True

            if changed:

                db.session.commit()

                print(
                    "[EduCertify] Existing Admin account "
                    "updated successfully."
                )

            else:

                print(
                    "[EduCertify] Admin account already exists."
                )

    except Exception as exc:

        try:

            from database.database import db

            db.session.rollback()

        except Exception:
            pass

        print(
            "[EduCertify] Admin bootstrap warning: "
            f"{exc}"
        )


# ============================================================
# BLUEPRINT REGISTRATION
# ============================================================

def register_blueprints(app):
    """
    Register all EduCertify application blueprints.
    """

    try:

        from routes.public_routes import public_bp
        from routes.auth_routes import auth_bp
        from routes.course_routes import courses_bp
        from routes.student_routes import student_bp
        from routes.instructor_routes import instructor_bp
        from routes.admin_routes import admin_bp
        from routes.quiz_routes import quiz_bp
        from routes.certificate_routes import certificate_bp
        from routes.api_routes import api_bp

    except ImportError as exc:

        print(
            "[EduCertify] Blueprint import error:"
            f" {exc}"
        )

        raise

    # --------------------------------------------------------
    # PUBLIC
    # --------------------------------------------------------

    app.register_blueprint(
        public_bp
    )

    # --------------------------------------------------------
    # AUTHENTICATION
    # --------------------------------------------------------

    app.register_blueprint(
        auth_bp
    )

    # --------------------------------------------------------
    # COURSES
    # --------------------------------------------------------

    app.register_blueprint(
        courses_bp
    )

    # --------------------------------------------------------
    # STUDENT
    # --------------------------------------------------------

    app.register_blueprint(
        student_bp
    )

    # --------------------------------------------------------
    # INSTRUCTOR
    # --------------------------------------------------------

    app.register_blueprint(
        instructor_bp
    )

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    app.register_blueprint(
        admin_bp
    )

    # --------------------------------------------------------
    # QUIZ
    # --------------------------------------------------------

    app.register_blueprint(
        quiz_bp
    )

    # --------------------------------------------------------
    # CERTIFICATE
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
# PUBLIC HOME FALLBACK
# ============================================================

def register_public_fallback(app):
    """
    Register a fallback homepage only when no "/" route
    has already been registered.

    This protects the application from returning 404 when
    public_routes.py is incomplete or temporarily missing
    the public.home endpoint.
    """

    root_exists = False

    for rule in app.url_map.iter_rules():

        if rule.rule == "/":

            root_exists = True
            break

    if root_exists:

        print(
            "[EduCertify] Homepage route detected."
        )

        return

    # --------------------------------------------------------
    # FALLBACK HOME ROUTE
    # --------------------------------------------------------

    @app.route(
        "/",
        endpoint="educertify_home_fallback",
    )
    def educertify_home_fallback():

        return render_template(
            "index.html"
        )

    print(
        "[EduCertify] WARNING: public.home route "
        "was not detected."
    )

    print(
        "[EduCertify] Fallback homepage route "
        "registered at /"
    )


# ============================================================
# PWA ROUTES
# ============================================================

def register_pwa_routes(app):
    """
    Register Progressive Web App related routes.

    Service worker must be available from the root scope
    so it can control the complete EduCertify application.
    """

    @app.route(
        "/service-worker.js",
        methods=["GET"],
        endpoint="service_worker",
    )
    def service_worker():
        """
        Serve the EduCertify service worker from the site root.

        The physical file remains:
            static/service-worker.js

        The browser receives it from:
            /service-worker.js

        This allows the service worker to use:
            scope="/"
        and control the complete EduCertify application.
        """

        response = send_from_directory(
            app.static_folder,
            "service-worker.js",
            mimetype="application/javascript",
            max_age=0,
        )

        response.headers["Cache-Control"] = (
            "no-cache, no-store, must-revalidate"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response

    # --------------------------------------------------------
    # OPTIONAL ROOT MANIFEST ALIAS
    # --------------------------------------------------------

    @app.route(
        "/manifest.json",
        methods=["GET"],
        endpoint="root_manifest",
    )
    def root_manifest():
        """
        Serve the PWA manifest from the site root.
        """

        response = send_from_directory(
            app.static_folder,
            "manifest.json",
            mimetype="application/manifest+json",
            max_age=0,
        )

        response.headers["Cache-Control"] = (
            "no-cache, no-store, must-revalidate"
        )

        return response


# ============================================================
# PWA DIAGNOSTICS
# ============================================================

def register_pwa_diagnostics(app):
    """
    Register a small diagnostics endpoint for local PWA testing.

    GET /pwa-status

    This does not expose secrets. It only confirms that the
    root PWA resources exist and are being served correctly.
    """

    @app.route(
        "/pwa-status",
        methods=["GET"],
        endpoint="pwa_status",
    )
    def pwa_status():

        service_worker_path = os.path.join(
            app.static_folder,
            "service-worker.js",
        )

        manifest_path = os.path.join(
            app.static_folder,
            "manifest.json",
        )

        return jsonify(
            {
                "success": True,
                "service": "EduCertify",
                "pwa": {
                    "service_worker": (
                        "/service-worker.js"
                    ),
                    "service_worker_file_exists": (
                        os.path.isfile(service_worker_path)
                    ),
                    "manifest": "/manifest.json",
                    "manifest_file_exists": (
                        os.path.isfile(manifest_path)
                    ),
                    "expected_scope": "/",
                },
            }
        )


# ============================================================
# ERROR HANDLERS
# ============================================================

def register_error_handlers(app):
    """
    Register global application error handlers.

    Browser requests receive HTML.

    API requests receive JSON.
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
                        "error": "not_found",
                        "message": "Resource not found.",
                        "path": request.path,
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
                        "error": "forbidden",
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
    # 405
    # --------------------------------------------------------

    @app.errorhandler(405)
    def method_not_allowed(error):

        if request.path.startswith("/api/"):

            return (
                jsonify(
                    {
                        "success": False,
                        "error": "method_not_allowed",
                        "message": "HTTP method not allowed.",
                    }
                ),
                405,
            )

        return (
            render_template(
                "errors/404.html"
            ),
            405,
        )

    # --------------------------------------------------------
    # 413
    # --------------------------------------------------------

    @app.errorhandler(413)
    def request_too_large(error):

        if request.path.startswith("/api/"):

            return (
                jsonify(
                    {
                        "success": False,
                        "error": "request_too_large",
                        "message": "Uploaded file is too large.",
                    }
                ),
                413,
            )

        return (
            render_template(
                "errors/500.html"
            ),
            413,
        )

    # --------------------------------------------------------
    # 500
    # --------------------------------------------------------

    @app.errorhandler(500)
    def server_error(error):

        # ----------------------------------------------------
        # ROLLBACK DATABASE
        # ----------------------------------------------------

        try:

            from database.database import db

            db.session.rollback()

        except Exception:
            pass

        # ----------------------------------------------------
        # API RESPONSE
        # ----------------------------------------------------

        if request.path.startswith("/api/"):

            return (
                jsonify(
                    {
                        "success": False,
                        "error": "internal_server_error",
                        "message": "Internal server error.",
                    }
                ),
                500,
            )

        # ----------------------------------------------------
        # HTML RESPONSE
        # ----------------------------------------------------

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
            "app_name": app.config.get(
                "APP_NAME",
                "EduCertify",
            ),

            "app_version": app.config.get(
                "APP_VERSION",
                "2.0.0",
            ),

            "current_year": 2026,
        }


# ============================================================
# SECURITY SETTINGS
# ============================================================

def register_security_settings(app):
    """
    Configure secure session cookies.
    """

    # --------------------------------------------------------
    # HTTP ONLY
    # --------------------------------------------------------

    app.config["SESSION_COOKIE_HTTPONLY"] = True

    # --------------------------------------------------------
    # SAME SITE
    # --------------------------------------------------------

    app.config.setdefault(
        "SESSION_COOKIE_SAMESITE",
        "Lax",
    )

    # --------------------------------------------------------
    # SECURE COOKIE
    #
    # Enabled automatically for non-debug / production.
    # --------------------------------------------------------

    if not app.debug:

        app.config["SESSION_COOKIE_SECURE"] = True

    else:

        app.config.setdefault(
            "SESSION_COOKIE_SECURE",
            False,
        )


# ============================================================
# HEALTH CHECK
# ============================================================

def register_health_check(app):
    """
    Register application health endpoint.

    GET /health
    """

    @app.route(
        "/health",
        endpoint="health_check",
    )
    def health_check():

        return (
            jsonify(
                {
                    "status": "ok",
                    "service": "EduCertify",
                    "version": app.config.get(
                        "APP_VERSION",
                        "2.0.0",
                    ),
                }
            ),
            200,
        )


# ============================================================
# ROUTE DEBUG INFORMATION
# ============================================================

def print_startup_information(app):
    """
    Print useful startup information for local development.
    """

    print()
    print("=" * 64)
    print("                 EDUCERTIFY")
    print("       Learning & Certification Platform")
    print("=" * 64)

    print(
        f"Application : "
        f"{app.config.get('APP_NAME', 'EduCertify')}"
    )

    print(
        f"Version     : "
        f"{app.config.get('APP_VERSION', '1.0.0')}"
    )

    print(
        f"Debug       : "
        f"{app.debug}"
    )

    print(
        f"Templates   : "
        f"{app.template_folder}"
    )

    print(
        f"Static      : "
        f"{app.static_folder}"
    )

    print()
    print("Important URLs:")
    print("  Homepage       : /")
    print("  Health         : /health")
    print("  Manifest       : /manifest.json")
    print("  Service Worker : /service-worker.js")
    print("  PWA Status      : /pwa-status")
    print()

    # --------------------------------------------------------
    # CHECK HOMEPAGE
    # --------------------------------------------------------

    home_rules = [
        rule
        for rule in app.url_map.iter_rules()
        if rule.rule == "/"
    ]

    if home_rules:

        print(
            "[EduCertify] Homepage: READY"
        )

        for rule in home_rules:

            print(
                f"  Endpoint: {rule.endpoint}"
            )

    else:

        print(
            "[EduCertify] Homepage: NOT FOUND"
        )

    # --------------------------------------------------------
    # PRINT ROUTE COUNT
    # --------------------------------------------------------

    route_count = len(
        list(
            app.url_map.iter_rules()
        )
    )

    pwa_routes = {
        rule.rule
        for rule in app.url_map.iter_rules()
    }

    print(
        "[EduCertify] PWA routes:"
    )

    print(
        "  /service-worker.js : "
        f"{'READY' if '/service-worker.js' in pwa_routes else 'MISSING'}"
    )

    print(
        "  /manifest.json     : "
        f"{'READY' if '/manifest.json' in pwa_routes else 'MISSING'}"
    )

    print(
        "  /pwa-status        : "
        f"{'READY' if '/pwa-status' in pwa_routes else 'MISSING'}"
    )

    print(
        f"[EduCertify] Registered routes: "
        f"{route_count}"
    )

    print("=" * 64)
    print()


# ============================================================
# CREATE WSGI APPLICATION
# ============================================================

app = create_app()


# ============================================================
# LOCAL DEVELOPMENT SERVER
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # HOST
    # --------------------------------------------------------

    host = os.environ.get(
        "HOST",
        "127.0.0.1",
    )

    # --------------------------------------------------------
    # PORT
    # --------------------------------------------------------

    try:

        port = int(
            os.environ.get(
                "PORT",
                5000,
            )
        )

    except ValueError:

        port = 5000

    # --------------------------------------------------------
    # ENVIRONMENT
    # --------------------------------------------------------

    flask_env = os.environ.get(
        "FLASK_ENV",
        "development",
    ).lower()

    # --------------------------------------------------------
    # DEBUG
    # --------------------------------------------------------

    debug_mode = (
        flask_env == "development"
        and bool(
            app.config.get(
                "DEBUG",
                False,
            )
        )
    )

    # --------------------------------------------------------
    # START SERVER
    # --------------------------------------------------------

    print(
        "[EduCertify] Starting Flask development server..."
    )

    print(
        f"[EduCertify] Open: "
        f"http://{host}:{port}/"
    )

    app.run(
        host=host,
        port=port,
        debug=debug_mode,
    )