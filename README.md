# Family Feud — Pub Trivia Game by Game Night Guild

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

## How to Run a Game (Step by Step)

*Everything you need to know, even if you've never touched the app before.*

---

### Step 1: Before the Game (Setup at Home)

You'll do this once before heading to the venue. Takes about 5 minutes.

1. **Open the host dashboard** — go to `/host` in your browser and enter your PIN password.
2. **Load your questions.** You have three options:
   - **Easiest:** Pick a prebuilt survey from the dropdown (10 included — enough for your first few nights).
   - **Custom:** Upload a `.docx` or `.pptx` file with your own survey questions.
   - **Manual:** Create rounds one at a time from the dashboard.
3. **Understand the structure.** Every game has **8 rounds**. Each round has one question (e.g., *"Name something people do on their lunch break"*) and **3–6 ranked answers** based on a survey. The #1 answer is worth the most points, the last answer is worth the least.
4. **Print QR code cards** from the dashboard — one card per team. Each card has a unique 4-letter code and a QR code that links straight to the join page. *(Landscape or portrait — your call.)*
5. **Optionally print paper answer sheets** if you want teams to write answers by hand instead of using their phones.
6. **Tweak your settings** (`/host/settings`):
   - Pick a color theme (classic, dark, forest, stadium, or gamenight)
   - Set the QR base URL if you're using a custom domain
   - Choose a mobile experience mode (basic, advanced, or advanced with photo play)
   - Turn AI scoring on or off
7. **Optionally enable the TV Board** if you have a projector or big screen for the dramatic answer reveals.

> **Pro tip:** Bookmark `/host/scan` on your phone before you leave the house. You'll thank yourself later.

---

### Step 2: At the Venue — Team Registration

1. **Hand out QR code cards** to each table (or display a big QR on a screen).
2. **Teams scan the QR code** with their phone camera. It opens the join page automatically.
3. Teams enter the **4-letter code** printed on their card (e.g., `HBKM`). No I, O, or L in the codes — those letters cause too many arguments.
4. Teams pick a **team name** (max 30 characters — keep it pub-friendly).
5. That's it. They're in. No app to install, no account to create.
6. **On your dashboard**, you'll see each team appear as they join. Green dot = online. Grey dot = they went to the bar.
7. **If a team loses connection** (phone dies, Wi-Fi drops, someone closes the tab), they can rejoin by entering their code and team name again. No progress lost.

---

### Step 3: Playing a Round

*Repeat this for each of the 8 rounds.*

1. **Activate the round** from your host dashboard. Tap the round number, then "Activate."
2. **Every team's phone instantly updates** — they see the question and a set of blank answer fields (3–6 fields, depending on the round).
3. **Teams type their guesses.** Example: If the question is *"Name something you'd find in a junk drawer,"* a team might type: *Batteries, Tape, Scissors, Pens, Rubber Bands.*
4. **Teams enter a tiebreaker** — a number from 0 to 100, representing their guess for what percentage of survey respondents gave the #1 answer. *(This breaks ties later. Tell them to guess, not overthink it.)*
5. **Teams hit Submit.** One shot per round — no editing after submission. Make it count.
6. **You'll see a live counter** on your dashboard: "12 of 15 teams submitted." Use this to know when to move on.
7. **Close submissions** when you're ready — either when all teams have submitted, or when you decide time's up. Tap "Close Submissions" on the dashboard.

> **Need everyone's attention?** Use the **Broadcast** feature to send a message (up to 200 characters) to every team's phone. It pops up as a banner they can't ignore.

---

### Step 4: Scoring — Digital Submissions (Phones)

*This is how you score when teams submitted answers from their phones.*

1. **Open the Scoring Queue** from your dashboard.
2. **For each team**, you'll see:
   - The team's submitted answers on one side
   - The correct survey answers on the other side
3. **Check the boxes** next to each answer the team got right. The app does the math for you.
   - **How points work:** The #1 survey answer is worth the most points, and each answer below it is worth one less. If a round has 5 answers, matching the #1 answer earns 5 points, #2 earns 4, #3 earns 3, and so on.
4. **Or let the AI do it.** If AI scoring is enabled, tap "AI Score" — the AI reads the team's answers, figures out which ones match (including synonyms, abbreviations, and creative spellings), and suggests checkboxes. You review the suggestions and accept or adjust.
   - *"Minivan" matches "Van." "NYC" matches "New York." "Sammich" matches "Sandwich." The AI gets it.*
5. **Confirm the score.** The team immediately sees their result on their phone.
6. **Repeat** for every team's submission in the queue.

> **Made a mistake?** Scores can be undone or edited at any time. Nobody has to know.

---

### Step 5: Scoring — Paper Answer Sheets + Photo Scan

*This is the alternative for teams that wrote answers on paper instead of phones.*

