"""
Application configuration.

All secrets and environment-specific values are loaded from the .env file.
Never hardcode passwords, API keys, or connection secrets here.
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
    driver = os.environ.get("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    trust_cert = os.environ.get("SQL_TRUST_SERVER_CERTIFICATE", "yes")

    driver_encoded = driver.replace(" ", "+")

    if username and password:
        return (
            f"mssql+pyodbc://{username}:{password}@{server}/{database}"
            f"?driver={driver_encoded}&TrustServerCertificate={trust_cert}"
        )
    # Windows integrated auth fallback (no username/password supplied)
    return (
        f"mssql+pyodbc://@{server}/{database}"
        f"?driver={driver_encoded}&trusted_connection=yes&TrustServerCertificate={trust_cert}"
    )


class Config:
    """Base configuration shared by all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")

    # DB_ENGINE = "mssql" (production/real dev) or "sqlite" (local demo without SQL Server)
    DB_ENGINE = os.environ.get("DB_ENGINE", "mssql").lower()

    if DB_ENGINE == "sqlite":
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'educertify_dev.db')}"
    else:
        SQLALCHEMY_DATABASE_URI = _build_sqlserver_uri()

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # File uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    COURSE_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, "courses")
    LESSON_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, "lessons")
    CERTIFICATE_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, "certificates")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_SIZE_MB", 10)) * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "zip"}

    # Firebase (optional)
    FIREBASE_ENABLED = os.environ.get("FIREBASE_ENABLED", "false").lower() == "true"
    FIREBASE_CREDENTIALS_PATH = os.environ.get("FIREBASE_CREDENTIALS_PATH", "")

    # Certificate verification
    BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")

    # Session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 hours


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
