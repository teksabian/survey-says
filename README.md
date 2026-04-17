# Survey Says — Pub Trivia Game by Game Night Guild

*A Flask-powered survey-style game for pub trivia nights. Teams join via QR codes, AI does the homework, and the database deletes itself when you're done.*

> This README is the **Host / Operator's Manual**. Everything the host needs — from plugging it in to running a full night — is in here. Bookmark it, skim the parts you need, ignore the footnotes until something breaks.

---

## Table of Contents

1. [What Is This?](#what-is-this)
2. [Features at a Glance](#features-at-a-glance)
3. [Quick Start (Local Dev)](#quick-start-local-dev)
4. [The Operator's Playbook — Running a Game Night](#the-operators-playbook--running-a-game-night)
5. [Mobile Phone Game Modes (Deep Dive)](#mobile-phone-game-modes-deep-dive)
6. [Settings Reference (Every Toggle Explained)](#settings-reference-every-toggle-explained)
7. [Host Tools Reference](#host-tools-reference)
8. [The TV Board (Big-Screen Reveal)](#the-tv-board-big-screen-reveal)
9. [Surveys & Content](#surveys--content)
10. [Environment Variables](#environment-variables)
11. [Cloud Deployment (Render.com)](#cloud-deployment-rendercom)
12. [Architecture Notes](#architecture-notes)
13. [Security](#security)
14. [Testing](#testing)
15. [Troubleshooting](#troubleshooting)
16. [Tech Stack, Cost, Credits, License](#tech-stack-cost-credits-license)

---

## What Is This?

A complete digital Survey Says game built for weekly pub trivia nights. Teams join from their phones — no app install, no account creation, no asking the bartender for the WiFi password. Scan a QR code, enter a team name, and they're in.

The host (that's you) runs everything from a dashboard on any device: create rounds, activate questions, score answers, manage chaos as needed. Ten complete survey sets are included so you can run a full night out of the box. Bring your own questions via DOCX/PPTX upload, or create rounds manually if you enjoy that sort of thing.

**The game in one paragraph:** Every game has **8 rounds** (configurable 4–12). Each round has one survey question (*"Name something people do on their lunch break"*) and **3–6 ranked answers**. Teams type their guesses on their phones plus a tiebreaker (0–100). The host scores each team either by clicking checkboxes or by pressing the AI button and reviewing the suggestions. Matched answers score points (#1 answer = the most, last = 1 point). Leaderboard updates in real time. After 8 rounds, highest cumulative score wins. The bartender will not need to help anyone.

---

## Features at a Glance

### For Teams (Phone Side)
- 📱 Mobile-first interface with auto-save — answers survive app switching, phone sleep, and accidental navigation
- 🔑 Join via QR code or 4-letter team code *(no I, O, L, C, D, G, U, or V — the letters most likely to ruin someone's night)*
- 🔄 Real-time round updates via WebSocket (with polling fallback)
- 🟢 Connection status indicator (green dot = present, grey = somewhere else)
- 🔁 Team reconnect and code reclaim after disconnect
- 📊 **Three mobile experience modes** — plain submit, live leaderboard, or full PowerPoint-style reveal tracking (details below)

### For the Host
- 🔒 PIN-protected host dashboard
- 📢 Broadcast messages to all teams simultaneously (200 char banner)
- 🖨️ Printable QR code cards (portrait or landscape) and paper answer sheets
- 📷 `/host/scan` — mobile shortcut for photo scan *(bookmark it before pub night)*
- 📸 Photo scan: photograph paper answer sheets → AI OCR → auto-submit to scoring queue
- ⏸️ System pause to freeze all game actions mid-round
- ✏️ Score editing, undo, and reclaim-code for kicking inactive teams
- 💤 Sleep Server button to let Render spin down between nights

### Content
- 🎯 **10 prebuilt surveys** included (~80 questions total) — plug-and-play for night one
- 📄 DOCX/PPTX upload to bulk-create rounds from your own survey files
- ➕ Manual round creation (question + answer list, one at a time)
- 🤖 Optional AI round generation (Claude/GPT writes the questions and answers for you)

### AI Assist
- 🤖 Semantic answer matching (Claude or GPT): understands synonyms, abbreviations, specific-to-general ("minivan" → "van")
- 👀 Host reviews AI suggestions before anything is saved — AI suggests, host decides
- 🧠 Extended Thinking mode (Anthropic only) for deeper reasoning on tricky calls
- 🧾 Separate model selection for **OCR** (reading photos) and **Scoring** (matching answers)
- 📋 Training feedback loop: corrections saved to `corrections_history.json` and fed back into future calls
- 💰 ~$0.001–$0.05 per round depending on model *(cheaper than hiring a scorer, more reliable than asking a regular)*

### Architecture
- 💥 Nuclear reset on every server start — fresh slate for every pub night
- 🗄️ SQLite on ephemeral filesystem *(the database with commitment issues)*
- 👻 Session invalidation on restart — no ghost teams from last week
- 🔌 WebSocket real-time layer (Flask-SocketIO + gevent)

---

## Quick Start (Local Dev)

### Prerequisites
- Python 3.11+
- pip

### Setup
```bash
pip install -r requirements.txt
python app.py
# Visit http://localhost:5000
# Host login:  http://localhost:5000/host
# Default dev password: localdev
# Photo scan shortcut: http://localhost:5000/host/scan
```

> **Heads-up:** Every run of `python app.py` wipes the database on startup. That's by design — see [Nuclear Reset](#nuclear-reset-scorched-earth-policy).
>
> For verbose output: `LOG_LEVEL=DEBUG python app.py`

### Local Notes
- Database resets when you restart the server (or delete `feud.db`)
- Logs saved to `/logs/<timestamp>.log`
- QR codes default to `http://localhost:5000` (override in `/host/settings`)

---

## The Operator's Playbook — Running a Game Night

*Everything you need to know, even if you've never touched the app before. Follow it start to finish on your first night; skim it on later nights.*

---

### Step 1: Before the Game (Setup at Home)

Takes about 5 minutes. Do this once before heading to the venue.

1. **Open the host dashboard** — go to `/host` in your browser and enter the PIN (`HOST_PASSWORD`).
2. **Load your questions.** Three options:
   - **Easiest:** Pick a prebuilt survey from the dropdown (10 included — enough for your first few nights).
   - **Custom:** Upload a `.docx`, `.pptx`, or `.pptm` file with your own survey questions.
   - **Manual:** Create rounds one at a time from the dashboard (question, number of answers, answer text, #1-answer count).
   - **AI-generated:** Ask Claude/GPT to write a whole set for you (requires AI keys configured).
3. **Verify the structure.** Every game defaults to **8 rounds**. Each round has one question and **3–6 ranked answers**. The #1 answer is worth the most points; the last answer is worth 1 point.
4. **Print QR code cards** from `/host/print-codes` (portrait) or `/host/print-codes-landscape` (landscape) — one card per team. Each card has a unique 4-letter code and a QR code that links straight to the join page.
5. **Optionally print paper answer sheets** from the dashboard ("📝 Answer Sheets" button) — Group 1 (codes 1-30) and Group 2 (31-60). Use these if you want teams to write answers by hand instead of phones.
6. **Tweak your settings** (`/host/settings`). See the [Settings Reference](#settings-reference-every-toggle-explained) for every knob:
   - Pick a **Color Theme** (8 available — 5 gaming + 3 easy-read)
   - Set the **QR base URL** if you're using a custom domain
   - Pick a **Mobile Experience Mode** (basic / advanced-no-PP / advanced-PP)
   - Turn **AI Scoring** on or off
   - Turn on the **TV Board** if you have a projector or big screen
7. **Bookmark `/host/scan` on your phone** before you leave the house. You'll thank yourself when paper sheets pile up.

---

### Step 2: At the Venue — Team Registration

1. **Hand out QR code cards** to each table (or project a big QR on screen).
2. **Teams scan the QR code** with their phone camera. It opens `/join?code=XXXX` automatically.
3. Teams see the **4-letter code** pre-filled on their card (e.g., `HBKM`). No I, O, L, C, D, G, U, or V in the codes — those cause too many arguments and OCR misreads.
4. Teams pick a **team name** (max 30 characters, must be unique — duplicates auto-suffix with "2", "3", etc.).
5. That's it. They're in. No app to install, no account to create.
6. **On your dashboard**, you'll see each team appear live (green dot = online via active heartbeat, grey dot = offline / went to the bar). The team grid auto-refreshes via WebSocket; no page reload needed.
7. **If a team loses connection**, they rejoin by entering their code and team name again. The app validates they own the code and restores their session — no progress lost.
8. **If a team abandons their code** (wrong team name, wrong table, whatever), click **🗑️ Reclaim** on their code tile. This frees the code and wipes their submissions.

---

### Step 3: Playing a Round

*Repeat for each of the 8 rounds.*

1. **Activate the round** from your dashboard. Tap the round number, then "Activate." The WebSocket fires `round:started` and every connected phone updates instantly.
2. **Every team's phone shows** the question plus 3–6 blank answer fields (round-dependent) and a tiebreaker field.
3. **Teams type their guesses.** Example: *"Name something you'd find in a junk drawer"* → *Batteries, Tape, Scissors, Pens, Rubber Bands.*
4. **Teams enter a tiebreaker** (0–100) — their guess at the percentage of survey respondents who gave the #1 answer. This only matters when scores tie, but collect it every round anyway.
5. **Teams hit Submit.** One shot per round — no edits after submission (the submit button literally disables). Answers auto-save to localStorage every 500ms, so even accidental phone lock / app-switch / battery drama survives.
6. **Live submission counter** on your dashboard: "12 of 15 teams submitted." Use it to decide when to move on.
7. **Close submissions** with the big red 🔒 **End Round & Score** button when you're ready. Teams who haven't submitted won't be scored for this round. (They can still play next round.)

> **Need everyone's attention?** Use the **Broadcast** feature (`/host/settings` → "📢 Broadcast Message") to send up to 200 characters to every team's phone. It appears as a dismissible blue banner.

---

### Step 4: Scoring — Digital Submissions (Phones)

1. **Open the Scoring Queue** from your dashboard ("🎯 Go to Scoring Queue" after closing the round, or `/host/scoring-queue` directly).
2. **Navigate teams** with the arrow buttons. Unscored teams appear first; already-scored teams follow.
3. **For each team**, you see:
   - The team's submitted answers (left)
   - The correct survey answers with point values (right)
   - A checkbox next to each correct answer
4. **Score manually:** check the box next to each answer the team got right → points auto-calculate → tap **Save Score**.
   - Scoring math: #1 answer = num_answers points, #2 = num_answers−1, etc. For a 5-answer round, matching #1 and #3 = 5 + 3 = **8 points**.
5. **Or use AI:** if AI scoring is on, tap **🤖 AI Score** — the AI reads the team's answers, figures out which match (synonyms, abbreviations, creative spellings), pre-checks those boxes, and shows brief reasoning. You review and adjust, then Save.
   - *"Minivan" matches "Van." "NYC" matches "New York." "Sammich" matches "Sandwich." The AI gets it.*
6. **Confirm the score.** The team's phone updates immediately via WebSocket.
7. **Repeat** for every submission in the queue.

> **Made a mistake?** On `/host/scored-teams`, tap **Undo** (reverts to the previous score) or **Edit** (re-opens the checkbox view). Nobody has to know.

---

### Step 5: Scoring — Paper Answer Sheets + Photo Scan

1. **Collect the paper answer sheets** from the tables.
2. **Open `/host/scan`** on your phone.
3. **Snap a photo** of each answer sheet (page of 4 blocks or single-team block — both supported).
4. **The AI reads the handwriting** and extracts: 4-letter code, team name, Answer 1–6, and tiebreaker. Fields it's unsure about get an orange **CHECK** badge.
5. **Review & fix** anything the AI got wrong (messy handwriting happens — especially on "5"/"S", "1"/"7", and anything a barfly wrote).
6. **Submit** — the extracted answers land in the Scoring Queue, where you score them the same way as digital submissions (Step 4).

---

### Step 6: After Scoring a Round

1. **The leaderboard updates automatically** on every team's phone (no refresh needed) via the `leaderboard:update` WebSocket event.
2. **View the scored teams list** at `/host/scored-teams` — ranked by score, tiebreaker distance shown for ties.
3. **Undo or edit** any score if you catch a mistake.
4. **Check the "AI Accepted Answers" summary** (when using AI scoring) — lists which synonyms and alternates the AI counted. Announce these to the room so teams stop arguing. *(They will argue anyway.)*

---

### Step 7: The TV Board — Big-Screen Reveals *(Optional but Awesome)*

*Skip this if you don't have a projector or TV. Required if you're running `advanced_pp` mobile mode.*

1. **Enable the TV Board** in `/host/settings` → "📺 Enable TV Board Display".
2. **Open `/tv/board`** in a browser on the computer connected to your projector/TV. Full-screen, no login.
3. **Control it from your phone:** scan the **TV Remote** QR on your dashboard (goes to `/reveal/<token>` → passwordless host session → `/host/reveal-control`). No need to type the PIN on your phone.
4. **Switch TV screens** to set the mood:
   - **Welcome** → before the game starts
   - **Rules** → quick rules overview
   - **Question** → current round's question, huge text
   - **Board** → the answer grid with hidden tiles
   - **Halftime** → break screen
   - **Closing** → end-of-night screen
5. **Reveal answers one by one.** On the Board screen, tap each tile to flip it from blue (hidden) to gold (revealed). Classic flip animation included.
6. **"And The Survey Says..."** — the drama button. 3-2-1 countdown, then the #1 answer reveals with flourish.
7. **Reveal All** — cascades through every remaining answer (one per second). Use when you're ready to move on.
8. **Scores appear on the TV** after all answers are revealed (`scores_revealed` flag flips on). Teams on `advanced_pp` mobile mode also get to see the scoreboard unhidden at that point.

---

### Step 8: Between Rounds

1. **Broadcast** if you need to ("Round 3 starting in 2 minutes — grab a drink!").
2. **Activate the next round** from the dashboard.
3. **Teams' phones auto-update** — new question, fresh answer fields, tiebreaker cleared.
4. **Repeat Steps 3–7** for all 8 rounds.

---

### Step 9: End of the Night

1. **View the final leaderboard** — cumulative scores across all 8 rounds.
2. **Announce the winner.** Buy them a round. Or don't. Your call.
3. **Second game same night?** Hit **🔄 RESET GAME** — clears scores and rounds but keeps teams joined. Load a new survey and go again.
4. **Full reset?** Hit **🗑️ RESET EVERYTHING** — wipes all teams, codes, rounds, submissions. Teams get kicked to a Game Over screen.
5. **Or just shut down the server** — it wipes the database on every startup anyway. See [Nuclear Reset](#nuclear-reset-scorched-earth-policy).
6. **Done for the week?** Hit **💤 Put Server to Sleep** in settings to stop auto-refreshes and let Render spin down. Saves resources; wakes on next page load.

---

### Host Cheat Sheet — Every URL You Need

| What | Where |
|---|---|
| Host dashboard | `/host` |
| Host login | `/host/login` |
| Settings | `/host/settings` |
| Scoring queue | `/host/scoring-queue` |
| Scored teams / undo / edit | `/host/scored-teams` |
| Photo scan (mobile shortcut) | `/host/scan` |
| Photo scan (full) | `/host/photo-scan` |
| Manual entry | `/host/manual-entry` |
| Print QR cards (portrait) | `/host/print-codes` |
| Print QR cards (landscape) | `/host/print-codes-landscape` |
| Print answer sheets | `/host/print-answer-sheets?group=1` (or `2`) |
| TV board (projector, no login) | `/tv/board` |
| Reveal control (phone) | `/host/reveal-control` |
| Passwordless reveal login | `/reveal/<scan_token>` |

---

## Mobile Phone Game Modes (Deep Dive)

*The big one. This is what teams actually see on their phones.*

Survey Says has **one game (survey-style trivia)** but **three mobile experience modes** that change how much information teams get on their phones during and after each round. Pick the mode before the game starts (`/host/settings` → 📱 Mobile Experience). You can change it mid-game, but teams currently viewing a screen may need to navigate to pick up the change.

### The Three Modes at a Glance

| Mode | Value in settings | What teams see after submitting | Best for |
|---|---|---|---|
| **Basic** | `basic` | Classic waiting screen ("Survey Says…"), no leaderboard | Old-school feel, minimal distraction, phones-off vibe |
| **Advanced (No PP Display)** | `advanced_no_pp` | Live leaderboard with real scores visible | Games **without** a TV/projector PowerPoint reveal — teams get their eye candy on-phone |
| **Advanced (PP Display)** | `advanced_pp` | Live leaderboard with scores **hidden until the TV reveals them**, plus an on-phone "Survey Answers" tracker that mirrors the TV board as you flip tiles | Full pub-trivia theater — requires the **TV Board enabled** (auto-enforced by this mode) |

> Technical note: the mode lives in the `mobile_experience` database setting (default `advanced_no_pp`). The play page (`templates/play.html`) branches on this value to render different UI.

---

### Common Mobile UI (All Three Modes)

Every team phone has the same chrome regardless of mode:

- **Fixed header** (pinned at top):
  - Line 1: team name, connection status dot (green pulse = online, grey = disconnected), small gear icon (links to a join-code help screen)
  - Line 2: round number + current question, word-wrapped, big text
- **Broadcast banner** (blue, dismissible) — slides in when the host broadcasts a message
- **Viewport lock** — no zoom, no overscroll, submit button stays visible above the keyboard
- **44px touch targets** on every input and button
- **Auto-save to localStorage** every 500ms — survives app switching, phone sleep, accidental back-navigation
- **Session invalidation** — on server restart or "Reset All", the phone sees a mismatch between its session and the server's `STARTUP_ID`/`reset_counter` and shows the **Game Over** screen

---

### The Shared Round Lifecycle (What All Teams Experience)

1. **Join** (`/join`) — QR pre-fills the 4-letter code. Team taps Next → enters team name → redirected to `/play`.
2. **Waiting** (`/play`, no active round) — "⏳ Waiting for the Round to Start" with loading animation. Polls `/api/check-round-status` every 5–10s as a WebSocket fallback.
3. **Answer Submission** (`/play`, active round) — question in the header, 3–6 input fields labeled "Answer 1" to "Answer N", tiebreaker field (0–100). Submit button.
4. **Already Submitted** — the mode-specific screen (described below). Waits for the next round to activate.
5. **Round Transition** — when the host activates the next round, a **Winner Interstitial** overlays the current screen showing last round's winner (team name, score, trophy), then a "Next Round →" button drops them back into the Answer Submission state.
6. **Game Over** — server restart, Reset All, or stale session → "Game Over" screen with rejoin link.

The **only** screen that differs between the three modes is **#4 — Already Submitted**. Everything else is identical.

---

### Mode 1: Basic (`basic`)

**Post-submit screen:**
- Logo + "Survey Says"
- "Round N" label
- Green ✅ "Submitted"
- If submissions not yet closed: "⚠️ Do not manually refresh the page" warning + spinner + "Waiting for next round…"
- If submissions closed: red "⏰ Round Has Ended" card + "The host is now scoring. Wait for the next round!"
- **No leaderboard, no answer tracker, no score reveal.** Teams wait for the host to move on.

**When to pick it:**
- You're running the game without a TV board and don't want phones stealing the crowd's attention
- Elderly crowd / low-tech vibe
- Purists who want the spectacle on paper / projector, phones as silent input devices only

**Tech note:** `play.html` skips rendering `#leaderboard-container` entirely when `mobile_experience == 'basic'` — the WebSocket leaderboard events still fire but there's nothing to update on the phone.

---

### Mode 2: Advanced (No PP Display) — `advanced_no_pp` *(default)*

**Post-submit screen:**
- Everything from Basic, PLUS
- **Live Leaderboard** section — updates in real time as the host scores each team
  - All teams listed, ranked by cumulative score
  - "LIVE" badge, gold/silver/bronze rank circles for top 3
  - Your own team row is highlighted green + "(You)" suffix
  - Teams not yet scored for the current round show an hourglass ⌛ next to their rank
- The whole thing smoothly reorders as scores come in (0.5s CSS transition)

**When to pick it:**
- You're running the game **without** a TV/projector reveal — the phone IS the show
- Teams should see their score progression round by round
- Fast pace, minimal ceremony

**Tech note:** `play.html` fetches `/api/leaderboard` on load, then listens for `leaderboard:update` WebSocket events. `scoresRevealed` is always treated as true in this mode, so scores display immediately.

---

### Mode 3: Advanced (PP Display) — `advanced_pp` *(requires TV Board)*

This is the full theatrical experience, syncing the phone to the TV board so teams feel the reveal without spoilers.

**Post-submit screen:**
- "Round N" header + ✅ Submitted
- **Your Answers** section — read-only list of what the team submitted (#1 through #num_answers)
- **Survey Answers Tracker** (starts hidden, fills in as the host reveals tiles on the TV)
  - Each revealed survey answer appears in the team's list
  - ✅ Green row + points earned if the team matched that answer
  - ❌ Dim row if they missed
  - Slide-in animation as each reveal fires
- **Live Leaderboard** — same as `advanced_no_pp` BUT:
  - Scores display as **???** in gold until the host reveals them on the TV
  - When the TV hits "all revealed," the `leaderboard:scores_revealed` event fires and the `???` flips to real numbers with a pop animation

**Auto-enforcement:**
- When you pick `advanced_pp` in settings, **TV Board is force-enabled** and cannot be toggled off until you switch back to a different mode. The settings toggle is visually locked in the "on" position with a tooltip.

**When to pick it:**
- You've got a projector / TV connected to `/tv/board`
- You want the Family-Feud-game-show feel: phones for input, TV for reveals, shared drama
- You like making teams wait to see their score

**Tech note:** `play.html` tracks `myCheckedAnswers` (which survey answers THIS team matched), then listens for `tv:reveal` events to render the per-answer row in the tracker. `leaderboard:scores_revealed` flips the `scoresRevealed` flag to stop hiding numbers. `checked_answers` is serialized on the submission row as a comma-separated list of answer numbers.

---

### Quick Mobile Flow Tables

**Team Player Flow** (applies to all modes unless noted):

| Step | Screen | What Happens |
|------|--------|-------------|
| 1 | `/join?code=XXXX` | QR pre-fills the code. Team taps Submit. |
| 2 | Name entry OR reconnection | If code unused → pick team name. If code used → enter team name to reconnect. |
| 3 | `/play` (waiting) | "Waiting for host to start a round." Polls every 5–10s. |
| 4 | `/play` (active round) | Question, 3–6 answer fields, tiebreaker. Auto-save every keystroke. |
| 5 | Submit | One-shot submission. Live counter on host dashboard. |
| 6 | `/play` (submitted) | Screen depends on `mobile_experience` mode (see above). |
| 7 | Round transition | Winner interstitial → next round form. |
| 8 | `/play` (all rounds done) | Final leaderboard (if advanced mode) or waiting screen (basic). |
| 9 | Game Over | Server restart or Reset All → rejoin link. |

**Mobile-specific nice-to-haves:**
- `mobile_experience` setting controls UI variant
- Landscape lock on some screens (join page only)
- Copy-to-clipboard for team name on dashboard links (for sharing with tablemates)
- Persistent broadcast dismissal via `localStorage` (dismissed banners stay dismissed for that team)

---

## Settings Reference (Every Toggle Explained)

*Everything in `/host/settings`, top to bottom, in the order it appears on the page.*

All settings persist in the SQLite `settings` table — which means they survive until the next server restart, then reset to defaults. If you want a setting to stick permanently, set it as an environment variable (see [Environment Variables](#environment-variables)).

---

### 🎮 Game Controls

#### ✅ Allow New Teams to Join *(toggle)*
- **Default:** ON
- **DB key:** `allow_team_registration`
- **What it does:** When OFF, new teams cannot claim a code — the join page rejects new registrations. Existing teams keep playing. Use this right after the game starts so latecomers can't sneak in.

#### ⏸️ PAUSE GAME / ▶️ RESUME GAME *(toggle button)*
- **Default:** Active (not paused)
- **DB key:** `system_paused`
- **What it does:** Freezes the whole game. While paused, teams cannot join, submit answers, or change anything. Use it for tech crises, emergencies, or when you need the room's attention (pair with a broadcast message). Teams see a pause indicator on their screens.

---

### 📱 Mobile Experience *(dropdown)*
- **Default:** `advanced_no_pp` (Advanced — No PP Display)
- **DB key:** `mobile_experience`
- **Options:**
  - **Basic (`basic`)** — Classic waiting screen after submission. No leaderboard.
  - **Advanced (No PP Display) (`advanced_no_pp`)** — Live leaderboard on team phones; best for games without a TV.
  - **Advanced (PP Display) (`advanced_pp`)** — Live leaderboard with scores hidden until TV reveal; per-answer reveal tracker on the phone. **Requires TV Board (auto-enforced).**
- **Details:** See the [Mobile Phone Game Modes](#mobile-phone-game-modes-deep-dive) section for screen-by-screen behavior of each mode.

---

### 🎨 Color Theme *(dropdown)*
- **Default:** `gamenight` (overrideable via `DEFAULT_THEME` env var)
- **DB key:** `color_theme`
- **Applies instantly** to host dashboard, team phones, and TV board

**Gaming Themes** (8 total, 5 gaming + 3 low-vision):

| Theme Key | Name | Palette |
|---|---|---|
| `classic` | Classic | Royal blue + gold, Arial Black |
| `dark` | Dark | Near-black + cyan, Arial Black |
| `forest` | Forest | Dark green + mustard gold, "Special Elite" typewriter font |
| `stadium` | Stadium | Matte black + crimson red, Barlow Condensed |
| `gamenight` | Game Night | Deep purple + yellow + teal, Lilita One rounded display font |

**Easy-Read Themes** (high-contrast, Verdana, for elderly/low-vision crowds):

| Theme Key | Name | Palette |
|---|---|---|
| `sunny` | Sunny Day | Warm cream + brown + orange |
| `clearsky` | Clear Sky | Pale blue + navy |
| `garden` | Garden | Soft sage + deep green |

> Theme resets to the `DEFAULT_THEME` env var (or `gamenight`) on every server restart. If you always want Stadium, set `DEFAULT_THEME=stadium`.

---

### 📺 TV Board Display *(toggle)*
- **Default:** ON
- **DB key:** `tv_board_enabled`
- **What it does:** Enables the `/tv/board` route and the reveal controls. When OFF, `/host/reveal-control` redirects back to the dashboard with an error flash.
- **Force-locked ON** when `mobile_experience == advanced_pp` (since that mode depends on the TV board firing reveal events).

---

### 🤖 AI Scoring

*Only visible if `ENABLE_AI_SCORING=true` AND at least one API key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`) is set.*

#### 🤖 AI-Assisted Scoring *(toggle)*
- **Default:** ON (when the card is visible)
- **DB key:** `ai_scoring_enabled`
- **What it does:** Controls whether the "Send to AI" button appears on the scoring queue. The toggle lets you flip AI off for a round without pulling API keys.

#### Answer Sheet OCR Model *(dropdown)*
- **DB key:** `ai_ocr_model`
- **Default:** Claude Sonnet 4 if Anthropic configured; GPT-4o if only OpenAI configured
- **Used for:** reading handwritten answer sheets from photos (`/host/scan`)
- **Models available** (only shown if the provider has a key set):
  - **Anthropic:** Claude Sonnet 4, Claude Opus 4, Claude Haiku 4.5
  - **OpenAI:** GPT-5.4, GPT-5.3 Instant, GPT-5.2, GPT-4o, GPT-4o Mini

#### AI Scoring Model *(dropdown)*
- **DB key:** `ai_scoring_model`
- **Default:** GPT-5.4 if OpenAI configured; Claude Sonnet 4 if only Anthropic configured
- **Used for:** semantic matching of team answers → survey answers in the scoring queue
- **Models** — same list as OCR. Different defaults because OCR benefits from Claude's vision, while scoring benefits from GPT-5's reasoning.

**Model cost ballpark** (per scoring call, 1 team × 1 round):

| Model | Approx Cost | Notes |
|---|---|---|
| Claude Haiku 4.5 | ~$0.002 | Fastest & cheapest |
| GPT-5.3 Instant | ~$0.002 | Fast, low hallucination |
| GPT-4o Mini | ~$0.001 | Cheapest OpenAI option |
| GPT-4o | ~$0.005 | Vision + fast |
| Claude Sonnet 4 | ~$0.01 | Balanced quality & cost |
| GPT-5.2 / 5.4 | ~$0.01 | Flagship reasoning |
| Claude Opus 4 | ~$0.05 | Highest quality |

> Scoring a full 8-round game for 15 teams costs roughly $0.12–$6.00 depending on model. Even Opus comes in under your bar tab.

#### 🧠 Extended Thinking *(toggle + budget dropdown)*

*Anthropic Claude models only. Hidden unless a Claude model is selected for OCR or scoring.*

- **DB key:** `extended_thinking_enabled` (bool) + `thinking_budget_tokens` (int)
- **What it does:** Enables Claude's thinking-step reasoning before it answers. Slower and more expensive, but noticeably better on ambiguous/creative answer matching (e.g., deciding whether "trap house" counts as "drug den").
- **Budget options:** 1,024 / 2,048 / 5,000 / 10,000 / 20,000 / 50,000 / 100,000 / 128,000 tokens
  - **1,024** = minimum (barely-there thinking)
  - **10,000** = default (recommended)
  - **128,000** = maximum (overkill unless you're testing)

---

### 🧠 AI Training Data

*Only visible when AI scoring is configured.*

- **💾 Save AI Training to GitHub** — pushes `corrections_history.json` to the configured `GITHUB_REPO` using `GITHUB_TOKEN`. Use at end of night to persist the AI's learned corrections across server restarts. Shows current session's correction count ("N corrections this session").
- **🗑️ Clear Training Data** — wipes the in-memory / local corrections file. Use if the AI has learned a bad habit and you want a clean slate.

> The corrections loop: every time you override the AI's suggestion (accept a match it missed, reject one it got wrong), that correction is appended to `corrections_history.json` and included as context in the next AI call. The AI gradually learns what your pub considers a match.

---

### 📢 Broadcast Message
- **DB key:** `broadcast_message`
- **What it does:** Whatever you type here gets pushed to every team's phone as a blue dismissible banner (200 char max). Auto-broadcasts via `broadcast:message` WebSocket event.
- **📤 Send to All Teams** — sends the current textarea contents.
- **🗑️ Clear Message** — clears the banner (appears on phones as the banner disappearing).

Use it for: break announcements, last-call warnings, "the bathroom in the back is broken," "we're moving to a different survey, disregard round 3," etc.

---

### 💤 Put Server to Sleep
- **No DB key** — uses a runtime flag + client-side behavior
- **What it does:** Stops all client-side auto-refresh timers so Render's free tier can spin the dyno down after 15 minutes. The button on the settings page toggles between Sleep and Wake. After sleep, pages return a "sleeping" status from `/host/get-sleep-status`.
- **Use it:** end of night, when you've stopped actively hosting but don't want to kill the browser.

---

### 🔄 Reset Game *(danger zone)*

Two buttons, increasingly destructive:

- **🔄 RESET GAME** *(keep teams joined)*
  - Deletes all rounds and submissions.
  - Keeps team codes + team names (they stay "joined").
  - Use this for mid-night "let's play a different survey" pivots.
  - Confirmation prompt required.

- **🗑️ RESET EVERYTHING** *(fresh start)*
  - Wipes rounds, submissions, **and** teams + codes.
  - All phones get a "Game Over" screen via `game:reset` WebSocket event (type: `full`).
  - Increments `reset_state['counter']` so any lingering sessions are invalidated on their next request.
  - Use this between games / nights when you don't want to restart the server.
  - Big confirmation prompt.

---

### 🎯 Game Configuration

#### QR Code Base URL
- **Env var override:** `QR_BASE_URL`
- **DB key:** `qr_base_url`
- **Default:** auto-detected from your browser's URL (or `RENDER_EXTERNAL_URL` in production, or `http://localhost:5000` in dev)
- **What it does:** Sets the URL embedded in the QR codes on the printed team cards. Teams scan → get dropped at `{QR_BASE_URL}/join?code=XXXX`.
- **Set it** if you use a custom domain (e.g., `https://pubfeud.gamenightguild.net`) and the auto-detect is guessing wrong.
- **Example:** `https://pubfeud.gamenightguild.net` → QR codes link to `https://pubfeud.gamenightguild.net/join`

---

### Settings NOT on the Settings Page

Some config lives elsewhere or is set at server boot:

| Setting | Where | Default |
|---|---|---|
| Number of rounds (4–12) | Round creation UI | 8 |
| Answers per round (3–6) | Round creation UI | Varies per round; default 4 |
| Host password | `HOST_PASSWORD` env var | `localdev` |
| Log level | `LOG_LEVEL` env var | `INFO` |
| Default theme on boot | `DEFAULT_THEME` env var | `gamenight` |
| GitHub training-save target | `GITHUB_REPO` env var | `teksabian/family-feud` |

---

## Host Tools Reference

### Dashboard (`/host`)
The main control panel. Left column: active round info, answer entry/display, scoreboard. Right column: round list with activate/close buttons, round creation (prebuilt / upload / manual / AI). Below: team code grid with reclaim buttons and print-codes / print-answer-sheets links.

**Key buttons / controls:**
- **Activate** (per round) — sets that round as active, broadcasts to all team phones
- **🔒 End Round & Score** — closes submissions; blocks further submits; unlocks the scoring queue
- **👁️ SHOW ANSWERS / HIDE ANSWERS** — toggles visibility of the correct answers on the host's screen (so you can flip your laptop without spoiling anyone)
- **🔧 Edit** (per answer) — change an answer's text after the fact (e.g., fix a typo)
- **🗑️ Reclaim** (per code) — delete a team's submissions and free the code for reuse
- **TV Remote QR** — passwordless reveal-control link for your phone (uses a rotating `scan_token`)
- **📺 TV Board button** — pop out `/tv/board` in a new window sized 1920×1080

### Scoring Queue (`/host/scoring-queue`)
One team per page. Arrows to navigate. Unscored teams come first. Checkbox list of official answers; tap to mark matches. AI Score button if enabled. Save Score commits + advances.

### Scored Teams (`/host/scored-teams`)
Ranked list of everyone who's been scored for the current round. Undo (→ previous_score field restore) or Edit (→ re-open checkboxes) per row.

### Photo Scan (`/host/scan` and `/host/photo-scan`)
- `/host/scan` is the mobile-optimized shortcut (auto-redirect target after login on mobile devices when AI is on)
- `/host/photo-scan` is the full camera interface
- Supports multi-team page (2×2 grid) OR single-team block
- AI extracts code, team name, 6 answers, tiebreaker, and a list of low-confidence fields
- Low-confidence fields highlighted orange with "CHECK" badge
- Review + edit + Submit → submission lands in scoring queue

### Manual Entry (`/host/manual-entry`)
Dropdown to pick a team code, form fields for answers + tiebreaker, submit → submission in queue. Use for: teams that didn't use paper or phones (e.g., shouted their answers, wrote them on a napkin).

### Print Codes
- `/host/print-codes` — portrait, one code per page
- `/host/print-codes-landscape` — landscape, one code per page, view-only no QR (for display not play)
- Each code sheet has: big 4-letter code, QR image encoding `{QR_BASE_URL}/join?code=XXXX`, and instructions

### Print Answer Sheets
- `/host/print-answer-sheets?group=1` — codes 1-30 (typically the first group you hand out)
- `/host/print-answer-sheets?group=2` — codes 31-60 (if you need more)
- Each page: 2×2 grid of answer blocks with Team Name, Code, Answer 1-6 lines, Tiebreaker #

### Round Edit (`/host/edit-answer/<round_id>/<answer_num>`)
Change an individual answer's text or respondent count after answers are locked in. Rescores any affected submissions.

### Reveal Control (`/host/reveal-control`)
See [TV Board](#the-tv-board-big-screen-reveal) section.

### Login / Token Entry
- `/host/login` — PIN form
- `/reveal/<token>` — passwordless entry (token shown as QR on dashboard; rotates on each server restart)

---

## The TV Board (Big-Screen Reveal)

### The Big Picture
The TV board is an optional **second screen** that runs on a laptop/tablet/Chromecast plugged into a projector or TV. The host controls it from their phone via `/host/reveal-control`. State is in-memory (resets on server restart).

### URLs
| What | URL | Auth |
|---|---|---|
| TV display (projector) | `/tv/board` | None — full-screen, no login |
| Host reveal control | `/host/reveal-control` | Host session required |
| Passwordless reveal login | `/reveal/<scan_token>` | Token from dashboard QR |

### Screens You Can Switch To
Each button on the reveal control sets `tv_state` and broadcasts `tv:state_update` to the TV display:

| Screen | Purpose |
|---|---|
| **Welcome** | Pre-game logo/title card |
| **Rules** | Quick house rules recap |
| **Question** | Current round's question, huge text |
| **Board** | Answer grid, tiles start hidden |
| **Halftime** | Break screen |
| **Closing** | End-of-night screen |

### Board Screen Interactions
- Tiles render as **blue (hidden)** showing "#N" and "N pts" until revealed
- Tap a tile on your phone's reveal control → flips to **gold (revealed)** showing answer text + respondent count
- Flip is a 0.6s 3D rotation (peak pub-trivia theatrics)
- **"And The Survey Says..."** — 3-2-1 countdown animation → auto-reveals #1
- **Reveal All** — cascades remaining tiles open at ~1s intervals
- Once all tiles are revealed, `scores_revealed` flips on; TV switches to a leaderboard view, and `advanced_pp` mobile phones unhide their score numbers with a pop animation

### WebSocket Events Used
- `tv:state_update` — active screen changed (Welcome/Rules/Question/Board/…)
- `tv:reveal` — specific answer tile revealed
- `leaderboard:scores_revealed` — all answers revealed, scores unlocked
- `leaderboard:update` — any score changed, leaderboard re-sorted

---

## Surveys & Content

### Prebuilt Surveys
**10 complete surveys** are baked in (hard-coded in `routes/host/rounds.py` as `PREBUILT_SURVEYS`). Each has 8 rounds, ~80 questions total. Pick from the dropdown on the dashboard, one click loads the whole game. Contents are all classic pub-trivia survey fare: "Name something people keep in their junk drawer," "Name something parents warn their kids not to get their fingers caught in," etc.

### Upload a Survey File
Upload `.docx`, `.pptx`, or `.pptm` from the dashboard. The parser (`parsers.py`) extracts questions + ranked answers + optional counts and creates all rounds at once. **Uploading replaces existing rounds** (fresh start per upload).

**Expected file structure** (either DOCX or PPTX):
- One question per round with numbered ranked answers
- See files in `/surveys/` directory (1.docx through 10.docx) for concrete examples
- Each file represents one night's set of 8 rounds

### Manual Round Creation
From the dashboard, create rounds one at a time. Set:
- Round number (1–8 by default, up to 12)
- Number of answers (3–6)
- Answer text for each rank
- Optional respondent count for #1 answer (shown on the board as "(45 people)")

### AI-Generated Rounds
If AI keys are configured, the dashboard shows an **"AI Generate"** option. The AI writes:
1. N questions using `FEUD_QUESTIONS_PROMPT` — starts with "Name something…", "Tell me…", etc.
2. Ranked answers per question using `FEUD_ANSWERS_PROMPT` — points sum to ~93-97 (realistic survey distribution where not every respondent's answer makes the board)

Uses the AI generation model (separate from scoring/OCR models). Cost is similar to a scoring call per round.

### Points Math (Important)
Points are **derived from rank position**, NOT from respondent count:
- #1 answer = `num_answers` points
- #2 answer = `num_answers - 1` points
- …
- Last answer = 1 point

**Example:** 5-answer round, team matches answers #1 and #3 → 5 + 3 = **8 points**.

The per-answer respondent counts are for flavor (displayed on the TV board and host dashboard). They do not affect scoring.

### Access Codes
- 4-letter codes, loaded from `codes.json`
- Allowed letters: **A B E F H J K M N P R S T W X Y Z** (17 letters)
- Excluded letters: **C D G I L O Q U V** (easily confused with numbers, other letters, or handwriting)
- Examples: HBKM, PRTX, BANJ, JHWK
- Max ~60 codes available by default

---

## Environment Variables

Set in Render dashboard (production) or in a local `.env` file (development).

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SECRET_KEY` | Yes (Render auto-generates) | Random token | Flask session signing |
| `HOST_PASSWORD` | Yes | `localdev` *(dev only — change for prod!)* | Host dashboard PIN |
| `RENDER` | Cloud only | unset | Enables cloud mode (stdout logging, URL detection) |
| `RENDER_EXTERNAL_URL` | Cloud only | `https://pubfeud.gamenightguild.net` | Render sets this; used as QR default |
| `QR_BASE_URL` | No | auto-detect | Override QR base domain |
| `ANTHROPIC_API_KEY` | No | unset | Anthropic Claude API key |
| `OPENAI_API_KEY` | No | unset | OpenAI API key |
| `ENABLE_AI_SCORING` | No | `false` | Must be `true` to activate AI scoring |
| `AI_MODEL` | No | unset | Legacy fallback AI model override |
| `AI_SCORING_MODEL` | No | auto | Override the model used for scoring |
| `AI_OCR_MODEL` | No | auto | Override the model used for photo OCR |
| `GITHUB_TOKEN` | No | unset | Sync AI corrections to a GitHub repo |
| `GITHUB_REPO` | No | `teksabian/family-feud` | Target repo for training saves |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` for verbose, `WARNING` for quiet |
| `DEFAULT_THEME` | No | `gamenight` | Color theme to use on each restart (one of: classic, dark, forest, stadium, gamenight, sunny, clearsky, garden) |
| `PORT` | Cloud only | `10000` | Gunicorn bind port (Render sets this) |

> **AI Scoring requires** `ENABLE_AI_SCORING=true` **AND** at least one API key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`). Both can be set — pick your model from the settings dropdown.

---

## Cloud Deployment (Render.com)

### Prerequisites
- GitHub account
- Render.com account (free tier works; $7/mo Starter recommended)
- Optional: custom domain (e.g., pubfeud.gamenightguild.net)

### Deploy Steps

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/survey-says.git
   git push -u origin main
   ```

2. **Create Render App**
   - [dashboard.render.com](https://dashboard.render.com) → New → Web Service
   - Connect your GitHub repo
   - Render auto-detects `render.yaml`
   - Click Create Web Service

3. **Configure Environment Variables**
   - In Render dashboard → Environment → Add
   - Set `HOST_PASSWORD` (required — strong password!)
   - Set `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY` if using AI
   - Set `ENABLE_AI_SCORING=true` if using AI
   - Optionally set `DEFAULT_THEME`, `LOG_LEVEL`, `GITHUB_TOKEN`

4. **Custom Domain** *(optional)*
   - Render dashboard → your app → Settings → Custom Domain
   - Add your domain → Render provisions SSL automatically
   - Set DNS CNAME: `your-subdomain` → `your-app.onrender.com`
   - 10–60 min propagation

5. **Single Worker Constraint — IMPORTANT**
   - `render.yaml` pins the start command to `--workers 1` via the `GeventWebSocketWorker`
   - Do not increase workers. `STARTUP_ID`, `reset_state`, SQLite, and session invalidation all require a single worker process
   - Scale up = horizontal, not vertical; but single-venue usage never needs it

### Deploy = Restart = Wipe
Pushing to GitHub triggers a Render deploy, which restarts the server, which wipes the database. Perfect for weekly pub nights; less perfect mid-game. Plan deploys accordingly.

### Free Tier Sleep
Render's free tier apps sleep after 15 min of inactivity. First team to hit the join page when the server is asleep will see a 30-60s cold start. The $7/mo Starter tier removes this (recommended for regular hosting).

---

## Architecture Notes

### Nuclear Reset (Scorched Earth Policy)
Every time the server starts, the database is wiped completely: submissions, rounds, team names, sessions — all of it. Teams that were connected receive a polite message asking them to rejoin. The data does not get a polite message.

On Render, every deploy triggers a server restart, which triggers the wipe. This makes weekly pub nights trivially simple: deploy before the event, and you have a fresh game. No cleanup scripts, no stale team names from last month.

A **Reset All** button in the host dashboard performs the same wipe without a server restart, for mid-night resets.

Two runtime values gate session validity:
- **`STARTUP_ID`** — unique timestamp generated at boot; baked into every client session; any mismatch = invalid session
- **`reset_state['counter']`** — incremented on every Reset All; clients comparing an older counter are kicked

Full details: [docs/architecture/NUCLEAR_RESET.md](docs/architecture/NUCLEAR_RESET.md)

### Real-Time Layer
- Flask-SocketIO + gevent-websocket
- Single-worker Gunicorn (required for in-memory state + SQLite)
- Fallback polling via `/api/check-round-status` and `/api/leaderboard` in case WebSockets get blocked by corporate WiFi or flaky hotspots
- Heartbeat every 30s keeps the host's "online" dots accurate

### Blueprints / Module Layout
| Module | File | Purpose |
|---|---|---|
| `auth` | `auth.py` | Host login, session decorators |
| `host` | `routes/host/__init__.py` + submodules | Host blueprint registration and shared constants |
| `host.dashboard` | `routes/host/dashboard.py` | Main dashboard, settings, sleep mode |
| `host.rounds` | `routes/host/rounds.py` | Create, activate, close, upload, edit rounds |
| `host.codes` | `routes/host/codes.py` | Code generation, QR print, reclaim |
| `host.broadcast` | `routes/host/broadcast.py` | Broadcast messages, reset / reset-all |
| `host.training` | `routes/host/training.py` | Save/clear AI training corrections |
| `team` | `routes/team.py` | Team join, submit, play |
| `scoring` | `routes/scoring.py` | Scoring queue, AI scoring, photo scan, manual entry |
| `api` | `routes/api.py` | JSON endpoints (polling fallback) |
| `tv` | `routes/tv.py` | TV board + reveal control |
| `sockets` | `sockets.py` | WebSocket event handlers |
| `database` | `database.py` | SQLite connection + schema + settings helpers |
| `ai` | `ai.py` | Anthropic / OpenAI clients, prompts, corrections |
| `parsers` | `parsers.py` | DOCX / PPTX parsing for round upload |
| `config` | `config.py` | Env vars, constants, theme definitions, prompts |
| `tv_state` | `tv_state.py` | In-memory TV reveal state |
| `survey_history` | `survey_history.py` | Past-question tracking for AI generation |

### Database Schema (abridged)
- **`team_codes`** — code, used, team_name, reconnected, last_heartbeat
- **`rounds`** — round_number, question, num_answers, answer1–6, answer1_count–6, is_active, submissions_closed, winner_code
- **`submissions`** — team_code, team_name, round_id, answer1–6, tiebreaker, score, previous_score, checked_answers, host_submitted
- **`settings`** — key/value store for all the toggles above
- **`ai_corrections`** — training memory (also mirrored to `corrections_history.json`)

### AI Scoring Pipeline
1. Team submits → stored in `submissions`
2. Host taps AI Score → `ai.score_with_ai()` builds a prompt with: question, survey answers, team answers, corrections history
3. Call goes to Claude or GPT (based on `ai_scoring_model`)
4. AI returns JSON: matched answer numbers + brief reasoning
5. Matches pre-check on the scoring UI; host reviews and adjusts
6. Save → any diff between AI and host is appended to `corrections_history.json`
7. Next call includes recent corrections as few-shot context

### Photo Scan Pipeline
1. Host takes photo → image posted to `/host/photo-scan-submit`
2. `ai.extract_from_photo()` sends image + `PHOTO_SCAN_PROMPT` to configured OCR model
3. AI returns JSON with code, team name, 6 answers, tiebreaker, low-confidence field list
4. Review UI highlights low-confidence fields orange
5. Host submits → rows inserted into `submissions` table, ready for scoring

Full details:
- [docs/features/AI_SCORING.md](docs/features/AI_SCORING.md)
- [docs/features/MOBILE_EXPERIENCE.md](docs/features/MOBILE_EXPERIENCE.md)

---

## Security

- ✅ Host routes protected by PIN (`@host_required` decorator checks `session['host_authenticated']`)
- ✅ SQL injection prevention (parameterized queries throughout)
- ✅ XSS protection (template escaping, `textContent` not `innerHTML` in all dynamic JS rendering)
- ✅ Session security (Flask signed cookies, random `SECRET_KEY` in prod)
- ✅ HTTPS on Render (free SSL)
- ✅ Passwordless reveal uses `secrets.compare_digest` (constant-time comparison) against a `secrets.token_urlsafe(16)` token that rotates on each restart
- ✅ Unambiguous team codes (restricted letter set prevents OCR/handwriting confusion)
- ✅ Code reclaim requires host auth; teams cannot force-take another team's code without knowing the team name

See [docs/security/SECURITY_PATCHES.md](docs/security/SECURITY_PATCHES.md) for the full audit history.

---

## Testing

Comprehensive test suite organized by planetary severity:

- **Mars (Security)** — XSS injection, SQL injection, auth bypass attempts
- **Venus (Stress)** — Concurrent submissions, API polling under load
- **Jupiter (Destruction)** — Race conditions, edge cases, data integrity under chaos
- **Oort Cloud (Limits)** — Unicode, NULL values, boundary conditions at the theoretical edge of acceptable input *(if it survives the Oort Cloud suite, it will survive your pub)*

Plus v1.1.0 feature-level tests for reconnect, reclaim, timestamp handling, heartbeat, and score undo. Plus AI feature tests for extended thinking and photo capture.

```bash
# Run all tests
python -m unittest discover tests/

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

## Troubleshooting

### Teams see "Game Over" on first join
The server was just restarted. Expected behavior — have them rejoin. Nuclear reset by design.

### AI scoring button missing from scoring queue
Check three things: `ENABLE_AI_SCORING=true`, at least one API key configured, **and** the AI Scoring toggle is ON in `/host/settings`. All three required.

### TV board shows nothing / blank
Check `tv_board_enabled` is ON in settings. If using `advanced_pp` mobile mode, it should be force-enabled. Refresh `/tv/board` — it reconnects to the current in-memory state.

### Photo scan extracted the wrong team code
Check two things: the code was written in the top-right corner (not on the Team Name line), and it uses only the allowed 17 letters. Handwritten 0s often get read as Os but the allowed letter set excludes O, so it'll usually snap to the closest valid letter.

### First team to join after idle sees a long hang
Render free-tier cold start (30–60s). Upgrade to Starter ($7/mo) or tell them to wait.

### Broadcast banner won't go away
Each team dismisses independently (localStorage). Sending a NEW broadcast replaces the message for everyone. Clearing the message (`🗑️ Clear Message`) hides the banner for all teams whose page hasn't been dismissed yet.

### "Reset All" didn't kick everyone
Make sure only one Gunicorn worker is running (`--workers 1` in `render.yaml`'s start command). Reset All increments an in-memory counter; extra workers don't see the increment.

### Logs
- Local: `/logs/<timestamp>.log`
- Render: dashboard → Logs tab
- `LOG_LEVEL=DEBUG` for verbose tracing

---

## Tech Stack, Cost, Credits, License

### Tech Stack
| Component | Technology |
|---|---|
| **Backend** | Flask 3.1.2 |
| **Real-time** | Flask-SocketIO + gevent-websocket |
| **Database** | SQLite (ephemeral) |
| **Production server** | Gunicorn (1 worker, GeventWebSocketWorker) |
| **Frontend** | Vanilla JS + HTML/CSS *(no framework, no build step)* |
| **QR Codes** | qrcode + Pillow |
| **Document parsing** | python-docx + python-pptx |
| **AI Scoring/OCR** | anthropic ≥ 0.55.0 / openai ≥ 1.30.0 *(one or both)* |
| **Deployment** | Render.com |

### Cost
| Item | Cost |
|---|---|
| Render Free Tier | $0/mo *(sleeps after 15 min)* |
| Render Starter Tier | $7/mo *(always on — recommended)* |
| AI Scoring (Anthropic or OpenAI) | ~$0.001–$0.05 per scoring call (depends on model) |
| SQLite / ephemeral DB | Free *(the database deletes itself, saving you money and therapy)* |

A typical 8-round night with 15 teams and mid-tier AI models costs under $2 in API calls. Opus + extended thinking can push to $10. Host a big tournament every month and you might actually hit a meaningful bill; a weekly pub night won't.

### Documentation
- [Changelog](docs/CHANGELOG.md) — Full version history
- [AI Scoring](docs/features/AI_SCORING.md) — Setup, usage, training loop
- [Mobile Experience](docs/features/MOBILE_EXPERIENCE.md) — Mobile optimizations and photo scan
- [Nuclear Reset](docs/architecture/NUCLEAR_RESET.md) — Server startup reset behavior explained
- [Render Deployment](docs/deployment/RENDER_DEPLOYMENT.md) — Cloud deployment guide
- [Security Patches](docs/security/SECURITY_PATCHES.md) — Security audit history

### Support
If something's broken:
1. Check the logs (`/logs/` locally, Render dashboard in prod)
2. Run the test suite — planetary names tell you which layer failed
3. Check GitHub issues

### Credits
Built for weekly pub trivia nights at Game Night Guild local venues.

Powered by Flask, Gunicorn, and a determination to avoid spreadsheets.

AI scoring powered by Claude (Anthropic) and GPT (OpenAI) — who also wrote parts of the test suite and therefore have some skin in the game.

Ten prebuilt surveys included so you don't have to spend Friday afternoon writing trivia questions.

If something breaks mid-game, the audience is usually distracted by their drinks.

### License
Private use for Game Night Guild pub trivia events.

---

**v4.1.0 — Plasma** | Battle-tested at actual pub nights | Survey SAYS: production ready. 🍻

