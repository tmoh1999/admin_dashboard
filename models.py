from sqlalchemy import Index, UniqueConstraint
import enum
from sqlalchemy.orm import validates
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

def utc_now():
    return datetime.now(timezone.utc)

class UserRole(enum.Enum):
    USER  = "user"
    ADMIN = "admin"

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), nullable=False)

    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(
        db.Enum(UserRole),
        nullable=False,
        default=UserRole.USER
    )

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now
    )

    __table_args__ = (
        UniqueConstraint("email",    name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
        Index("ix_users_role",          "role"),
        Index("ix_users_email_role",    "email", "role"),
        Index("ix_users_username_role", "username", "role"),
    )

    # ------------------------------------------------------------------ #
    #  validators                                                          #
    # ------------------------------------------------------------------ #

    @validates("email")
    def validate_email(self, key, value):
        if not value or "@" not in value:
            raise ValueError(f"Invalid email address: {value!r}")
        return value.lower().strip()

    @validates("username")
    def validate_username(self, key, value):
        if not value or not value.strip():
            raise ValueError("Username cannot be empty")
        return value.strip()

    # ------------------------------------------------------------------ #
    #  password helpers                                                    #
    # ------------------------------------------------------------------ #

    def set_password(self, password):
        if len(password) < 8:
            raise ValueError(
                "Password must be at least 8 characters long"
            )        
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # ------------------------------------------------------------------ #
    #  serialization                                                       #
    # ------------------------------------------------------------------ #

    def to_dict(self):
        return {
            "id":         self.id,
            "username":   self.username,
            "email":      self.email,
            "role":       self.role.value,
            "is_active":  self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"