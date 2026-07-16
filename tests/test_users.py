import json

from datetime import datetime, timedelta, timezone

from models import User, db, UserRole


def create_admin_user():
    user = User(
        username="adminuser",
        email="admin@example.com",
        role=UserRole.ADMIN,
        is_active=True,
        is_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


def get_auth_headers(client, username, password):
    response = client.post(
        "/api/auth/login",
        json={"login": username, "password": password},
    )
    payload = response.get_json()
    return {"Authorization": f"Bearer {payload['access_token']}"}


def test_list_users_requires_admin(client):
    response = client.get("/api/users")
    assert response.status_code == 401


def test_list_users_returns_paginated_results(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    for i in range(12):
        user = User(
            username=f"user{i}",
            email=f"user{i}@example.com",
            role=UserRole.USER,
            is_active=True,
            is_email_verified=True,
        )
        user.set_password("password123")
        db.session.add(user)
    db.session.commit()

    response = client.get("/api/users?page=1&sort_column=username&sort_direction=asc", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["total_pages"] == 2
    assert len(payload["results"]) == 10
    assert payload["results"][0]["username"] == "adminuser"


def test_get_user_by_id_returns_user(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    response = client.get(f"/api/users/{admin.id}", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["username"] == admin.username
    assert payload["email"] == admin.email
    assert payload["role"] == admin.role.value


def test_get_user_by_id_not_found(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    response = client.get("/api/users/999", headers=headers)
    assert response.status_code == 404
    assert response.get_json()["error"] == "User not found"


def test_create_user_by_admin_with_invalid_payload(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    response = client.post("/api/users", json={}, headers=headers)
    assert response.status_code == 400
    assert response.get_json()["error"] == "Username, email, and password are required"


def test_create_user_by_admin_creates_user(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    response = client.post(
        "/api/users",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "role": "user",
            "is_active": "true",
        },
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["message"] == "User created successfully"
    assert payload["user"]["username"] == "newuser"
    assert payload["user"]["email"] == "newuser@example.com"

    user = User.query.filter_by(username="newuser").first()
    assert user is not None
    assert user.check_password("password123")
    assert user.role == UserRole.USER


def test_update_user_by_admin_changes_fields(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    user = User(
        username="existinguser",
        email="existing@example.com",
        role=UserRole.USER,
        is_active=True,
        is_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    response = client.put(
        f"/api/users/{user.id}",
        json={
            "username": "updateduser",
            "email": "updated@example.com",
            "role": "admin",
            "is_active": "false",
            "is_email_verified": "false",
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["username"] == "updateduser"
    assert payload["email"] == "updated@example.com"
    assert payload["role"] == "admin"
    assert payload["is_active"] is False
    assert payload["is_email_verified"] is False


def test_set_user_password_by_admin_requires_password(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    user = User(
        username="userpw",
        email="userpw@example.com",
        role=UserRole.USER,
        is_active=True,
        is_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    response = client.post(f"/api/users/{user.id}/set-password", json={}, headers=headers)
    assert response.status_code == 400
    assert response.get_json()["error"] == "Password is required"


def test_set_user_password_by_admin_updates_password(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    user = User(
        username="userpw2",
        email="userpw2@example.com",
        role=UserRole.USER,
        is_active=True,
        is_email_verified=True,
    )
    user.set_password("oldpassword")
    db.session.add(user)
    db.session.commit()

    response = client.post(
        f"/api/users/{user.id}/set-password",
        json={"password": "newpassword123"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "Password updated successfully"

    user = db.session.get(User, user.id)
    assert user.check_password("newpassword123")


def test_delete_user_by_admin_archives_user(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    user = User(
        username="deleteuser",
        email="deleteuser@example.com",
        role=UserRole.USER,
        is_active=True,
        is_email_verified=True,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    response = client.delete(f"/api/users/{user.id}", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["message"] == "User archived successfully."

    user = db.session.get(User, user.id)
    assert user.is_active is False


def test_get_current_user_returns_self(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    response = client.get("/api/users/me", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["username"] == admin.username
    assert payload["email"] == admin.email


def test_edit_user_updates_username_and_email(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    response = client.put(
        "/api/users/me",
        json={"username": "admin2", "email": "admin2@example.com"},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["username"] == "admin2"
    assert payload["email"] == "admin2@example.com"

    user = db.session.get(User, admin.id)
    assert user.username == "admin2"
    assert user.email == "admin2@example.com"
    assert user.pending_email is None


def test_delete_current_user_archives_account(client):
    admin = create_admin_user()
    headers = get_auth_headers(client, admin.username, "password123")

    response = client.delete("/api/users/me", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["message"] == "User archived successfully."

    user = db.session.get(User, admin.id)
    assert user.is_active is False
