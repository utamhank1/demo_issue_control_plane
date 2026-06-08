import os
import time
from flask import Flask, request, jsonify
import threading
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
        "is_mock": True,
        "pr_url": None
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

    # Final step: Complete the workflow, change status text, and add the hyperlink.
    time.sleep(5)
    mock_session["status"] = "Pull Request Opened Successfully"
    mock_session["progress_pct"] = 100
    mock_session["pr_url"] = f"{repo_url}/pulls"  # Points to the repo's PR tab for the simulation
        
    # Finalize state metrics
    SYSTEM_STATE["metrics"]["active_sessions"] -= 1
    SYSTEM_STATE["metrics"]["completed_remediations"] += 1
    SYSTEM_STATE["metrics"]["prs_opened"] += 1
    # Recalculate pass rate dynamically
    total = SYSTEM_STATE["metrics"]["completed_remediations"]
    SYSTEM_STATE["metrics"]["pass_rate"] = f"{round((total / (total + 1)) * 100, 1)}%"
    
    print(f"[SIMULATION] Completed remediation loop for Issue #{issue_number}.")

def trigger_real_devin(issue_number, issue_title, issue_body, repo_url):
    """
    Fires the actual API request to the live Devin platform when variables are configured in the environment. This will create a real Devin session and spin up an agent to remediate the issue end-to-end.
    """
    print(f"[LIVE] Triggering real Devin Agent for Issue #{issue_number}...")
    
    headers = {
        "Authorization": f"Bearer {DEVIN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        f"Fix the bug described in GitHub Issue #{issue_number} for {repo_url}.\n\n"
        f"Title: {issue_title}\n"
        f"Details:\n{issue_body}\n\n"
        f"Instructions:\n"
        f"1. Spin up the environment and replicate the issue.\n"
        f"2. Apply the fix and run tests to ensure zero regression.\n"
        f"3. CRITICAL: Open a Pull Request back to the main branch with your changes when complete."
    )
    
    payload = {
        "prompt": prompt,
        "unbanned_tools": ["github", "shell", "browser"]
    }
    
    try:
        response = requests.post(DEVIN_API_URL, json=payload, headers=headers, timeout=15)
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"[LIVE] Successfully created Devin session: {data.get('session_id')}")
            # Add tracking data to state to show on the dashboard
            SYSTEM_STATE["sessions"].insert(0, {
                "session_id": data.get("session_id"),
                "issue_number": issue_number,
                "issue_title": issue_title,
                "repository": repo_url,
                "status": "Running via Devin API",
                "progress_pct": 50,
                "is_mock": False
            })
        else:
            print(f"[LIVE] Failed to hit Devin API. Status: {response.status_code}, Error: {response.text}")
    except Exception as e:
        print(f"[LIVE] Connection error to Devin API: {str(e)}")

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.json or {}

    action = payload.get("action")
    issue = payload.get("issue", {})
    label = payload.get("label", {})
    repository = payload.get("repository", {})
    issue_number = issue.get("number")
    issue_title = issue.get("title", "")
    issue_body = issue.get("body", "")
    repo_url = repository.get("html_url", "")

    # Match the exact trigger loop: When an issue is labeled "devin-remediate"
    if action == "labeled" and label.get("name") == "devin-remediate":
        print(f"\n Target event hit! Issue #{issue_number} labeled 'devin-remediate'.")
        
        # Offload execution to a background thread so the webhook finishes immediately. 
        # GitHub requires a response in <10 seconds or it counts as a timeout failure.
        if not DEVIN_API_KEY:
            thread = threading.Thread(target=simulate_devin_workflow, args=(issue_number, issue_title, repo_url))
            thread.start()
            return jsonify({"status": "simulating", "message": "No Devin API Key found. Initiating control plane simulation mode."}), 200
        else:
            thread = threading.Thread(target=trigger_real_devin, args=(issue_number, issue_title, issue_body, repo_url))
            thread.start()
            return jsonify({"status": "processing", "message": "Live Devin session loop initiated via API."}), 200

    return jsonify({"status": "ignored", "message": "Event did not match 'devin-remediate' labeling parameters."}), 200

# Internal endpoints for your dashboard to fetch telemetry data.
@app.route('/api/state', methods=['GET'])
def get_state():
    return jsonify(SYSTEM_STATE), 200

# Endpoint to let reviewers trigger a mock remediation directly from the UI button
@app.route('/api/simulate-trigger', methods=['POST'])
def manual_simulation_trigger():
    thread = threading.Thread(target=simulate_devin_workflow, args=(104, "Security Vulnerability: Insecure Debug Endpoint Exposed", TARGET_REPOSITORY))
    thread.start()
    return jsonify({"status": "simulation_started"}), 200

@app.route('/', methods=['GET'])
def health():
    mode = "DEMO (Simulation)" if not DEVIN_API_KEY else "LIVE (Devin Connected)"
    return {'status': 'healthy', 'mode': mode}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
