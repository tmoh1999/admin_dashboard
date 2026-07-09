from flask import Blueprint, request, jsonify, current_app
from models import User, db
from extensions import limiter, jwt, mail
from flask_mail import Message
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
revoked_tokens = set()


def get_active_user_by_id(user_id):
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return None
    return user


def get_active_user_by_email(email):
    if not email:
        return None
    user = User.query.filter_by(email=email.lower().strip(), is_active=True).first()
    return user


def send_verification_email(user, verification_url):
    message = Message(
        subject="Verify your email for Admin Dashboard",
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
        recipients=[user.email],
        body=(
            f"Hello {user.username},\n\n"
            f"Please verify your email by visiting the link below:\n\n"
            f"{verification_url}\n\n"
            "If you did not create an account, please ignore this email."
        ),
    )
    mail.send(message)

def send_password_reset_verification_email(user, verification_url):
    message = Message(
        subject="Reset your password for Admin Dashboard",
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
        recipients=[user.email],
        body=(
            f"Hello {user.username},\n\n"
            f"You requested a password reset. Please reset your password by visiting the link below:\n\n"
            f"{verification_url}\n\n"
            "If you did not request a password reset, please ignore this email."
        ),
    )
    mail.send(message)
@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    return jwt_payload["jti"] in revoked_tokens

@auth_bp.route("/register", methods=["POST"])
def register():
    # Ensure JSON request
    if not request.is_json:
        return jsonify({"error": "JSON data required"}), 400

    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    email= data.get("email")

    if not username or not password or not email:
        return jsonify({"error": "Username and password and email are required for registration"}), 400

    # Check if user exists
    existing_user = User.query.filter(
        (User.username==username) |
        (User.email==email)
    ).first()
    if existing_user:
        return jsonify({"error": "Username or email already exists"}), 400

    # Hash password and create user
    new_user = User(username=username, email=email)
    new_user.set_password(password)
    db.session.add(new_user)

    if not current_app.config["REQUEST_MAIL_VERIFICATION"]:
        new_user.is_email_verified = True
        new_user.pending_email = None
        db.session.commit()
        return jsonify({
            "message": "Registration successful!",
            "user": {"id": new_user.id, "username": new_user.username}
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
            "details": str(exc)
        }), 500

    response = {
        "message": "Registration successful! Verification email sent.",
        "user": {"id": new_user.id, "username": new_user.username}
    }
    if current_app.debug:
        response["verification_url"] = verification_url

    return jsonify(response), 201
    
@auth_bp.route("/verify-email/<token>", methods=["GET"])
def verify_email(token):
    user_id = User.verify_email_verification_token(
        token,
        current_app.config["JWT_SECRET_KEY"],
        current_app.config["EMAIL_VERIFICATION_SALT"],
        current_app.config["EMAIL_VERIFICATION_TOKEN_EXPIRES"],
    )
    if not user_id:
        return jsonify({"error": "Invalid or expired verification token"}), 400

    user = get_active_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.is_email_verified and not user.pending_email:
        return jsonify({"message": "Email already verified"}), 200

    if user.pending_email:
        user.email = user.pending_email
        user.pending_email = None

    user.is_email_verified = True
    db.session.commit()

    return jsonify({"message": "Email verified successfully"}), 200

@auth_bp.route("/reset-password/<token>", methods=["GET"])
def reset_password_endpoint(token):
    user_id = User.verify_password_reset_token(
        token,
        current_app.config["JWT_SECRET_KEY"],
        current_app.config["EMAIL_VERIFICATION_SALT"],
        current_app.config["EMAIL_VERIFICATION_TOKEN_EXPIRES"],
    )
    if not user_id:
        return jsonify({"error": "Invalid or expired verification token"}), 400

    user = get_active_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if not user.is_email_verified:
        return jsonify({"message": "Email not verified"}), 400

    return jsonify({"message": "Verified: ready to reset password"}), 200


@auth_bp.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    # Accept new password and update user
    if not request.is_json:
        return jsonify({"error": "JSON data required"}), 400

    data = request.get_json()
    new_password = data.get("password")
    if not new_password:
        return jsonify({"error": "Password is required"}), 400

    user_id = User.verify_password_reset_token(
        token,
        current_app.config["JWT_SECRET_KEY"],
        current_app.config["EMAIL_VERIFICATION_SALT"],
        current_app.config["EMAIL_VERIFICATION_TOKEN_EXPIRES"],
    )
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 400

    user = get_active_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        user.set_password(new_password)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db.session.commit()
    return jsonify({"message": "Password has been reset successfully"}), 200

