import os
import requests
from flask import Flask, render_template

app = Flask(__name__)

# URL of the backend service within the docker network
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:5001")

@app.route('/')
def index():
    try:
        # Fetch the live state from your backend /api/state endpoint
        response = requests.get(f"{BACKEND_URL}/api/state", timeout=2)
        state = response.json()
    except Exception:
        # Fallback if backend is temporarily unreachable
        state = {
            "metrics": {"active_sessions": 0, "completed_remediations": 0, "pass_rate": "0%", "prs_opened": 0},
            "sessions": []
        }
    return render_template('index.html', state=state)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)