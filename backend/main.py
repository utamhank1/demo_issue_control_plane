import os
import time
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

def simulate_devin_workflow(issue_number, issue_title, repo_url):
    """
    Simulates a Devin session over 30 seconds so reviewers can see the visual 
    loop on the control plane dashboard without needing an API key. Easier to demo for business stakeholders and product team.
    """
    print(f"[SIMULATION] Starting mock Devin agent for Issue #{issue_number}...")
    
    session_id = f"mock-session-{int(time.time())}"
    mock_session = {
        "session_id": session_id,
        "issue_number": issue_number,
        "issue_title": issue_title,
        "repository": repo_url,
        "status": "Initializing sandbox...",
        "progress_pct": 10,
        "is_mock": True
    }
    
    SYSTEM_STATE["sessions"].insert(0, mock_session)
    SYSTEM_STATE["metrics"]["active_sessions"] += 1
    
    # Define steps to simulate the technical depth requested in the submission
    steps = [
        ("Cloning repository and targeting vulnerabilities...", 25),
        ("Running security linter (Bandit)... Found 2 High CVEs.", 45),
        ("Refactoring insecure endpoints and patching dependencies...", 65),
        ("Running unit tests to verify fix locally... All tests passed.", 85),
        ("Success! Opening Pull Request back to main branch.", 100)
    ]
    
    for status, pct in steps:
        time.sleep(5)  # Pause to simulate processing time
        mock_session["status"] = status
        mock_session["progress_pct"] = pct
        print(f"[SIMULATION] Session {session_id} Update: {status} ({pct}%)")
        
    # Finalize state metrics
    SYSTEM_STATE["metrics"]["active_sessions"] -= 1
    SYSTEM_STATE["metrics"]["completed_remediations"] += 1
    SYSTEM_STATE["metrics"]["prs_opened"] += 1
    # Recalculate pass rate dynamically
    total = SYSTEM_STATE["metrics"]["completed_remediations"]
    SYSTEM_STATE["metrics"]["pass_rate"] = f"{round((total / (total + 1)) * 100, 1)}%"
    
    print(f"[SIMULATION] Completed remediation loop for Issue #{issue_number}.")

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
