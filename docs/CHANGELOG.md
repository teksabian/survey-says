# Changelog

All notable changes to Family Feud (Pub Feud) are documented here. Reverse chronological order.

---

## v4.1.0 - Plasma (Mar 10, 2026)
- AI-powered round generation with survey totals summing to 93-97
- Compressed host dashboard UI for less wasted space
- Removed redundant Settings buttons

## v4.0.0 - Plasma (Mar 7, 2026)
- Separate AI scoring from host submission with new `host_submitted` column
- AI auto-scored submissions keep SUBMIT button enabled for host review
- Dashboard notification counter reflects host-unsubmitted count (not AI-scored count)
- Server-side auto-scoring retries up to 3 times with exponential backoff on failure
- WebSocket `scoring:submission_scored` event updates scoring queue in-place for real-time updates
- Client-side auto-AI scoring retries after 5s for any panels that failed first pass
- Winner determination only triggers when host has submitted all teams

## v3.2.0 - Fission (Mar 5, 2026)
- Add "What AI Accepted This Round" collapsible panel on Scored Teams page
- Panel shows fringe/synonym answers the AI accepted per survey answer slot (e.g., "truck" for "car")
- Smart misspelling filter: 3-check heuristic (sequential similarity, character-bag composition, substring containment) excludes typos and only shows true synonyms
- New GET /host/ai-accepted-summary endpoint aggregates AI reasoning data from scored submissions
- Data lazy-loads on first panel expand; re-toggling does not re-fetch

## v3.1.0 - Fission (Mar 3, 2026)
- Add OpenAI models as alternative AI provider (GPT-5.2, GPT-4o, GPT-4o-mini)
- Host can pick between Anthropic Claude and OpenAI GPT models from settings dropdown
- Models grouped by provider in settings UI with `<optgroup>` labels
- Extended Thinking toggle hidden when OpenAI model selected (Anthropic-only feature)
- AI scoring and photo OCR work with either provider — same prompts, same UI
- Only models whose provider API key is configured appear in the dropdown

## v3.0.1 - Fission (Feb 28, 2026)
- Fix scanner to auto-advance when host activates next round (no more manual refresh)
- Show waiting screen on phone scanner when no active round instead of error toast
- Enhance check-active-round endpoint to return round details for polling

## v2.0.5 - Photo Scan (Feb 15, 2026)
- Add photo scan: snap paper answer sheets from phone camera, auto-submit to scoring queue
- Add team registration page; clean up dashboard for photo scan workflow
- Add `/host/scan` shortcut URL for mobile hosts
- Root URL now redirects to `/join` instead of `/host`
- Remove ambiguous letters from code generation; add fuzzy code matching

## v2.0.4 - Host Notes & AI Training Persistence (Feb 15, 2026)
- Add host notes to AI corrections — teach AI your scoring philosophy
- Persist corrections to JSON file with GitHub sync for long-term AI training

## v2.0.3 - AI Scoring Training (Feb 14, 2026)
- Add AI scoring training: corrections feedback loop so AI learns from host overrides
- Scoring queue redesign: layout reorder, per-answer AI feedback, button cleanup

## v2.0.2 - AI Scoring Reasoning (Feb 13, 2026)
- Add AI scoring reasoning display: shows why AI matched each answer
- Remove auto-check from scoring queue; all checkboxes unchecked by default

## v2.0.1 - AI-Assisted Scoring (Feb 12, 2026)
- Introduce AI-assisted scoring powered by Claude API
- Fix Vision prompt: code and team name are separate fields

## v2.0.0 "Fusion" (Feb 12, 2026)
- Merge v1.x Nuclear line with v2 AI features on main branch
- Set version to v2.0.0

## v1.2.2 - Verbose Logging (Feb 12, 2026)
- Add maximum verbose logging across backend and frontend
- Rename "Manual Scoring" to "Scoring"; fix settings.html JS bug; remove unused imports

## v1.2.1 - Background Tab Reset Detection (Feb 12, 2026)
- Fix background browser tabs not detecting game reset
- Player post-submit UX: persistent answer display + winner interstitial

## v1.2.0 - Dedup & Cache Busting (Feb 12, 2026)
- Deduplicate rejoin logic for returning players
- Add cache busting for Render deploys to prevent stale assets

## v1.1.3 - Environment Variable Password (Feb 12, 2026)
- Replace hardcoded host PIN with `HOST_PASSWORD` environment variable

## v1.1.2 - Rejoin & Heartbeat Fixes (Feb 11, 2026)
- Fix team rejoin 500 error, reset-kick logic, status dots, faster heartbeat

