# Security Patches & Audit History

This document consolidates all security-related fixes and testing performed on Survey Says.

---

## 1. Stored XSS in Toast Notifications (v1.0.5)

**Severity:** Critical
**Discovered by:** ChatGPT QA Testing (Feb 11, 2026)

**Vulnerability:** Toast notification system used `innerHTML` to display messages containing user-supplied team names. A malicious team name like `<img src=x onerror=alert(1)>` would execute JavaScript on the host screen.

**Impact:** Attacker could steal host session, spam controls, or break the game.

**Fix:** Replaced all `innerHTML` usage with safe DOM building using `textContent`, which treats all content as plain text. Applied to `_toast.html`, `host.html`, and `play.html`.

---

## 2. Ghost Team Sessions After Reset (v1.0.5)

**Severity:** Critical
**Discovered by:** ChatGPT QA Testing (Feb 11, 2026)

**Vulnerability:** "Reset All" cleared the database but not user sessions. Old phones still had valid sessions, causing code collisions when new teams joined with the same codes.

**Fix:** Added game_id epoch system — each "Reset All" increments a counter. The `team_session_valid` decorator checks session game_id against current game_id. Mismatch = session cleared, redirect to join page. Later replaced by STARTUP_ID system (nuclear reset on every server restart).

---

## 3. Flask Decorator Auth Bypass (V3.9.9.1)

**Severity:** Critical (Emergency Patch)
**Discovered by:** QA Testing (Feb 9, 2026)

**Vulnerability:** All 30 host panel routes were accessible without PIN authentication due to Flask decorator ordering bug. `@host_required` was placed above `@app.route`, but Flask processes decorators bottom-to-top, so it registered the unprotected function.

**Impact:** Any team member on the WiFi could reset the game, manipulate scores, view all codes, or close rounds.

**Fix:** Corrected decorator order on all 30 routes — `@app.route` on top, `@host_required` below. Also added missing auth decorator to `/host/print-codes-landscape`.

**Routes fixed:** `/host`, `/host/reset-all`, `/host/reset`, `/host/close-round`, `/host/scoring-queue`, `/host/score-team/<id>`, `/host/codes-status`, `/host/generate-codes`, `/host/toggle-setting`, `/host/settings`, `/host/print-codes`, `/host/print-codes-landscape`, `/host/upload-answers`, `/host/round/create`, `/host/round/<id>/activate`, `/host/round/<id>/answers`, `/host/round/<id>/edit-answer`, `/host/round/<id>/delete`, `/host/round/<id>/close-round`, `/host/round/<id>/next-round`, `/host/check-active-round`, `/host/count-unscored`, `/host/round-summary`, `/host/edit-score/<id>`, `/host/broadcast`, `/host/clear-broadcast`, `/host/manual-entry`, `/host/score-and-next`, `/host/round-complete`, `/host/create-round-manual`.

---

## 4. Mars Mode Adversarial Testing (V3.9.7)

**Test Date:** February 8, 2026
**Approach:** Adversarial/chaos testing — SQL injection, XSS, boundary conditions, race conditions, database corruption, broadcast abuse.

### Results: 15 issues found (3 critical, 7 warnings, 5 info)

**Critical findings:**
1. **XSS in broadcast messages** — Host could inject `<script>` tags displayed on all team phones. Fixed with `html.escape()` on input.
2. **Orphaned submissions crash leaderboard** — Deleting a team after submission caused NULL errors. Fixed with NULL checks in templates.
3. **Missing answer column safety** — Rounds with fewer answers caused NULL errors in scoring. Fixed with `.get()` and NULL checks.

**Warning findings:**
- Empty team names allowed (fixed: added validation)
- Extreme tiebreaker values accepted (fixed: limited to 0-100)
- 10,000 character broadcast messages break mobile UI (fixed: 200 char limit)
- Paused + registration enabled simultaneously (fixed: auto-disable registration on pause)

**What passed cleanly:**
- SQL injection: All blocked by parameterized queries
- Duplicate codes: Blocked by UNIQUE constraints
- Unicode/emoji support: Excellent
- Case-sensitive codes: Working correctly
- Tiebreaker sorting: Accurate

**Security grade:** B+ (A after fixes applied)

---

## Current Security Posture

**Protected against:**
- SQL injection (parameterized queries throughout)
- XSS (textContent for user data, html.escape for broadcast)
- Session hijacking (STARTUP_ID invalidation on restart, game_id epochs on reset)
- Unauthorized host access (decorator ordering verified on all 30 routes)
- Input abuse (length limits, validation, type checking)

**Architecture:**
- PIN-protected host panel via `HOST_PASSWORD` environment variable
- Nuclear reset on every server restart — no data persists
- STARTUP_ID session invalidation catches stale sessions
- All team routes validated via `team_session_valid` decorator
