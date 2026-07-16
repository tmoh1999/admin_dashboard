import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("EMAIL_VERIFICATION_SALT", "test-salt")
os.environ.setdefault("REQUEST_MAIL_VERIFICATION", "False")

from app import create_app
from models import db


@pytest.fixture()
def client():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "REQUEST_MAIL_VERIFICATION": False,
            "MAIL_SUPPRESS_SEND": True,
        }
    )

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()
