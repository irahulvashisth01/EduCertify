"""
Shared pytest fixtures for the EduCertify test suite.

Each test run uses a fresh in-memory SQLite database (via TestingConfig)
so tests never touch real data and can run in any environment without
SQL Server installed.
"""

import pytest
from app import create_app
from config import TestingConfig
from database.database import db as _db


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    return _db


def register(client, full_name, email, password, role="Student"):
    return client.post(
        "/auth/register",
        data={
            "full_name": full_name,
            "email": email,
            "password": password,
            "confirm_password": password,
            "role": role,
        },
        follow_redirects=True,
    )


def login(client, email, password):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )
