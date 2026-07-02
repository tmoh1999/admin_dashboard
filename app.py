from dotenv import load_dotenv
load_dotenv()

import os
from datetime import timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from models import db
from blueprints import auth_bp
from extensions import limiter, jwt, mail
migrate = Migrate()
def create_app(test_config=None):
    app = Flask(__name__)
    CORS(app, origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(","))
    if os.getenv("SECRET_KEY") is None:
        raise ValueError("SECRET_KEY environment variable not set")
    if os.getenv("DATABASE_URL") is None:
        raise Exception("DATABASE_URL environment variable is not set")

    app.secret_key = os.environ.get("SECRET_KEY")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET_KEY"] = os.environ.get("SECRET_KEY")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=10)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)
    app.config["JWT_BLOCKLIST_ENABLED"] = True
    app.config["JWT_BLOCKLIST_TOKEN_CHECKS"] = ["access", "refresh"]
    app.config["EMAIL_VERIFICATION_TOKEN_EXPIRES"] = int(os.environ.get("EMAIL_VERIFICATION_TOKEN_EXPIRES", 3600))
    app.config["EMAIL_VERIFICATION_SALT"] = os.environ.get("EMAIL_VERIFICATION_SALT", "email-verification")
    app.config["EMAIL_VERIFICATION_URL"] = os.environ.get(
        "EMAIL_VERIFICATION_URL",
        "http://localhost:5000/api/auth/verify-email/{token}"
    )
    app.config["EMAIL_RESET_PASSWORD_URL"] = os.environ.get(
        "EMAIL_RESET_PASSWORD_URL",
        "http://localhost:5000/api/auth/reset-password/{token}"
    )
    app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "False").lower() == "true"
    app.config["MAIL_USE_SSL"] = os.environ.get("MAIL_USE_SSL", "False").lower() == "true"
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@example.com")
    app.config["REQUEST_MAIL_VERIFICATION"] = os.environ.get("REQUEST_MAIL_VERIFICATION", "True").lower() == "true"

    if test_config:
        app.config.update(test_config)

    db.init_app(app)  
    jwt.init_app(app)      
    mail.init_app(app)
    migrate.init_app(app,db)
    limiter.init_app(app)      
    app.register_blueprint(auth_bp)
    
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({
            "error": "Too many requests"
        }), 429

    return app

app = create_app()


@app.route("/")
def home():
    return jsonify({
        "success":True,
    })

if __name__ == "__main__":
    app.run(
            host="0.0.0.0", 
            port=5000, 
            debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true"        
    )
