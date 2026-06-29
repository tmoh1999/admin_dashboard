from flask import Blueprint, request, jsonify
from models import User, db
from extensions import limiter
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

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

    # Hash pass(identity=str(user.id))word and create user
    new_user = User(username=username, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    access_token = create_access_token(identity=str(new_user.id))
    refresh_token = create_refresh_token(identity=str(new_user.id))

    return jsonify({
        "message": "Registration successful!",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": new_user.id, "username": new_user.username}
    }), 201
    
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
        return jsonify({"error": "Username and password required"}), 400

    # Find user in DB
    user:User = User.query.filter(
        (User.username==login) |
        (User.email==login)
    ).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username or password"}), 401

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "message": "Login successful!",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user.id, "username": user.username}
    }), 200

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    current_user = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user)
    return jsonify({
        "access_token": new_access_token
    }), 200

@auth_bp.route("/test")
@jwt_required()
def test():
    user=get_jwt_identity()
    return jsonify({
        "success":True,
    })