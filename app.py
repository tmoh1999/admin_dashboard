
import os
from flask import Flask,jsonify
from flask_cors import CORS

def create_app(test_config=None):
    app = Flask(__name__)
    CORS(app, origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(","))
    if test_config:
        app.config.update(test_config)

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
