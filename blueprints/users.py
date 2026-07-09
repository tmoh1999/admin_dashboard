from flask import Blueprint, request, jsonify, current_app
from models import User, db
from extensions import mail
from flask_mail import Message

from flask_jwt_extended import (
    get_jwt_identity,
    jwt_required,
)

users_bp = Blueprint('users', __name__, url_prefix='/api/users')

@users_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
    }), 200
def send_verification_new_email(user, verification_url):
    message = Message(
        subject="Verify your new email for Admin Dashboard",
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
        recipients=[user.pending_email],
        body=(
            f"Hello {user.username},\n\n"
            f"Please verify your email by visiting the link below:\n\n"
            f"{verification_url}\n\n"
            "If you did not change email address, please ignore this email."
        ),
    )
    mail.send(message)

@users_bp.route('/edit', methods=['PUT'])
@jwt_required()
def edit_user():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    username = data.get('username')
    email = data.get('email')

    if username:
        existing_user = User.query.filter(
            User.username == username,
            User.id != current_user_id
        ).first()
        if existing_user:
            return jsonify({"error": "Username already exists"}), 400

        user.username = username

    normalized_email = None
    if email:
        normalized_email = email.lower().strip()
        if not normalized_email or "@" not in normalized_email:
            return jsonify({"error": f"Invalid email address: {email!r}"}), 400
        existing_user = User.query.filter(
            (User.email == normalized_email) | (User.pending_email == normalized_email),
            User.id != current_user_id
        ).first()
        if existing_user:
            return jsonify({"error": "Email already exists"}), 400

    if not current_app.config["REQUEST_MAIL_VERIFICATION"]:
        if normalized_email:
            user.email = normalized_email
            user.pending_email = None
            user.is_email_verified = True
        elif not user.is_email_verified:
            user.is_email_verified = True
    elif normalized_email and normalized_email != user.email:
        if normalized_email != user.pending_email:
            user.pending_email = normalized_email
            user.is_email_verified = False
            verification_token = user.generate_email_verification_token(
                current_app.config["JWT_SECRET_KEY"],
                current_app.config["EMAIL_VERIFICATION_SALT"],
            )
            verification_url = current_app.config["EMAIL_VERIFICATION_URL"].format(
                token=verification_token
            )
            try:
                send_verification_new_email(user, verification_url)
            except Exception as exc:
                db.session.rollback()
                return jsonify({
                    "error": "Failed to send verification email.",
                    "details": str(exc)
                }), 500

    db.session.commit()

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "pending_email": user.pending_email,
        "is_active": user.is_active,
    }), 200