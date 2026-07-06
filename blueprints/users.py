from flask import Blueprint, request, jsonify, current_app
from models import User, db


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