from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """Bind SQLAlchemy to the Flask app and create tables if they don't exist."""

    db.init_app(app)

    with app.app_context():
        from database import models  # noqa: F401

        db.create_all()