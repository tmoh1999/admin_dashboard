import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("EMAIL_VERIFICATION_SALT", "test-salt")
os.environ.setdefault("REQUEST_MAIL_VERIFICATION", "False")

from app import create_app
from models import User, db


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


def test_register_creates_user(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "tester",
            "email": "tester@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["message"].startswith("Registration successful")
    assert payload["user"]["username"] == "tester"

    user = User.query.filter_by(username="tester").first()
    assert user is not None
    assert user.check_password("password123")
    assert user.is_email_verified is True


def test_login_returns_tokens_for_valid_credentials(client):
    user = User(username="loginuser", email="login@example.com")
    user.set_password("password123")
    user.is_email_verified = True
    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={"login": "loginuser", "password": "password123"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["message"] == "Login successful!"
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["user"]["username"] == "loginuser"


def test_login_fails_with_invalid_password(client):
    user = User(username="badpass", email="badpass@example.com")
    user.set_password("password123")
    user.is_email_verified = True
    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={"login": "badpass", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    payload = response.get_json()
    assert payload["error"] == "Invalid login or password"
