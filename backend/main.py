import os
from flask import Flask, request
import json

app = Flask(__name__)

# Load configurations from environment variables.
DEVIN_API_KEY = os.getenv("DEVIN_API_KEY", "").strip()
TARGET_REPOSITORY = os.getenv("TARGET_REPOSITORY", "utamhank1/superset_exploration")
APP_ENV = os.getenv("APP_ENV", "demo")

DEVIN_API_URL = "https://api.devin.ai/v1/sessions"

# System Current state - global state to act as a lightweight data store for the dashboard. In production would 
# like to load this to firestore or redis.
SYSTEM_STATE = {
    "sessions": [],
    "metrics": {
        "active_sessions": 0,
        "completed_remediations": 14,  # Pre-seed some baseline numbers for visual punch
        "prs_opened": 14,
        "pass_rate": "93.3%"
    }
}

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.json
    print("Received webhook payload!")
    print(json.dumps(payload, indent=2))
    return 'OK', 200

@app.route('/', methods=['GET'])
def health():
    return {'status': 'healthy'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
