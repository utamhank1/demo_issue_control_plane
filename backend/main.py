import os
from flask import Flask, request
import json

app = Flask(__name__)

# Load configurations from environment variables
DEVIN_API_KEY = os.getenv("DEVIN_API_KEY", "").strip()
TARGET_REPOSITORY = os.getenv("TARGET_REPOSITORY", "utamhank1/superset_exploration")
APP_ENV = os.getenv("APP_ENV", "demo")

DEVIN_API_URL = "https://api.devin.ai/v1/sessions"

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