1. **Collect the paper answer sheets** from the tables.
2. **Open `/host/scan`** on your phone (that bookmark you made in Step 1 — told you).
3. **Snap a photo** of each answer sheet.
4. **The AI reads the handwriting** and extracts: team code, team name, answers, and tiebreaker. Fields it's not sure about are highlighted in orange with a "CHECK" badge.
5. **Review the extracted data** — fix anything the AI got wrong (messy handwriting happens).
6. **Hit Submit** — the answers go into the Scoring Queue, where you score them the same way as digital submissions (Step 4).

---

### Step 6: After Scoring a Round

1. **The leaderboard updates automatically** on every team's phone. No refresh needed.
2. **View the scored teams list** on your dashboard — teams ranked by score, with tiebreaker distance shown.
3. **Undo or edit** any score if you catch a mistake. The "previous score" is saved so you can always revert.
4. **Check the "AI Accepted Answers" summary** — it shows which synonyms and alternate answers the AI counted as correct. Announce these to the room so teams stop arguing. *(They will argue anyway.)*

---

### Step 7: The TV Board — Big Screen Reveals *(Optional but Awesome)*

*This is the dramatic, Family-Feud-style answer reveal on a projector or TV. Skip this if you don't have a big screen.*

1. **Enable TV Board** in `/host/settings`.
2. **Open `/tv/board`** in a browser on the computer connected to your projector/TV. This page is full-screen and doesn't require a login.
3. **Control the board from your phone** — go to `/host/reveal-control` (or scan the QR code shown on your dashboard).
4. **Switch screens** to set the mood:
   - **Welcome** → show before the game starts
   - **Rules** → quick rules overview
   - **Question** → displays the current round's question in big text
   - **Board** → the answer board with hidden tiles
   - **Halftime** → break screen
   - **Closing** → end-of-night screen
5. **Reveal answers one by one.** On the Board screen, tap each answer tile to flip it from blue (hidden) to gold (revealed). Classic Family Feud flip animation included.
6. **"And The Survey Says..."** — tap this button for maximum drama. A 3-2-1 countdown plays, then the #1 answer is revealed.
7. **"Reveal All"** — shows all remaining answers in sequence (one per second). Use this when you're ready to move on.

---

### Step 8: Between Rounds

1. **Broadcast a message** if you need to ("Round 3 starting in 2 minutes — grab a drink!").
2. **Activate the next round** from your dashboard.
3. **Teams' phones auto-update** — they see the new question and fresh answer fields immediately.
4. **Repeat Steps 3–7** for all 8 rounds.

---

### Step 9: End of the Night

1. **View the final leaderboard** — cumulative scores across all 8 rounds.
2. **Announce the winner.** Buy them a round. Or don't. Your call.
3. **For a second game** (same night): Hit **"Reset"** — clears all scores and rounds but keeps teams joined. Load a new survey and go again.
4. **To fully reset**: Hit **"Reset All"** — wipes everything. Teams see a "Game Over" screen and have to rejoin from scratch.
5. **Or just shut down the server** — it wipes the database on every startup anyway. That's by design. See [Nuclear Reset](#nuclear-reset-scorched-earth-policy).

---

### Host Cheat Sheet

| What | Where |
|---|---|
| Host dashboard | `/host` |
| Settings | `/host/settings` |
| Photo scan (mobile) | `/host/scan` |
| Scoring queue | `/host/scoring-queue` |
| TV board (projector) | `/tv/board` |
| Reveal control (phone) | `/host/reveal-control` |
| Print QR cards | `/host/print-codes` |
| Print answer sheets | `/host/print-answer-sheets` |

> **Three mobile experience modes:**
> - **Basic** — Teams submit answers only. Simple, fast, no distractions.
> - **Advanced** — Submit answers + see the live leaderboard on their phone.
> - **Advanced + Photo Play** — Full experience including photo features. Auto-enables the TV Board.

---

## Mobile UI Flows

*How each mode works on a phone, screen by screen.*

---

### Team Player Mode

**Entry point:** Scan QR code → `/join?code=XXXX`

| Step | Screen | What Happens |
|------|--------|-------------|
| 1 | **Join** (`/join`) | QR pre-fills the 4-letter code. Team taps "Submit." If code is unused → name entry form. If code was already used → reconnection form (enter team name to rejoin). |
| 2 | **Name Registration** | Team picks a name (max 30 chars, no duplicates). Session created. Redirects to `/play`. |
| 3 | **Waiting** (`/play`) | "Waiting for host to start a round…" message. Fixed header shows team name + green connection dot. Poll every 5–10s for round activation. |
| 4 | **Answer Submission** (`/play`) | Round activates → screen updates automatically. Shows the question, 3–6 answer input fields, and a tiebreaker field (0–100). Answers auto-save to localStorage on every keystroke (debounced 500ms). |
| 5 | **Submit** | Team taps Submit. One shot per round — no edits after. Live counter shows "X of Y teams submitted." |
| 6 | **Already Submitted** | Confirms submission. Shows what the team entered (read-only). Leaderboard updates arrive via WebSocket after host scores. |
| 7 | **Game Over** | Server restart or host "Reset All" → session invalidated → "Game Over" screen with reason. Must rejoin from scratch. |

