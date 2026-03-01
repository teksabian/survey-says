# Render.com Deployment Guide

**Platform:** Render.com
**Runtime:** Python 3.11
**Server:** Gunicorn

---

## Services & Branching Strategy

We have **two separate Render services** connected to the same GitHub repo:

| Service | URL | Branch | Purpose |
|---------|-----|--------|---------|
| **Production (v1)** | `pubfeud.gamenightguild.net` | `v1` | Live game nights |
| **Dev (v2)** | `ff-v2-dev.gamenightguild.net` | `main` | Development & testing |

### How to deploy safely

- **Pushing to `main`** → only the **v2-dev** service rebuilds
- **Pushing to `v1`** → only the **production** service rebuilds
- Production is never affected by v2 development work

### Preview Environments: ON

Render Preview Environments are **enabled** in `render.yaml` with automatic generation. Each PR gets a temporary preview instance that auto-expires after 3 days of inactivity. Preview URLs are auto-assigned by Render (e.g., `family-feud-pr-N.onrender.com`). QR codes on previews use the preview's own URL, not production.

### Making major changes

1. Create a feature branch off `main`
2. Develop and test locally
3. Open a PR to `main` — merge to deploy to `ff-v2-dev.gamenightguild.net`
4. Test on the dev service
5. When stable, cherry-pick or merge into the `v1` branch for production

## Environment Detection

The app auto-detects whether it's running locally or on Render:

```python
if os.environ.get('RENDER'):
    # Cloud: logs to stdout (Render dashboard)
    # QR default: uses RENDER_EXTERNAL_URL or https://pubfeud.gamenightguild.net
else:
    # Local: logs to /logs/ directory
    # QR default: http://localhost:5000
```

## Environment Variables

Set these in Render dashboard under Environment:

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Flask session key (generate a random string) |
| `HOST_PASSWORD` | Yes | PIN for host panel access |
| `ANTHROPIC_API_KEY` | Optional | Claude API key for AI scoring |
| `RENDER` | Auto | Set automatically by Render |
| `RENDER_EXTERNAL_URL` | Auto | The service's public URL (set by Render) |
| `QR_BASE_URL` | Optional | Override the default QR code URL |
| `GITHUB_TOKEN` | Optional | For AI corrections sync to GitHub |

## Files

- **`render.yaml`** — Tells Render how to build and run (Python 3.11, gunicorn, env vars)
- **`requirements.txt`** — Python dependencies installed automatically

## Deploy Process

1. Push to GitHub (`git push origin main` for v2-dev, `git push origin v1` for production)
2. Render auto-detects the push and rebuilds the corresponding service
3. Dependencies installed from `requirements.txt`
4. Gunicorn starts the app
5. Nuclear reset runs (fresh game state)

## Local Development

```bash
pip install -r requirements.txt
python app.py
# Visit http://localhost:5000
```

Local behavior is unchanged — logs go to `/logs/`, QR codes default to localhost.

## Key Differences: Local vs Cloud

| Feature | Local | Render (Production) | Render (Dev) |
|---------|-------|---------------------|--------------|
| Server | Flask dev server | Gunicorn | Gunicorn |
| Logs | `/logs/` directory | Render dashboard | Render dashboard |
| QR Base URL | `http://localhost:5000` | `pubfeud.gamenightguild.net` | `ff-v2-dev.gamenightguild.net` |
| Secret Key | Random per start | Persistent env var | Persistent env var |
| Host Password | Default or env var | Required env var | Required env var |
| Branch | N/A | `v1` | `main` |
