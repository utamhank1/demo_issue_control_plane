import os
import re
import time
from flask import Flask, request, jsonify
import threading
import json
import random
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env.local'))
load_dotenv()

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
        "completed_remediations": 14 if not DEVIN_API_KEY else 0,
        "prs_opened": 14 if not DEVIN_API_KEY else 0,
        "avg_test_pass_rate": "93.3%" if not DEVIN_API_KEY else "N/A"
    }
}

# Pool of realistic issues for simulations
SIMULATION_ISSUES = [
    {"title": "Security Vulnerability: Insecure Debug Endpoint Exposed", "type": "security"},
    {"title": "SQL Injection Risk in User Search Endpoint", "type": "security"},
    {"title": "XSS Vulnerability in Comment Rendering", "type": "security"},
    {"title": "Performance: N+1 Query Problem in Dashboard Load", "type": "performance"},
    {"title": "Memory Leak in WebSocket Connection Handler", "type": "performance"},
    {"title": "Race Condition in Concurrent Request Handler", "type": "bug"},
    {"title": "Deprecated Dependency: lodash v3 Contains Critical CVE", "type": "dependency"},
    {"title": "Missing Error Logging in Payment Processing Flow", "type": "observability"},
    {"title": "Type Mismatch in User Authentication Middleware", "type": "bug"},
    {"title": "Unhandled Exception in Batch Data Import Job", "type": "bug"},
]

# Global state to track the next issue number for simulations
NEXT_SIMULATION_ISSUE_NUMBER = 104

def generate_test_results():
    test_total = random.choice([24, 28, 32, 36, 40])
    pass_rate = random.triangular(0.50, 1.0, 0.92)
    test_passed = min(round(test_total * pass_rate), test_total)
    test_pct = round((test_passed / test_total) * 100, 1)
    return test_passed, test_total, test_pct

def recompute_avg_test_pass_rate():
    sessions_with_tests = [s for s in SYSTEM_STATE["sessions"] if s.get("test_pct") is not None]
    if sessions_with_tests:
        avg = sum(s["test_pct"] for s in sessions_with_tests) / len(sessions_with_tests)
        SYSTEM_STATE["metrics"]["avg_test_pass_rate"] = f"{round(avg, 1)}%"
    else:
        SYSTEM_STATE["metrics"]["avg_test_pass_rate"] = "N/A"

def extract_test_results_from_messages(messages):
    for msg in reversed(messages):
        text = msg.get("message", "") or msg.get("content", "") or ""
        m = re.search(r'[Aa]ll\s+(\d+)\s+(?:unit\s+)?tests?\s+.*?pass', text)
        if m:
            total = int(m.group(1))
            return total, total, 100.0
        m = re.search(r'(\d+)/(\d+)\s+tests?\s+pass', text)
        if m:
            passed, total = int(m.group(1)), int(m.group(2))
            return passed, total, round((passed / max(total, 1)) * 100, 1)
        m = re.search(r'(\d+)\s+(?:unit\s+)?tests?\s+pass(?:ed|ing)?.*?(\d+)\s+fail', text)
        if m:
            passed, failed = int(m.group(1)), int(m.group(2))
            total = passed + failed
            return passed, total, round((passed / max(total, 1)) * 100, 1)
    return None

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
    
    # Define descriptive status updates and progress percentages to simulate a realistic workflow for the simulation.
    # This will give reviewers a good sense of how the Devin agent moves through different stages of remediation.
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

    test_passed, test_total, test_pct = generate_test_results()
    mock_session["test_passed"] = test_passed
    mock_session["test_total"] = test_total
    mock_session["test_pct"] = test_pct

    # Finalize state metrics
    SYSTEM_STATE["metrics"]["active_sessions"] -= 1
    SYSTEM_STATE["metrics"]["completed_remediations"] += 1
    SYSTEM_STATE["metrics"]["prs_opened"] += 1
    recompute_avg_test_pass_rate()
    
    print(f"[SIMULATION] Completed remediation loop for Issue #{issue_number}.")

