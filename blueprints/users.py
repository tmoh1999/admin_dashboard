from functools import wraps
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, current_app,render_template,send_file
from sqlalchemy import String, cast, func,or_
from models import User, db, UserRole
from extensions import mail, validate_boolean_field
from flask_mail import Message
import os
import io
from weasyprint import HTML,CSS
from openpyxl import load_workbook,Workbook
from flask_jwt_extended import (
    get_jwt_identity,
    jwt_required,
)

users_bp = Blueprint('users', __name__, url_prefix='/api/users')

def is_online(user):
    if not user.last_seen:
        return False
    last_seen = user.last_seen
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - last_seen) <= timedelta(minutes=5)
def is_demo_user():
    current_user_id = get_jwt_identity()
    current_user = db.session.get(User, current_user_id)    
    if not current_user or not current_user.is_active:
        return False
    return current_user.is_demo
def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = db.session.get(User, current_user_id)
        if not user or not user.is_active or user.role != UserRole.ADMIN:
            return jsonify({"error": "Admin access required"}), 403
        return fn(*args, **kwargs)

    return wrapper


def get_users_query():
    users_query = (
        User.query.filter(
            or_(
                User.is_demo == True,
                User.is_demo_data == True,
            )
        )
        if is_demo_user()
        else User.query
    )

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
                    cast(User.is_active, String),
                    cast(User.is_email_verified, String)
                )
            ).like(search)
        )

    sort_column = request.args.get("sort_column", "id")
    sort_direction = request.args.get("sort_direction", "desc")

    allowed_sort_columns = {
        "id": User.id,
        "username": User.username,
        "email": User.email,
        "is_email_verified": User.is_email_verified,
        "role": User.role,
        "is_active": User.is_active,
        "last_seen": User.last_seen,
        "status": User.last_seen,
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
            "is_email_verified": str(user.is_email_verified),
            "status": "online" if is_online(user) else "offline",
            "last_seen": user.last_seen,
            "created_at": user.created_at
        }
        for user in users
    ]

    return jsonify({
        "success": True,
        "results": results_list,
        "total_pages": pagination.pages,
    }), 200


@users_bp.route('', methods=['POST'])
@admin_required
def create_user_by_admin():
    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")
    role_value = data.get("role", "user")
    is_active_value = data.get("is_active", True)

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400

    if "@" not in email:
        return jsonify({"error": f"Invalid email address: {email!r}"}), 400

    existing_user = User.query.filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing_user:
        return jsonify({"error": "Username or email already exists"}), 400

    if isinstance(is_active_value, str):
        is_active_value = is_active_value.lower() in {"true", "1", "yes", "y"}

    role_name = str(role_value).lower() if role_value is not None else "user"
    if role_name not in {"user", "admin"}:
        return jsonify({"error": "Role must be either 'user' or 'admin'"}), 400

    is_demo=is_demo_user()
    if is_demo and role_name != "user":
        return jsonify({"error": "You are not allowed to create admin users in demo mode"}), 400
    
    new_user = User(
        username=username,
        email=email,
        role=UserRole(role_name),
        is_active=bool(is_active_value),
        is_email_verified=not current_app.config["REQUEST_MAIL_VERIFICATION"],
        is_demo=is_demo,
        is_demo_data=True if is_demo else False,
    )
    try:
        new_user.set_password(password)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "message": "User created successfully",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "role": new_user.role.value if new_user.role else None,
            "is_active": new_user.is_active,
            "is_email_verified": new_user.is_email_verified,
        }
    }), 201


@users_bp.route('/<int:user_id>', methods=['GET'])
@admin_required
def get_user_by_id(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if is_demo_user() and get_jwt_identity()!= user_id and not user.is_demo_data:
        return jsonify({"error": "You are not allowed to access this user in demo mode"}), 403

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value if user.role else None,
        "is_active": user.is_active,
        "is_email_verified": user.is_email_verified,
        "pending_email": user.pending_email,
        "status": "online" if is_online(user) else "offline",
        "last_seen": user.last_seen,
        "created_at": user.created_at
    }), 200


