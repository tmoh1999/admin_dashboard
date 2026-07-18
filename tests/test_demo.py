import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("EMAIL_VERIFICATION_SALT", "test-salt")
os.environ.setdefault("REQUEST_MAIL_VERIFICATION", "False")

from app_init import create_app
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


def test_demo_register_creates_demo_user(client):
    response = client.post(
        "/api/demo/register",
        json={
            "username": "demo_user",
            "email": "demo@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["message"].startswith("Registration successful")
    assert payload["user"]["username"] == "demo_user"

    user = User.query.filter_by(username="demo_user").first()
    assert user is not None
    assert user.is_demo is True
    assert user.is_demo_data is True
    assert user.check_password("password123")


def test_demo_login_returns_tokens_for_demo_user(client):
    user = User(
        username="demo_login",
        email="demo_login@example.com",
        is_demo=True,
        is_demo_data=True,
        is_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/api/demo/login",
        json={"login": "demo_login", "password": "password123"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["message"] == "Login successful!"
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["user"]["username"] == "demo_login"


def test_demo_login_rejects_non_demo_user(client):
    user = User(
        username="regular_user",
        email="regular@example.com",
        is_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/api/demo/login",
        json={"login": "regular_user", "password": "password123"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid login or password"
