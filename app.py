from dotenv import load_dotenv
load_dotenv()

import os
from flask import jsonify
from app_init import create_app



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