**Mobile-specific UI:**
- Fixed header: team name, round number, connection status (green/grey pulse dot)
- Collapsible instructions section (tap to expand)
- 44px touch targets on all inputs
- Submit button stays visible above the keyboard
- Broadcast banners from host appear as dismissible alerts
- `mobile_experience` setting controls UI variant (`simple` vs `advanced_no_pp`)

---

### Host Dashboard Mode

**Entry point:** `/host/login` → enter PIN → `/host`

| Step | Screen | What Happens |
|------|--------|-------------|
| 1 | **Login** (`/host/login`) | Password form. On mobile with AI enabled, redirects to photo scan after login. On desktop, redirects to dashboard. |
| 2 | **Dashboard** (`/host`) | Main control panel. Shows: team code grid (green = online, grey = offline), active round status, unscored submission count, round list with action buttons, QR code for TV reveal access. |
| 3 | **Generate Codes** | Generates 4-letter team codes. Print as QR cards (portrait or landscape) from `/host/print-codes`. |
| 4 | **Create Rounds** | Three options: upload `.docx`/`.pptx` (bulk), manual entry (one at a time), or AI generation (Claude API). |
| 5 | **Activate Round** | Tap a round → "Activate." Broadcasts `round:started` to all teams — their phones update instantly. |
| 6 | **Monitor** | Live submission counter. Broadcast messages to all teams (up to 200 chars). Close submissions when ready. |
| 7 | **Settings** (`/host/settings`) | QR base URL, registration toggle, system pause, AI model selection, color theme, TV board toggle, mobile experience mode. |
| 8 | **Reset** | "Reset" clears scores/rounds but keeps teams. "Reset All" wipes everything — teams see Game Over. |

**Real-time updates:** Team join/leave events, online/offline status, and submission counts all update via WebSocket without refresh.

---

### Scoring Mode

**Entry point:** Dashboard → "Scoring Queue" → `/host/scoring-queue`

| Step | Screen | What Happens |
|------|--------|-------------|
| 1 | **Scoring Queue** (`/host/scoring-queue`) | One team at a time. Arrow navigation between submissions. Unscored teams appear first. Shows: team name, submitted answers, correct survey answers with point values, checkboxes for each match. |
| 2a | **Manual Score** | Host checks boxes next to correct answers. Points auto-calculated (#1 answer = most points, descending). Tap "Save Score." |
| 2b | **AI Score** | Tap "AI Score" — AI reads team answers and pre-checks likely matches (synonyms, abbreviations, specific-to-general). Host reviews and adjusts before saving. |
| 3 | **Confirm** | Score saved. Team's phone updates via WebSocket. Navigate to next team with arrows. |
| 4 | **Scored Teams** (`/host/scored-teams`) | All scored teams ranked by score. Tiebreaker distance shown. Undo or edit any score. |

**Alternative entry — Photo Scan** (`/host/scan`):

| Step | Screen | What Happens |
|------|--------|-------------|
| 1 | **Camera** (`/host/photo-scan`) | Host photographs a paper answer sheet. |
| 2 | **AI OCR** | AI extracts team name, answers, and tiebreaker from the photo. Uncertain fields highlighted in orange with "CHECK" badge. |
| 3 | **Review** | Host corrects any OCR errors. |
| 4 | **Submit** | Answers go into the scoring queue — scored the same way as digital submissions. |

**Alternative entry — Manual Entry** (`/host/manual-entry`):

| Step | Screen | What Happens |
|------|--------|-------------|
| 1 | **Form** | Select team from dropdown, type answers, enter tiebreaker. |
| 2 | **Submit** | Creates a submission in the scoring queue. |

---

### TV Reveal Control Mode

**Entry point:** Scan QR from dashboard → `/reveal/<token>` (passwordless) → `/host/reveal-control`

| Step | Screen | What Happens |
|------|--------|-------------|
| 1 | **Access** | Host scans QR code shown on dashboard. Token grants host session — no password needed. Redirects to reveal control. |
| 2 | **Screen Select** (`/host/reveal-control`) | Buttons to switch the TV display: Welcome → Rules → Question → Board → Halftime → Closing. |
| 3 | **Question** | Displays current round's question in big text on TV. |
| 4 | **Board** | Answer tiles shown as hidden (blue). Host taps each tile to reveal (flip to gold). Classic Family Feud animation. |
| 5 | **"And The Survey Says…"** | Drama button — 3-2-1 countdown, then #1 answer revealed. |
| 6 | **Reveal All** | Shows all remaining answers in sequence (one per second). |
| 7 | **Scores** | Leaderboard appears on TV after all answers revealed. Teams' phones also receive the update. |

**TV Board** (`/tv/board`): Full-screen display for projector. No login required. Listens for WebSocket events from the reveal control. All state is in-memory and resets on server restart.

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

**v4.1.0 - Plasma** | Battle-tested at actual pub nights | Survey SAYS: production ready. 🍻
