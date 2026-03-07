# Family Feud — Pub Trivia Game

*A Flask-powered Family Feud clone for pub trivia nights. Teams join via QR codes, AI does the homework, and the database deletes itself when you're done.*

---

## What Is This?

A complete digital Family Feud game built for weekly pub trivia nights. Teams join from their phones — no app install, no account creation, no asking the bartender for the WiFi password. Scan a QR code, enter a team name, and you're in.

The host runs everything from a dashboard on any device: create rounds, activate questions, score answers, and manage chaos as needed. Ten complete survey sets are included so you can run a full night out of the box. Bring your own questions via DOCX/PPTX upload, or create rounds manually if you enjoy that sort of thing.

The bartender will not need to help anyone with setup.

---

## Features

### For Teams
- 📱 Mobile-first interface with auto-save — answers survive app switching, phone sleep, and accidental navigation
- 🔑 Join via QR code or 4-letter team code *(no I, O, or L — the letters most likely to ruin someone's night)*
- 🔄 Real-time round updates via polling (every 5–10 seconds)
- 🟢 Connection status indicator (green dot = present, grey = somewhere else)
- 🔁 Team reconnect and code reclaim after disconnect (v1.1.0)

### For Hosts
- 🔒 PIN-protected host dashboard
- 📢 Broadcast messages to all teams simultaneously
- 🖨️ Printable QR code cards (portrait or landscape)
- 📷 `/host/scan` — mobile shortcut for photo scan *(bookmark this before pub night)*
- 📸 Photo scan: photograph paper answer sheets → auto-submit to scoring queue
- ⏸️ System pause to freeze all game actions mid-round
- ✏️ Score editing and undo

### Content
- 🎯 10 prebuilt surveys included (~80 questions total) — plug-and-play for night one
- 📄 DOCX/PPTX upload to bulk-create rounds from your own survey files
- ➕ Manual round creation (question + answer list, one at a time)

### AI Scoring
- 🤖 AI semantic answer matching (Claude or GPT): understands synonyms, abbreviations, and specific-to-general matches ("minivan" → "van")
- 👀 Host reviews AI suggestions before anything is saved — AI suggests, host decides
- 🧠 Training feedback loop: your corrections are saved to `corrections_history.json` and fed back into future calls
- 📋 Fringe answer summary: after scoring, see which synonyms the AI accepted so you can announce them to the room
- 💰 ~$0.01 per round scored *(cheaper than hiring a scorer, more reliable than asking a regular)*

### Architecture
- 💥 Nuclear reset on every server start — fresh slate for every pub night
- 🗄️ SQLite on ephemeral filesystem *(the database with commitment issues)*
- 👻 Session invalidation on restart — no ghost teams from last week

---

## Game Flow

1. **Setup** (Host)
   - Create rounds and set correct answers (or load a prebuilt survey)
   - Generate team codes
   - Print code cards with QR codes

2. **Team Registration**
   - Teams scan QR or visit join page
   - Enter code and team name

3. **Game Play**
   - Activate a round
   - Teams submit answers via mobile
   - Broadcast a message if you need to get everyone's attention
   - Close submissions when ready

4. **Scoring**
   - Review submissions in the scoring queue
   - Use AI scoring for semantic matching, or score manually
   - *(Survey SAYS... the AI is usually right, but the host always wins)*
   - Award points; undo is available if you change your mind

5. **Winner**
   - View leaderboard
   - Announce winner
   - Advance to next round or wrap up the night

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- pip

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py

# Visit http://localhost:5000
# Host login: http://localhost:5000/host
# Default host password (dev only): localdev
# Photo scan shortcut: http://localhost:5000/host/scan
```

> **Note:** Each run of `python app.py` triggers the nuclear reset — the database wipes on startup. This is intentional. See [Architecture Notes](#architecture-notes).
>
> For verbose debug output: `LOG_LEVEL=DEBUG python app.py`

### Local Testing Notes
- Database resets when you restart the server (or delete `feud.db`)
- Logs saved to `/logs/` directory
- QR codes default to `http://localhost:5000`

---

## Cloud Deployment (Render.com)

### Prerequisites
- GitHub account
- Render.com account (free tier works)
- Optional: custom domain (e.g., pubfeud.gamenightguild.net)

### Deployment Steps

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/family-feud.git
   git push -u origin main
   ```

2. **Create Render App**
   - Go to [dashboard.render.com](https://dashboard.render.com)
   - "New" → "Web Service"
   - Connect your GitHub repo
   - Render auto-detects `render.yaml`
   - Click "Create Web Service"

3. **Configure Custom Domain** *(optional)*
   - In Render dashboard → your app
   - "Settings" → "Custom Domain"
   - Add your domain (e.g., `pubfeud.gamenightguild.net`)
   - Render provisions SSL automatically

4. **Setup DNS** *(if using GoDaddy)*
   - Go to DNS Management for your domain
   - Add CNAME record:
     - Name: `pubfeud`
     - Value: `your-app-name.onrender.com` (from Render)
     - TTL: 1 hour
   - Allow 10–60 minutes for propagation

5. **First Deploy**
   - Render auto-deploys from GitHub pushes
   - Visit your domain
   - Login with the `HOST_PASSWORD` you set in Render's environment variables
   - Configure QR base URL in `/host/settings`

> **Deploy = restart = database wipe.** Pushing to GitHub triggers a Render deploy, which restarts the server, which wipes the database. Perfect for weekly pub nights; less perfect if you were mid-game.
>
> **Free tier sleep:** Render's free tier apps sleep after 15 minutes of inactivity. If teams try to join and the page hangs, that's Render stretching after a nap. A $7/month Starter tier upgrade removes this.

---

## Environment Variables

Set in Render dashboard (or your local `.env` file):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SECRET_KEY` | Yes (Render auto-generates) | Random token | Flask session signing |
| `HOST_PASSWORD` | Yes | `localdev` *(dev only)* | Host dashboard PIN |
| `RENDER` | Cloud only | unset | Enables cloud mode (logging, URL detection) |
| `ANTHROPIC_API_KEY` | No | unset | Anthropic Claude API key (one provider required for AI scoring) |
| `OPENAI_API_KEY` | No | unset | OpenAI API key (alternative AI provider) |
| `ENABLE_AI_SCORING` | No | `false` | Must be `true` to activate AI scoring |
| `AI_MODEL` | No | auto (first available) | Override the AI model (Claude or GPT) |
| `GITHUB_TOKEN` | No | unset | Sync AI corrections history to a GitHub repo |
| `LOG_LEVEL` | No | `INFO` | Set to `DEBUG` for verbose troubleshooting |

> **AI Scoring requires** `ENABLE_AI_SCORING=true` **and** at least one API key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`). Both can be set — pick your model from the settings dropdown.

---

## Surveys & Content

### Prebuilt Surveys
Ten complete surveys are included, each with 8 rounds (~80 questions total). Load any survey from the host dashboard dropdown — no setup required. Enough to run your first few pub nights without touching a question editor.

### Upload Your Own
Upload a `.docx` or `.pptx` file from the host dashboard to bulk-create all rounds at once. Template survey files are included in the `/surveys/` directory for reference.

### Manual Round Creation
Create rounds one at a time via the host dashboard: enter the question, set the number of answers, and configure answer text and point values.

---

## Architecture Notes

### Nuclear Reset (Scorched Earth Policy)

Every time the server starts, the database is wiped completely: submissions, rounds, team names, sessions — all of it. Teams that were connected receive a polite message asking them to rejoin. The data does not get a polite message.

On Render, every deploy triggers a server restart, which triggers the wipe. This makes weekly pub nights trivially simple: deploy before the event, and you have a fresh game. No cleanup scripts, no stale team names from last month.

A **Reset All** button in the host dashboard performs the same wipe without a server restart, for mid-night resets.

Full details: [docs/architecture/NUCLEAR_RESET.md](docs/architecture/NUCLEAR_RESET.md)

### AI Scoring

Optional AI integration (Anthropic Claude or OpenAI GPT) for semantic answer matching. The AI understands synonyms, abbreviations, and the difference between "NY" and "New York." Host reviews all suggestions before anything is saved — the AI recommends, the host decides.

Your corrections are saved to `corrections_history.json` and fed back into future scoring calls, so the AI gradually learns your scoring philosophy (or at least stops suggesting the same wrong answer twice).

Requires `ENABLE_AI_SCORING=true` + at least one API key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`).