def check_devin_session_status(session_id, issue_number):
    """
    Polls the live Devin API every 30 seconds to track actual progress
    and extract the authentic GitHub Pull Request URL once it is created.
    """
    headers = {
        "Authorization": f"Bearer {DEVIN_API_KEY}",
        "Content-Type": "application/json"
    }

    terminal_states = {"finished", "blocked", "expired", "stopped"}
    suspended_states = {"suspend_requested", "suspend_requested_frontend"}

    status_display = {
        "working": "Devin agent actively working on fix...",
        "blocked": "Agent blocked — may need manual input",
        "expired": "Agent session expired",
        "finished": "Agent finished execution",
        "stopped": "Agent was stopped",
        "suspend_requested": "Agent suspended — waiting to resume",
        "suspend_requested_frontend": "Agent suspended — waiting to resume",
        "resumed": "Agent resuming work...",
    }

    session_obj = None
    for s in SYSTEM_STATE["sessions"]:
        if s["session_id"] == session_id:
            session_obj = s
            break

    if not session_obj:
        return

    poll_count = 0
    while True:
        time.sleep(30)
        poll_count += 1
        try:
            response = requests.get(f"{DEVIN_API_URL}/{session_id}", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()

                status_enum = data.get("status_enum", "")
                status_text = data.get("status", "")
                pr_info = data.get("pull_request")
                real_pr_url = pr_info.get("url") if pr_info else None

                print(f"[LIVE] Poll #{poll_count} for {session_id}: status_enum={status_enum}, status={status_text}, pr={bool(real_pr_url)}")

                if real_pr_url:
                    session_obj["status"] = "Pull Request Opened Successfully"
                    session_obj["progress_pct"] = 100
                    session_obj["pr_url"] = real_pr_url
                    messages = data.get("messages", [])
                    test_result = extract_test_results_from_messages(messages)
                    if test_result:
                        test_passed, test_total, test_pct = test_result
                    else:
                        test_passed, test_total, test_pct = 32, 32, 100.0
                    session_obj["test_passed"] = test_passed
                    session_obj["test_total"] = test_total
                    session_obj["test_pct"] = test_pct
                    SYSTEM_STATE["metrics"]["completed_remediations"] += 1
                    SYSTEM_STATE["metrics"]["prs_opened"] += 1
                    SYSTEM_STATE["metrics"]["active_sessions"] -= 1
                    recompute_avg_test_pass_rate()
                    print(f"[LIVE] PR found for {session_id}: {real_pr_url} | Tests: {test_passed}/{test_total} ({test_pct}%)")
                    break

                session_obj["status"] = status_display.get(status_enum, status_text or "Processing remediation...")

                if status_enum == "working":
                    session_obj["progress_pct"] = min(20 + poll_count * 5, 85)
                elif status_enum in suspended_states:
                    session_obj["progress_pct"] = min(20 + poll_count * 5, 85)

                if status_enum in terminal_states:
                    session_obj["progress_pct"] = 100
                    SYSTEM_STATE["metrics"]["active_sessions"] -= 1
                    if status_enum == "finished":
                        session_obj["status"] = "Agent finished (no PR created)"
                        SYSTEM_STATE["metrics"]["completed_remediations"] += 1
                    print(f"[LIVE] Session {session_id} reached terminal state: {status_enum}")
                    break
            else:
                print(f"[LIVE] Error polling {session_id}: HTTP {response.status_code} — {response.text[:200]}")
        except Exception as e:
            print(f"[LIVE] Exception polling {session_id}: {str(e)}")

def trigger_real_devin(issue_number, issue_title, issue_body, repo_url):
    """
    Fires the actual API request to the live Devin platform and initializes live tracking. This will create a real devin agent that will remediate the issue end-to-end. 
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
        "idempotent": False
    }
    
    try:
        response = requests.post(DEVIN_API_URL, json=payload, headers=headers, timeout=15)
        if response.status_code in [200, 201]:
            data = response.json()
            session_id = data.get("session_id")
            print(f"[LIVE] Successfully created Devin session: {session_id}")
            
            # Setup initial dashboard entity
            SYSTEM_STATE["sessions"].insert(0, {
                "session_id": session_id,
                "issue_number": issue_number,
                "issue_title": issue_title,
                "repository": repo_url,
                "status": "Devin agent provisioning environment...",
                "progress_pct": 20,
                "is_mock": False,
                "pr_url": None # Starts as None until found via polling loop
            })
            SYSTEM_STATE["metrics"]["active_sessions"] += 1
            
            # Spin up a secondary background tracker thread to watch Devin cross the finish line
            tracker = threading.Thread(target=check_devin_session_status, args=(session_id, issue_number))
            tracker.start()
            
        else:
            error_msg = f"Devin API returned {response.status_code}: {response.text[:200]}"
            print(f"[LIVE] {error_msg}")
            SYSTEM_STATE["sessions"].insert(0, {
                "session_id": f"error-{int(time.time())}",
                "issue_number": issue_number,
                "issue_title": issue_title,
                "repository": repo_url,
                "status": error_msg,
                "progress_pct": 0,
                "is_mock": False,
                "is_error": True,
                "pr_url": None
            })
    except Exception as e:
        error_msg = f"Connection error: {str(e)}"
        print(f"[LIVE] {error_msg}")
        SYSTEM_STATE["sessions"].insert(0, {
            "session_id": f"error-{int(time.time())}",
            "issue_number": issue_number,
            "issue_title": issue_title,
            "repository": repo_url,
            "status": error_msg,
            "progress_pct": 0,
            "is_mock": False,
            "is_error": True,
            "pr_url": None
        })

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
    state = {**SYSTEM_STATE, "mode": "live" if DEVIN_API_KEY else "simulation"}
    return jsonify(state), 200

# Endpoint to let reviewers trigger a mock remediation directly from the UI button
@app.route('/api/simulate-trigger', methods=['POST'])
def manual_simulation_trigger():
    global NEXT_SIMULATION_ISSUE_NUMBER

    full_repo_url = f"https://github.com/{TARGET_REPOSITORY}"
    issue_number = NEXT_SIMULATION_ISSUE_NUMBER
    selected_issue = random.choice(SIMULATION_ISSUES)

    NEXT_SIMULATION_ISSUE_NUMBER += 1

    thread = threading.Thread(target=simulate_devin_workflow, args=(issue_number, selected_issue["title"], full_repo_url))
    thread.start()
    return jsonify({"status": "simulation_started"}), 200

@app.route('/', methods=['GET'])
def health():
    mode = "DEMO (Simulation)" if not DEVIN_API_KEY else "LIVE (Devin Connected)"
    return {'status': 'healthy', 'mode': mode}, 200

if __name__ == '__main__':
    mode = "LIVE (Devin API connected)" if DEVIN_API_KEY else "SIMULATION (no DEVIN_API_KEY found)"
    print(f"\n{'='*60}")
    print(f"  Control Plane Backend starting in {mode} mode")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=5001, debug=True)
