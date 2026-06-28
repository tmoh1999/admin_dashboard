from flask import Blueprint, request,jsonify
from models import User,db
import os
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import limiter
from datetime import timedelta
from flask_jwt_extended import create_access_token
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

    # Hash password and create user
    new_user = User(username=username,email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    # Generate JWT token

    access_token = create_access_token(
        identity=new_user.id,
        expires_delta=timedelta(minutes=120)
    )
    # Return success JSON with token
    return jsonify({
        "message": "Registration successful!",
        "token": access_token,
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

    # Generate JWT token
    access_token = create_access_token(
        identity=user.id,
        expires_delta=timedelta(minutes=120)
    )
    # Return success JSON with token
    return jsonify({
        "message": "Login successful!",
        "token": access_token,
        "user": {"id": user.id, "username": user.username}
    }), 200