Full details: [docs/features/AI_SCORING.md](docs/features/AI_SCORING.md)

---

## Host Tools

| URL | Purpose |
|---|---|
| `/host` | Main dashboard |
| `/host/settings` | QR URL, registration toggle, system pause, broadcast |
| `/host/scan` | Photo scan shortcut (mobile-optimized) |
| `/host/print-codes` | Printable QR code cards (portrait) |
| `/host/print-codes-landscape` | Printable QR code cards (landscape) |
| `/host/scoring-queue` | Review and score submitted answers |

**Mobile hosts:** `/host/scan` auto-redirects on login. Bookmark it before pub night.

---

## Testing

Comprehensive test suite organized by planetary severity:

- **Mars (Security)** — XSS injection, SQL injection, auth bypass attempts
- **Venus (Stress)** — Concurrent submissions, API polling under load
- **Jupiter (Destruction)** — Race conditions, edge cases, data integrity under chaos
- **Oort Cloud (Limits)** — Unicode, NULL values, boundary conditions at the theoretical edge of acceptable input *(if it survives the Oort Cloud suite, it will survive your pub)*

Five targeted v1.1.0 feature tests cover: team reconnection, code reclaim, timestamp handling, heartbeat/active-tab detection, and score undo.

```bash
# Full planetary suite
python tests/test_planetary_suite_v3992.py

# v1.1.0 feature tests
python tests/test_v110_feature1_reconnect.py
python tests/test_v110_feature2_reclaim.py
python tests/test_v110_feature3_timestamp.py
python tests/test_v110_feature4_heartbeat.py
python tests/test_v110_feature5_undo.py

# AI feature tests
python tests/test_extended_thinking.py
python tests/test_photo_capture_review.py
```

