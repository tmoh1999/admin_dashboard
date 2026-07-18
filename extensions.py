from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_migrate import Migrate
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
)
jwt = JWTManager()
mail = Mail()
migrate = Migrate()


def validate_boolean_field(field_name, value):
    """
    Validate and convert a boolean field value.
    
    Args:
        field_name: Name of the field (for error messages)
        value: The value to validate (bool or string)
    
    Returns:
        tuple: (is_valid: bool, result: value or error_message)
    """
    if value is None:
        return False, f"{field_name} cannot be null"
    
    if isinstance(value, bool):
        return True, value
    
    if isinstance(value, str):
        if value.lower() not in {"true", "false"}:
            return False, f"{field_name} must be a boolean value"
        return True, value.lower() == "true"
    
    return False, f"{field_name} must be a boolean value"