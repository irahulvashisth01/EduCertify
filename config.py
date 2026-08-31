"""
EduCertify — Application configuration.

Supports:
- PostgreSQL on Render
- Microsoft SQL Server locally
- SQLite for local/demo testing

All secrets and environment-specific values are loaded
from environment variables / .env.
"""

import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _build_sqlserver_uri():
    """Build a SQLAlchemy connection URI for Microsoft SQL Server via pyodbc."""

    server = os.environ.get("SQL_SERVER", "localhost")
    database = os.environ.get("SQL_DATABASE", "EduCertify")
    username = os.environ.get("SQL_USERNAME", "")
    password = os.environ.get("SQL_PASSWORD", "")
    driver = os.environ.get(
        "SQL_DRIVER",
        "ODBC Driver 18 for SQL Server"
    )
    trust_cert = os.environ.get(
        "SQL_TRUST_SERVER_CERTIFICATE",
        "yes"
    )

    driver_encoded = driver.replace(" ", "+")

    if username and password:
        return (
            f"mssql+pyodbc://{username}:{password}@{server}/{database}"
            f"?driver={driver_encoded}"
            f"&TrustServerCertificate={trust_cert}"
        )

    return (
        f"mssql+pyodbc://@{server}/{database}"
        f"?driver={driver_encoded}"
        f"&trusted_connection=yes"
        f"&TrustServerCertificate={trust_cert}"
    )


def _build_database_uri():
    """
    Select the database connection.

    Priority:
    1. DATABASE_URL — used by Render PostgreSQL
    2. DB_ENGINE=sqlite — local SQLite
    3. SQL Server — local/legacy configuration
    """

    database_url = os.environ.get("DATABASE_URL", "").strip()

    # Render PostgreSQL
    if database_url:
        # Render may provide postgresql:// or postgres://.
        # Convert them to the psycopg SQLAlchemy dialect.
        if database_url.startswith("postgres://"):
            database_url = database_url.replace(
                "postgres://",
                "postgresql+psycopg://",
                1,
            )
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )

        return database_url

    # Local SQLite
    db_engine = os.environ.get(
        "DB_ENGINE",
        "mssql"
    ).lower()

    if db_engine == "sqlite":
        return (
            "sqlite:///"
            + os.path.join(BASE_DIR, "educertify_dev.db")
        )

    # Local SQL Server
    return _build_sqlserver_uri()


class Config:
    """Base configuration shared by all environments."""

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "dev-only-insecure-key",
    )

    SQLALCHEMY_DATABASE_URI = _build_database_uri()

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # File uploads
    UPLOAD_FOLDER = os.path.join(
        BASE_DIR,
        "uploads",
    )

    COURSE_UPLOAD_FOLDER = os.path.join(
        UPLOAD_FOLDER,
        "courses",
    )

    LESSON_UPLOAD_FOLDER = os.path.join(
        UPLOAD_FOLDER,
        "lessons",
    )

    CERTIFICATE_UPLOAD_FOLDER = os.path.join(
        UPLOAD_FOLDER,
        "certificates",
    )

    MAX_CONTENT_LENGTH = (
        int(
            os.environ.get(
                "MAX_UPLOAD_SIZE_MB",
                10,
            )
        )
        * 1024
        * 1024
    )

    ALLOWED_IMAGE_EXTENSIONS = {
        "png",
        "jpg",
        "jpeg",
        "gif",
        "webp",
    }

    ALLOWED_DOCUMENT_EXTENSIONS = {
        "pdf",
        "doc",
        "docx",
        "ppt",
        "pptx",
        "zip",
    }

    # Firebase
    FIREBASE_ENABLED = (
        os.environ.get(
            "FIREBASE_ENABLED",
            "false",
        ).lower()
        == "true"
    )

    FIREBASE_CREDENTIALS_PATH = os.environ.get(
        "FIREBASE_CREDENTIALS_PATH",
        "",
    )

    # Certificate verification
    BASE_URL = os.environ.get(
        "BASE_URL",
        "http://127.0.0.1:5000",
    )

    # Session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    PERMANENT_SESSION_LIFETIME = (
        60 * 60 * 8
    )


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False

    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///:memory:"
    )


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config():
    """
    Select configuration from FLASK_ENV.
    """

    env = os.environ.get(
        "FLASK_ENV",
        "development",
    ).lower()

    return config_map.get(
        env,
        DevelopmentConfig,
    )