---

## Tech Stack

| Component | Technology |
|---|---|
| **Backend** | Flask 3.1.2 |
| **Database** | SQLite (ephemeral) |
| **Production Server** | Gunicorn |
| **Frontend** | Vanilla JS + HTML/CSS *(no framework, no build step, just JavaScript doing its best)* |
| **QR Codes** | qrcode + Pillow |
| **Document Upload** | python-docx + python-pptx |
| **AI Scoring** | anthropic >= 0.55.0 / openai >= 1.30.0 *(optional — one or both)* |
| **Deployment** | Render.com |

---

## Cost

| Item | Cost |
|---|---|
| Render Free Tier | $0/month *(app sleeps after 15 min of inactivity)* |
| Render Starter Tier | $7/month *(always on — recommended for pub nights)* |
| AI Scoring (Anthropic / OpenAI) | ~$0.001–$0.05 per round (depends on model) |
| SQLite / ephemeral DB | Free *(the database deletes itself, saving you money and therapy)* |

---

## Security

- ✅ Host routes protected by PIN
- ✅ SQL injection prevention (parameterized queries throughout)
- ✅ XSS protection (template escaping, `textContent` not `innerHTML`)
- ✅ Session security (Flask signed cookies)
- ✅ HTTPS on Render (free SSL)
- ✅ Unambiguous team codes (no I, O, or L to prevent OCR/handwriting confusion)

See [docs/security/SECURITY_PATCHES.md](docs/security/SECURITY_PATCHES.md) for the full security audit history.

---

## Documentation

- [Changelog](docs/CHANGELOG.md) — Full version history
- [AI Scoring](docs/features/AI_SCORING.md) — AI-assisted scoring setup, usage, and training loop
- [Mobile Experience](docs/features/MOBILE_EXPERIENCE.md) — Mobile optimizations and photo scan
- [Nuclear Reset](docs/architecture/NUCLEAR_RESET.md) — Server startup reset behavior explained
- [Render Deployment](docs/deployment/RENDER_DEPLOYMENT.md) — Cloud deployment guide
- [Security Patches](docs/security/SECURITY_PATCHES.md) — Security audit history

---

## Support

If something's broken:
1. Check the logs (local: `/logs/`, Render: dashboard)
2. Run the test suite — the planetary names will tell you which layer failed
3. Check GitHub issues

---

## Credits

Built for weekly pub trivia nights at Game Night Guild local venues.

Powered by Flask, Gunicorn, and a determination to avoid spreadsheets.

AI scoring powered by Claude (Anthropic) and GPT (OpenAI) — who also wrote the test suite and therefore have some skin in the game.

Ten prebuilt surveys included so you don't have to spend Friday afternoon writing trivia questions.

If something breaks mid-game, the audience is usually distracted by their drinks.

---

## License

Private use for Game Night Guild pub trivia events.

---

**v4.0.0 - Plasma** | Battle-tested at actual pub nights | Survey SAYS: production ready. 🍻
