from functools import wraps

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import String, cast, func
from models import User, db, UserRole
from extensions import mail
from flask_mail import Message

from flask_jwt_extended import (
    get_jwt_identity,
    jwt_required,
)

users_bp = Blueprint('users', __name__, url_prefix='/api/users')


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        if not user or not user.is_active or user.role != UserRole.ADMIN:
            return jsonify({"error": "Admin access required"}), 403
        return fn(*args, **kwargs)

    return wrapper


def get_users_query():
    users_query = User.query

    query = request.args.get("search")
    if query:
        search = f"%{query.lower()}%"
        users_query = users_query.filter(
            func.lower(
                func.concat(
                    cast(User.id, String), " ",
                    cast(User.username, String), " ",
                    cast(User.email, String), " ",
                    cast(User.role, String), " ",
                    cast(User.is_active, String)
                )
            ).like(search)
        )

    sort_column = request.args.get("sort_column", "id")
    sort_direction = request.args.get("sort_direction", "desc")

    allowed_sort_columns = {
        "id": User.id,
        "username": User.username,
        "email": User.email,
        "role": User.role,
        "is_active": User.is_active,
        "created_at": User.created_at,
    }
    column = allowed_sort_columns.get(sort_column, User.id)

    users_query = users_query.order_by(
        column.asc() if sort_direction == "asc" else column.desc()
    )
    return users_query


@users_bp.route('', methods=['GET'])
@admin_required
def list_users():
    page = request.args.get("page", 1, type=int)

    pagination = get_users_query().paginate(
        page=page,
        per_page=10,
        error_out=False,
    )

    users = pagination.items
    results_list = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value if user.role else None,
            "is_active": str(user.is_active),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
        for user in users
    ]

    return jsonify({
        "success": True,
        "results": results_list,
        "total_pages": pagination.pages,
    }), 200


@users_bp.route('/<int:user_id>', methods=['GET'])
@admin_required
def get_user_by_id(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value if user.role else None,
        "is_active": user.is_active,
        "is_email_verified": user.is_email_verified,
        "pending_email": user.pending_email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }), 200


@users_bp.route('/<int:user_id>', methods=['PUT'])
@admin_required
def update_user_by_admin(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No update data provided"}), 400

    if "username" in data:
        username = data.get("username")
        if not username or not str(username).strip():
            return jsonify({"error": "Username cannot be empty"}), 400

        normalized_username = str(username).strip()
        existing_user = User.query.filter(
            User.username == normalized_username,
            User.id != user_id,
        ).first()
        if existing_user:
            return jsonify({"error": "Username already exists"}), 400
        user.username = normalized_username

    if "email" in data:
        email = data.get("email")
        normalized_email = email.lower().strip() if email else None
        if not normalized_email or "@" not in normalized_email:
            return jsonify({"error": f"Invalid email address: {email!r}"}), 400

        existing_user = User.query.filter(
            (User.email == normalized_email) | (User.pending_email == normalized_email),
            User.id != user_id,
        ).first()
        if existing_user:
            return jsonify({"error": "Email already exists"}), 400

        user.email = normalized_email
        user.pending_email = None
        user.is_email_verified = True

    if "role" in data:
        role_value = data.get("role")
        if role_value is None:
            return jsonify({"error": "Role cannot be null"}), 400

        role_name = str(role_value).lower()
        if role_name not in {"user", "admin"}:
            return jsonify({"error": "Role must be either 'user' or 'admin'"}), 400
        user.role = UserRole(role_name)

    if "is_active" in data:
        user.is_active = bool(data.get("is_active"))

    db.session.commit()

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value if user.role else None,
        "is_active": user.is_active,
        "is_email_verified": user.is_email_verified,
        "pending_email": user.pending_email,
    }), 200


@users_bp.route('/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user_by_admin(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.is_active = False
    db.session.commit()

    return jsonify({"message": "User archived successfully."}), 200


@users_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user or not user.is_active:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
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

@users_bp.route('/me', methods=['PUT'])
@jwt_required()
def edit_user():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user or not user.is_active:
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

@users_bp.route('/me', methods=['DELETE'])
@jwt_required()
def delete_current_user():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user or not user.is_active:
        return jsonify({"error": "User not found"}), 404

    user.is_active = False
    db.session.commit()

    return jsonify({"message": "User archived successfully."}), 200