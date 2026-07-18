from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token

from models import User, db, UserRole
from extensions import limiter
from blueprints.auth import send_verification_email

demo_bp = Blueprint("demo", __name__, url_prefix="/api/demo")


@demo_bp.route("/register", methods=["POST"])
def demo_register():
    if not request.is_json:
        return jsonify({"error": "JSON data required"}), 400

    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")

    if not username or not password or not email:
        return jsonify({"error": "Username and password and email are required for registration"}), 400

    existing_user = User.query.filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing_user:
        return jsonify({"error": "Username or email already exists"}), 400

    new_user = User(
        username=username,
        email=email,
        is_demo=True,
        is_demo_data=True,
        role=UserRole.ADMIN,
    )
    new_user.set_password(password)
    db.session.add(new_user)

    if not current_app.config["REQUEST_MAIL_VERIFICATION"]:
        new_user.is_email_verified = True
        new_user.pending_email = None
        db.session.commit()
        return jsonify({
            "message": "Registration successful!",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "role": new_user.role.value,
            },
        }), 201

    db.session.commit()
    verification_token = new_user.generate_email_verification_token(
        current_app.config["JWT_SECRET_KEY"],
        current_app.config["EMAIL_VERIFICATION_SALT"],
    )
    verification_url = current_app.config["EMAIL_VERIFICATION_URL"].format(
        token=verification_token
    )

    try:
        send_verification_email(new_user, verification_url)
    except Exception as exc:
        return jsonify({
            "error": "Failed to send verification email.",
            "details": str(exc),
        }), 500

    response = {
        "message": "Registration successful! Verification email sent.",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "role": new_user.role.value,
        },
    }
    if current_app.debug:
        response["verification_url"] = verification_url

    return jsonify(response), 201


@demo_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def demo_login():
    if not request.is_json:
        return jsonify({"error": "JSON data required"}), 400

    data = request.get_json()
    login = data.get("login")
    password = data.get("password")

    if not login or not password:
        return jsonify({"error": "login and password required"}), 400

    user = User.query.filter(
        User.is_demo.is_(True),
        (User.username == login) | (User.email == login.strip().lower()),
    ).first()
    if not user or not user.is_active or not user.check_password(password):
        return jsonify({"error": "Invalid login or password"}), 401

    if current_app.config["REQUEST_MAIL_VERIFICATION"] and not user.is_email_verified:
        return jsonify({"error": "Email address not verified"}), 403

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    user.last_seen = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({
        "message": "Login successful!",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user.id, "username": user.username, "role": user.role.value},
    }), 200
