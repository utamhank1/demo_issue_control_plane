import os
from flask import Flask, render_template

app = Flask(__name__)

# URL of the backend service within the docker network
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:5001")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)