## v1.1.1 - Bug Fixes & Connection Status (Feb 11, 2026)
- Bug fixes and code connection status indicators for teams

## v1.1.0 - Major Bug Fixes (Feb 11, 2026)
- Major round of stability and reliability fixes from live pub testing

## v1.0.6 - Nuclear Bug Fixes (Feb 11, 2026)
- Fix "Reset All" not invalidating phone sessions (added RESET_COUNTER + Game Over page)
- Fix "Put Server to Sleep" not stopping phone polling (server-side sleep flag)
- Simplify QR Base URL settings for Render hosting

## v1.0.5 - Security Patch (Feb 11, 2026)
- Patch stored XSS vulnerability in toast notifications (innerHTML → textContent)
- Fix ghost team sessions after reset (game_id epoch system)
- Add nuclear reset on server startup (STARTUP_ID invalidation)

## v1.0.4.1 - Hotfix (Feb 11, 2026)
- Fix missing tiebreaker explanation text on manual entry page

## v1.0.4 (Round 5) - Auto-Save & Idle Check (Feb 11, 2026)
- Add answer auto-save via localStorage (debounced 500ms)
- Add "Are you still there?" idle check after 30 minutes
- Complete all 17 originally-planned features

## v1.0.3 (Round 4) - Polish & Fixes (Feb 11, 2026)
- Fix case-sensitive duplicate team name check (now case-insensitive)
- Add score edit history with previous score display and undo
- Add upload error feedback with loading spinners

## v1.0.2 (Round 3) - Broadcast & UI Polish (Feb 10, 2026)
- Fix broadcast persistence: dismiss persists across page transitions via localStorage
- Move "SHOW ANSWERS" button to host dashboard toolbar

## v1.0.1 (Round 2) - Critical Hotfixes (Feb 10, 2026)
- Fix PowerPoint upload missing `pptx` module (auto-install dependencies)
- Fix Sleep Server not waking up (toggle button behavior)
- Fix broadcast only showing on answer page (now on all player pages)
- Fix scoring queue broken by modal popup (replaced with toggle reveal)

## v1.0.0 (Round 1) - UI/UX Overhaul (Feb 10, 2026)
- Host login page redesign (bigger logo, "Pub Family Feud" title)
- Settings page reorganization with sleep server button
- Add broadcast dismiss, connection status indicator, mobile answer validation
- Add 30-char team name limit, duplicate name prevention, confirmation dialogs
- Per-team "View Answer" on scoring queue

## Pre-v1: V3.9.9.2 - UI Improvements (Feb 9, 2026)
- Add auto-refresh polling (5s) on team play page
- Skip empty scoring queue; go straight to winner announcement
- Auto-fill team name in manual entry when code selected

## Pre-v1: V3.9.9.1 - Critical Security Patch (Feb 9, 2026)
- Fix Flask decorator ordering bug leaving 30 host routes unprotected
- All host panel routes now properly require PIN authentication

## Pre-v1: V3.9.9 - 7 Critical Bug Fixes (Feb 8, 2026)
- Fix multiple active rounds, race condition on activation, out-of-order activation
- Fix duplicate submissions from WiFi drops
- Fix QR codes: remove auto-fill, add port number to URL

## Pre-v1: V3.1 - Tied Score & Mobile Fixes (Feb 8, 2026)
- Fix white screen on tied scores (Jinja2 abs() filter workaround)
- Fix team code order jumping every 10 seconds
- Fix mobile question text cutting off submit button

## Pre-v1: V3 - Host Dashboard Upgrades (Feb 7, 2026)
- Host dashboard header redesign with logo
- Combined "Create Rounds" box (manual OR upload)
- Team codes auto-refresh every 10 seconds with animations

## Pre-v1: V2 - Logging & Branding (Feb 7, 2026)
- Fix round summary crash on tied scores (NULL tiebreaker handling)
- Add comprehensive logging system with timestamped files
- Join page branding: Game Night Guild logo, updated instructions

## Pre-v1: V1 - Core Feature Complete (Early Feb 2026)
- Two paths to create rounds: manual form or DOCX upload
- Manual entry for paper team submissions
- Auto-generate 25 team codes on startup
- Round summary with tiebreaker and "Start Next Round"
- Mobile-optimized team experience

## Pre-v1: V0 - Foundation (Early Feb 2026)
- Core 8-round Family Feud game engine (Flask + SQLite)
- Team code system, DOCX answer sheet upload, manual scoring
- Host dashboard with round management, scoring queue, leaderboard
