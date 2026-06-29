from dotenv import load_dotenv
load_dotenv()

import os
from datetime import timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from models import db
from blueprints import auth_bp
from flask_jwt_extended import JWTManager
from extensions import limiter
jwt = JWTManager()
migrate= Migrate()
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

    if test_config:
        app.config.update(test_config)

    db.init_app(app)  
    jwt.init_app(app)      
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
