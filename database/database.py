"""
Central SQLAlchemy database instance.

Imported by app.py (to bind to the Flask app) and by database/models.py
(to define models). Keeping the `db` object in its own module avoids
circular imports between app.py and models.py.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """Bind SQLAlchemy to the Flask app and create tables if they don't exist."""
    db.init_app(app)
    with app.app_context():
        # Import models here so they are registered on `db.metadata`
        # before create_all() is called.
        from database import models  # noqa: F401
        db.create_all()