@users_bp.route('/<int:user_id>', methods=['PUT'])
@admin_required
def update_user_by_admin(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if is_demo_user() and get_jwt_identity()!= user_id and not user.is_demo_data:
        return jsonify({"error": "You are not allowed to access this user in demo mode"}), 403
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

    if "role" in data and not is_demo_user():
        role_value = data.get("role")
        if role_value is None:
            return jsonify({"error": "Role cannot be null"}), 400

        role_name = str(role_value).lower()
        if role_name not in {"user", "admin"}:
            return jsonify({"error": "Role must be either 'user' or 'admin'"}), 400
        user.role = UserRole(role_name)

    if "is_active" in data:
        is_valid, result = validate_boolean_field("is_active", data.get("is_active"))
        if not is_valid:
            return jsonify({"error": result}), 400
        user.is_active = result

    if "is_email_verified" in data:
        is_valid, result = validate_boolean_field("is_email_verified", data.get("is_email_verified"))
        if not is_valid:
            return jsonify({"error": result}), 400
        user.is_email_verified = result

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


@users_bp.route('/<int:user_id>/set-password', methods=['POST'])
@admin_required
def set_user_password(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if is_demo_user() and get_jwt_identity()!= user_id and not user.is_demo_data:
        return jsonify({"error": "You are not allowed to access this user in demo mode"}), 403

    data = request.get_json(silent=True) or {}
    password = data.get("password")

    if not password or not str(password).strip():
        return jsonify({"error": "Password is required"}), 400

    try:
        user.set_password(str(password))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db.session.commit()

    return jsonify({"message": "Password updated successfully"}), 200


@users_bp.route('/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user_by_admin(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if is_demo_user() and get_jwt_identity()!= user_id and not user.is_demo_data:
        return jsonify({"error": "You are not allowed to access this user in demo mode"}), 403
    user.is_active = False
    db.session.commit()

    return jsonify({"message": "User archived successfully."}), 200


@users_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    current_user_id = get_jwt_identity()
    user = db.session.get(User, current_user_id)
    if not user or not user.is_active:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "status": "online" if is_online(user) else "offline",
        "last_seen": user.last_seen,
        "created_at":user.created_at
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
    user = db.session.get(User, current_user_id)
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
    user = db.session.get(User, current_user_id)
    if not user or not user.is_active:
        return jsonify({"error": "User not found"}), 404

    user.is_active = False
    db.session.commit()

    return jsonify({"message": "User archived successfully."}), 200


@users_bp.route('/stats', methods=['GET'])
@admin_required
def get_user_stats():
    base_query = User.query if not is_demo_user() else User.query.filter(
        or_(
            User.is_demo == True,
            User.is_demo_data == True,
        )
    )
    
    total_users = base_query.count()
    
    active_users = base_query.filter(User.is_active == True).count()
    
    inactive_users = base_query.filter(User.is_active == False).count()
    
    admin_count = base_query.filter(User.role == UserRole.ADMIN).count()
    
    user_count = base_query.filter(User.role == UserRole.USER).count()
    
    verified_emails = base_query.filter(User.is_email_verified == True).count()
    
    unverified_emails = base_query.filter(User.is_email_verified == False).count()
    
    online_users = sum(1 for user in base_query.all() if is_online(user))
    
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    users_last_7_days = base_query.filter(User.created_at >= seven_days_ago).count()
    
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    users_last_30_days = base_query.filter(User.created_at >= thirty_days_ago).count()
    
    # Registration chart data - daily registrations for last 30 days
    registration_chart = []
    for i in range(30):
        day_start = thirty_days_ago + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        count = base_query.filter(
            User.created_at >= day_start,
            User.created_at < day_end
        ).count()
        registration_chart.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": count
        })
    
    return jsonify({
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "admin_count": admin_count,
        "user_count": user_count,
        "verified_emails": verified_emails,
        "unverified_emails": unverified_emails,
        "online_users": online_users,
        "users_last_7_days": users_last_7_days,
        "users_last_30_days": users_last_30_days,
        "registration_chart": registration_chart,
    }), 200

@users_bp.route("/export/excel", methods=["GET"])
@admin_required
def export_users():
    
    # Create a new Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Users"

    # Write header row
    ws.append(
        [
            "ID",
            "Username",
            "Email",
            "Eole",
            "Is_active",
            "Is_email_verified",
            "Status",
            "Last_seen",
            "Created_at"
        ]
    )
    users = get_users_query().all()
    for user in users:
        ws.append([    
            user.id,
            user.username,
            user.email,
            user.role.value if user.role else None,
            str(user.is_active),
            str(user.is_email_verified),
            "online" if is_online(user) else "offline",
            user.last_seen.replace(tzinfo=None),
            user.created_at.replace(tzinfo=None)
        ])
    # Save to in-memory file
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name="users.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
@users_bp.route("/export/pdf",methods=["GET"])
@admin_required
def users_pdf():
    users = get_users_query().all()
    results_list = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value if user.role else None,
            "is_active": str(user.is_active),
            "is_email_verified": str(user.is_email_verified),
            "status": "online" if is_online(user) else "offline",
            "last_seen": user.last_seen,
            "created_at": user.created_at
        }
        for user in users
    ]    
    columns=[
        { "Name": "ID", "accessor": "id" },
        { "Name": "Username", "accessor": "username" },
        { "Name": "Email", "accessor": "email" },
        { "Name": "IsEmailVerified", "accessor": "is_email_verified" },
        { "Name": "Role", "accessor": "role" },
        { "Name": "IsActive", "accessor": "is_active" },
        { "Name": "Status", "accessor": "status" },
        { "Name": "Last Seen", "accessor": "last_seen" },
        { "Name": "Created At", "accessor": "created_at" },
    ]

    # render to PDF
    html = render_template("table_pdf_template.html", data=results_list,columns=columns,table_name="Users")
    
    css_path = os.path.join(current_app.root_path, "static", "css","bootstrap.min.css")
    pdf_bytes = HTML(string=html, base_url=current_app.root_path).write_pdf(stylesheets=[CSS(css_path)])
    pdf_file = io.BytesIO(pdf_bytes)
    return send_file(
        pdf_file,
        mimetype="application/pdf",
        as_attachment=True,          # True → download, False → open in browser
        download_name="users.pdf"  # filename for the browser
    )	
