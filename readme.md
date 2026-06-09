# Devin Control Plane - Autonomous Security Remediation Dashboard

An observability dashboard that demonstrates an autonomous vulnerability remediation pipeline powered by [Devin AI](https://devin.ai). When a GitHub issue is labeled `devin-remediate`, the control plane spins up a Devin agent that clones the repo, applies a fix, runs tests, and opens a pull request - all visible in real-time on the dashboard.

The app ships with a **simulation mode** that runs the full visual workflow without any API keys, making it easy to demo for stakeholders.https://github.com/utamhank1/demo_issue_control_plane/blob/feature/distribution-packaging/readme.md

---

## Quick Start (Simulation Mode)

No API keys or configuration needed. Just clone and run:

```bash
git clone <this-repo-url>
cd demo_issue_observability_plane
docker compose up --build
```

Open **http://localhost:3000** in your browser and click **"Simulate 'devin-remediate' Event"** to watch the pipeline animate through a 30-second mock remediation cycle.

---

## Configuration (Live Mode)

To connect to the real Devin API and receive GitHub webhooks, create a `.env.local` file:

```bash
cp .env.example .env.local
```

Then edit `.env.local` and fill in:

| Variable | Required For | Description |
|---|---|---|
| `DEVIN_API_KEY` | Live mode | Your Devin API key from [app.devin.ai/settings](https://app.devin.ai/settings) |
| `GITHUB_WEBHOOK_SECRET` | Webhook verification | A secret token to validate incoming GitHub payloads |
| `NGROK_AUTHTOKEN` | Webhook profile | Free auth token from [ngrok.com](https://dashboard.ngrok.com/signup) |

### GitHub Repository Access

The target repository is **`utamhank1/superset_exploration`** (private). To use live mode with pull request links:

1. You need read access to this repository. Request access from the repo owner.
2. The PR links on the dashboard will point to this repo's pull requests.
3. To target a different repo, set `TARGET_REPOSITORY=owner/repo` in your `.env.local`.

---

## Running with Webhooks (ngrok)

To receive live GitHub webhooks on your local machine, start the app with the webhook profile:

```bash
docker compose --profile webhook up --build
```

This starts an ngrok tunnel alongside the app. To find your public webhook URL:

1. Open the ngrok inspector at **http://localhost:4040**
2. Copy the `https://xxxx.ngrok-free.app` URL
3. In your GitHub repo, go to **Settings > Webhooks > Add webhook**:
   - **Payload URL:** `https://xxxx.ngrok-free.app/webhook`
   - **Content type:** `application/json`
   - **Secret:** The value of `GITHUB_WEBHOOK_SECRET` from your `.env.local`
   - **Events:** Select "Issues" (specifically the "labeled" event)

Now label any issue with `devin-remediate` to trigger a live remediation.

---

## Architecture

```
GitHub Issue (labeled "devin-remediate")
        |
        v
   [ngrok tunnel]  <-- only needed for live webhooks
        |
        v
   Backend (Flask :5001)
     - /webhook         receives GitHub events
     - /api/state       serves dashboard telemetry
     - /api/simulate-trigger  fires mock workflows
        |
        v
   Dashboard (Flask :3000)
     - Polls /api/state every 3 seconds
     - Renders real-time progress bars, PR links, test coverage
```

**Simulation mode** (no API key): The backend runs a 30-second mock workflow with randomized test results and animated progress steps.

**Live mode** (with API key): The backend calls the Devin API to create a real agent session, then polls every 30 seconds until a pull request appears or the session reaches a terminal state.

---

## Ports

| Service | Port | Description |
|---|---|---|
| Dashboard | 3000 | Web UI |
| Backend | 5001 | API server |
| ngrok Inspector | 4040 | Tunnel status (webhook profile only) |

---

## Troubleshooting

**Dashboard shows "No active Devin agent execution threads"**
This is the default empty state. Click the simulate button or send a webhook to start a pipeline.

**`env_file .env.local not found` error**
You're on an older version of Docker Compose that doesn't support `required: false`. Either:
- Create an empty `.env.local` file: `touch .env.local`
- Or upgrade Docker Compose to v2.24+

**ngrok container exits immediately**
Make sure `NGROK_AUTHTOKEN` is set in your `.env.local`. Sign up for a free account at [ngrok.com](https://dashboard.ngrok.com/signup).