@auth_bp.route("/password-reset", methods=["POST"])
def password_reset():       
    if not request.is_json:
        return jsonify({"error": "JSON data required"}), 400

    data = request.get_json()
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = get_active_user_by_email(email)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if current_app.config["REQUEST_MAIL_VERIFICATION"] and not user.is_email_verified:
        return jsonify({"message": "Email not verified"}), 400

    verification_token = user.generate_password_reset_token(
        current_app.config["JWT_SECRET_KEY"],
        current_app.config["EMAIL_VERIFICATION_SALT"],
    )
    verification_url = current_app.config["EMAIL_RESET_PASSWORD_URL"].format(
        token=verification_token
    )

    try:
        send_password_reset_verification_email(user, verification_url)
    except Exception as exc:
        return jsonify({
            "error": "Failed to send verification email.",
            "details": str(exc)
        }), 500

    response = {"message": "Password reset verification email resent."}
    if current_app.debug:
        response["verification_url"] = verification_url

    return jsonify(response), 200


@auth_bp.route("/resend-verification", methods=["POST"])
def resend_verification():
    if not current_app.config["REQUEST_MAIL_VERIFICATION"]:
        return jsonify({
            "message": "email verification process is not active.",
        }), 400        
    if not request.is_json:
        return jsonify({"error": "JSON data required"}), 400

    data = request.get_json()
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = get_active_user_by_email(email)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.is_email_verified and not user.pending_email:
        return jsonify({"message": "Email already verified"}), 200
    verification_token = user.generate_email_verification_token(
        current_app.config["JWT_SECRET_KEY"],
        current_app.config["EMAIL_VERIFICATION_SALT"],
    )
    verification_url = current_app.config["EMAIL_VERIFICATION_URL"].format(
        token=verification_token
    )

    try:
        if user.pending_email:
            message = Message(
                subject="Verify your new email for Admin Dashboard",
                sender=current_app.config["MAIL_DEFAULT_SENDER"],
                recipients=[user.pending_email],
                body=(
                    f"Hello {user.username},\n\n"
                    f"Please verify your new email by visiting the link below:\n\n"
                    f"{verification_url}\n\n"
                    "If you did not change your email address, please ignore this email."
                ),
            )
            mail.send(message)
        else:
            send_verification_email(user, verification_url)
    except Exception as exc:
        return jsonify({
            "error": "Failed to send verification email.",
            "details": str(exc)
        }), 500

    response = {"message": "Verification email resent."}
    if current_app.debug:
        response["verification_url"] = verification_url

    return jsonify(response), 200

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    # Ensure JSON request
    if not request.is_json:
        return jsonify({"error": "JSON data required"}), 400

    data = request.get_json()
    login = data.get("login")
    password = data.get("password")

    if not login or not password:
        return jsonify({"error": "login and password required"}), 400

    # Find user in DB
    user:User = User.query.filter(
        (User.username==login) |
        (User.email==login.strip().lower())
    ).first()
    if not user or not user.is_active or not user.check_password(password):
        return jsonify({"error": "Invalid login or password"}), 401

    if current_app.config["REQUEST_MAIL_VERIFICATION"] and not user.is_email_verified:
        return jsonify({"error": "Email address not verified"}), 403

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "message": "Login successful!",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user.id, "username": user.username}
    }), 200

@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    if not get_active_user_by_id(get_jwt_identity()):
        return jsonify({"error": "User not found"}), 404
    revoked_tokens.add(get_jwt()["jti"])
    return jsonify({
        "message": "Logout successful!"
    }), 200

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    current_user = get_jwt_identity()
    if not get_active_user_by_id(current_user):
        return jsonify({"error": "User not found"}), 404
    new_access_token = create_access_token(identity=current_user)
    return jsonify({
        "access_token": new_access_token
    }), 200

@auth_bp.route("/test")
@jwt_required()
def test():
    if not get_active_user_by_id(get_jwt_identity()):
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "success":True,
    })