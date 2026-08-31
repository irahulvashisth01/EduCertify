"""
EduCertify — Application entry point.

app.py stays thin: it initializes Flask, wires up the database, registers
blueprints, and defines global error handlers. All business logic lives in
services/, and all HTTP handling lives in routes/.
"""

import os
from flask import Flask, render_template

from config import get_config
from database.database import init_db


def create_app(config_class=None):
    app = Flask(__name__)
    app.config.from_object(config_class or get_config())

    # Ensure upload directories exist
    for folder in (
        app.config["UPLOAD_FOLDER"],
        app.config["COURSE_UPLOAD_FOLDER"],
        app.config["LESSON_UPLOAD_FOLDER"],
        app.config["CERTIFICATE_UPLOAD_FOLDER"],
    ):
        os.makedirs(folder, exist_ok=True)

    init_db(app)
    register_blueprints(app)
    register_error_handlers(app)
    register_template_globals(app)

    return app


def register_blueprints(app):
    from routes.public_routes import public_bp
    from routes.auth_routes import auth_bp
    from routes.course_routes import courses_bp
    from routes.student_routes import student_bp
    from routes.instructor_routes import instructor_bp
    from routes.admin_routes import admin_bp
    from routes.quiz_routes import quiz_bp
    from routes.certificate_routes import certificate_bp
    from routes.api_routes import api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(instructor_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(certificate_bp)
    app.register_blueprint(api_bp)


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500


def register_template_globals(app):
    @app.context_processor
    def inject_globals():
        return {"app_name": "EduCertify"}


app = create_app()

if __name__ == "__main__":
    debug_mode = app.config.get("DEBUG", True)
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
