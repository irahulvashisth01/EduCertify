"""
EduCertify — Application Configuration

Supports:

- PostgreSQL on Render
- Microsoft SQL Server locally
- SQLite for local/demo testing

All secrets and environment-specific values are loaded
from environment variables / .env.
"""

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


BASE_DIR = os.path.abspath(
    os.path.dirname(__file__)
)


# ============================================================
# SQL SERVER
# ============================================================

def _build_sqlserver_uri():
    """
    Build a SQLAlchemy connection URI for Microsoft SQL Server
    through pyodbc.
    """

    server = os.environ.get(
        "SQL_SERVER",
        "localhost",
    )

    database = os.environ.get(
        "SQL_DATABASE",
        "EduCertify",
    )

    username = os.environ.get(
        "SQL_USERNAME",
        "",
    )

    password = os.environ.get(
        "SQL_PASSWORD",
        "",
    )

    driver = os.environ.get(
        "SQL_DRIVER",
        "ODBC Driver 18 for SQL Server",
    )

    trust_cert = os.environ.get(
        "SQL_TRUST_SERVER_CERTIFICATE",
        "yes",
    )

    # URL encode credentials/driver safely.
    driver_encoded = quote_plus(driver)

    if username and password:

        username_encoded = quote_plus(username)
        password_encoded = quote_plus(password)

        return (
            f"mssql+pyodbc://"
            f"{username_encoded}:"
            f"{password_encoded}@"
            f"{server}/{database}"
            f"?driver={driver_encoded}"
            f"&TrustServerCertificate={trust_cert}"
        )

    return (
        f"mssql+pyodbc://@"
        f"{server}/{database}"
        f"?driver={driver_encoded}"
        f"&trusted_connection=yes"
        f"&TrustServerCertificate={trust_cert}"
    )


# ============================================================
# DATABASE URI
# ============================================================

def _build_database_uri():
    """
    Select the database connection.

    Priority:

    1. DATABASE_URL
       PostgreSQL on Render

    2. DB_ENGINE=sqlite
       Local SQLite

    3. SQL Server
       Local/legacy configuration
    """

    database_url = os.environ.get(
        "DATABASE_URL",
        "",
    ).strip()

    # --------------------------------------------------------
    # Render PostgreSQL
    # --------------------------------------------------------

    if database_url:

        # Render may provide:
        #
        # postgres://
        #
        # or:
        #
        # postgresql://
        #
        # SQLAlchemy + psycopg requires:
        #
        # postgresql+psycopg://

        if database_url.startswith(
            "postgres://"
        ):

            database_url = database_url.replace(
                "postgres://",
                "postgresql+psycopg://",
                1,
            )

        elif database_url.startswith(
            "postgresql://"
        ):

            database_url = database_url.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )

        # Already correctly configured.
        elif database_url.startswith(
            "postgresql+psycopg://"
        ):

            pass

        return database_url

    # --------------------------------------------------------
    # Local SQLite
    # --------------------------------------------------------

    db_engine = os.environ.get(
        "DB_ENGINE",
        "mssql",
    ).strip().lower()

    if db_engine == "sqlite":

        sqlite_path = os.path.join(
            BASE_DIR,
            "educertify_dev.db",
        )

        return (
            "sqlite:///"
            + sqlite_path.replace("\\", "/")
        )

    # --------------------------------------------------------
    # Local SQL Server
    # --------------------------------------------------------

    return _build_sqlserver_uri()


# ============================================================
# BASE CONFIGURATION
# ============================================================

class Config:
    """
    Base configuration shared by all environments.
    """

    # --------------------------------------------------------
    # Flask
    # --------------------------------------------------------

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "dev-only-insecure-key",
    )

    # --------------------------------------------------------
    # SQLAlchemy
    # --------------------------------------------------------

    SQLALCHEMY_DATABASE_URI = (
        _build_database_uri()
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # --------------------------------------------------------
    # File uploads
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Allowed files
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Firebase
    # --------------------------------------------------------

    FIREBASE_ENABLED = (
        os.environ.get(
            "FIREBASE_ENABLED",
            "false",
        ).strip().lower()
        == "true"
    )

    FIREBASE_CREDENTIALS_PATH = os.environ.get(
        "FIREBASE_CREDENTIALS_PATH",
        "",
    )

    # --------------------------------------------------------
    # Supabase
    # --------------------------------------------------------

    SUPABASE_URL = os.environ.get(
        "SUPABASE_URL",
        "",
    ).strip()

    SUPABASE_SECRET_KEY = os.environ.get(
        "SUPABASE_SECRET_KEY",
        "",
    ).strip()

    SUPABASE_CERTIFICATE_BUCKET = os.environ.get(
        "SUPABASE_CERTIFICATE_BUCKET",
        "certificates",
    ).strip() or "certificates"

    # --------------------------------------------------------
    # Certificate verification
    # --------------------------------------------------------

    BASE_URL = os.environ.get(
        "BASE_URL",
        "http://127.0.0.1:5000",
    ).rstrip("/")

    # --------------------------------------------------------
    # Session
    # --------------------------------------------------------

    SESSION_COOKIE_HTTPONLY = True

    SESSION_COOKIE_SAMESITE = "Lax"

    PERMANENT_SESSION_LIFETIME = (
        60 * 60 * 8
    )


# ============================================================
# DEVELOPMENT
# ============================================================

class DevelopmentConfig(Config):
    DEBUG = True


# ============================================================
# PRODUCTION
# ============================================================

class ProductionConfig(Config):
    DEBUG = False

    SESSION_COOKIE_SECURE = True


# ============================================================
# TESTING
# ============================================================

class TestingConfig(Config):
    TESTING = True

    DEBUG = True

    WTF_CSRF_ENABLED = False

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///:memory:"
    )


# ============================================================
# CONFIG MAP
# ============================================================

config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


# ============================================================
# GET CONFIGURATION
# ============================================================

def get_config():
    """
    Select configuration based on FLASK_ENV.
    """

    env = os.environ.get(
        "FLASK_ENV",
        "development",
    ).strip().lower()

    return config_map.get(
        env,
        DevelopmentConfig,
    )