"""
Team-facing routes for Family Feud.

Owns: join flow (code validation, team name submission, reconnection),
play page, answer submission, view page, and terms page.
"""

import sqlite3
from flask import Blueprint, request, render_template, redirect, url_for, session, flash

from config import logger, STARTUP_ID, reset_state
from auth import team_session_valid
from database import db_connect, get_setting

team_bp = Blueprint('team', __name__)


# ============= JOIN ROUTES =============

@team_bp.route('/join')
def join():
    """Team join page - step 1"""
    paused = get_setting('system_paused', 'false') == 'true'
    reg_closed = get_setting('allow_team_registration', 'true') == 'false'
    logger.debug(f"[TEAM] join() page loaded | paused={paused}, registration_closed={reg_closed}")
    # Check if system is paused
    if paused:
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")

    # Check if team registration is allowed
    if reg_closed:
        return render_template('join.html', error="🚫 Team registration is currently closed.")

    # Support ?code= query param to pre-fill code from QR scan
    prefill_code = request.args.get('code', '').strip().upper()
    return render_template('join.html', prefill_code=prefill_code)


@team_bp.route('/terms')
def terms():
    """Terms and conditions page"""
    return render_template('terms.html')


@team_bp.route('/join/validate-code', methods=['POST'])
def validate_code():
    """Step 1: Validate team code"""
    logger.debug(f"[TEAM] validate_code() - code='{request.form.get('code', '').strip().upper()}'")
    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")

    # Check if team registration is allowed
    if get_setting('allow_team_registration', 'true') == 'false':
        return render_template('join.html', error="🚫 Team registration is currently closed.")

    code = request.form.get('code', '').strip().upper()

    if not code:
        return render_template('join.html', error="Please enter a code")

    with db_connect() as conn:
        code_row = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()

        if not code_row:
            logger.warning(f"[TEAM] validate_code() - code '{code}' not found in database")
            return render_template('join.html', error="Invalid code. Check your code and try again.")

        if code_row['used']:
            logger.info(f"[TEAM] validate_code() - code '{code}' already used by '{code_row['team_name']}', showing reconnect form")
            # Code is in use - show reconnection form
            return render_template('join.html', code=code, show_reconnect_form=True, existing_team=code_row['team_name'])

    logger.info(f"[TEAM] validate_code() - code '{code}' is valid and unused, showing team name form")
    return render_template('join.html', code=code, show_team_form=True)


def _rejoin_team(conn, code, code_row, source="REJOIN"):
    """Shared rejoin logic for both join_submit and join_reconnect routes.

    Handles: DB update (reconnected flag, heartbeat), session creation, redirect.
    Called AFTER validation has already confirmed the code is used and team name matches.

    Args:
        conn: Active database connection
        code: Team code (uppercase)
        code_row: Database row for the team code
        source: Log label ("REJOIN" or "RECONNECT") for distinguishing routes in logs

    Returns:
        Flask redirect to team_play
    """
    original_name = code_row['team_name']  # Always use DB capitalization

    logger.debug(f"[TEAM] {source}: Team '{original_name}' rejoining with code {code}")

    # Mark as reconnected + refresh heartbeat
    conn.execute(
        "UPDATE team_codes SET reconnected = 1, last_heartbeat = CURRENT_TIMESTAMP WHERE code = ?",
        (code,)
    )
    conn.commit()

    # Create session with current server state
    session['code'] = code
    session['team_name'] = original_name
    session['startup_id'] = STARTUP_ID
    session['reset_counter'] = reset_state['counter']

    logger.info(f"[TEAM] {source}: Session created for '{original_name}' (Code: {code}), redirecting to team_play")
    return redirect(url_for('team.team_play'))


@team_bp.route('/join/reconnect', methods=['POST'])
def join_reconnect():
    """Reconnect with existing team code"""
    logger.debug("[TEAM] RECONNECT: Attempt started")

    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        logger.info(f"[TEAM] RECONNECT: Blocked - system paused")
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")

    code = request.form.get('code', '').strip().upper()
    team_name = request.form.get('team_name', '').strip()

    logger.debug(f"[TEAM] RECONNECT: code='{code}', team_name='{team_name}'")

    if not code or not team_name:
        logger.warning(f"[TEAM] RECONNECT: Missing code or team_name")
        return render_template('join.html', error="Please enter both code and team name")

    with db_connect() as conn:
        code_row = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()

        if not code_row:
            logger.warning(f"[TEAM] RECONNECT: Code '{code}' not found in database")
            return render_template('join.html', error="Invalid code")

        logger.debug(f"[TEAM] RECONNECT: Code found - used={code_row['used']}, team_name='{code_row['team_name']}'")

        if not code_row['used']:
            logger.warning(f"[TEAM] RECONNECT: Code '{code}' not yet used, rejecting reconnect")
            return render_template('join.html', error="This code hasn't been used yet. Use regular join.")

        # Case-insensitive team name comparison
        if code_row['team_name'].lower() != team_name.lower():
            logger.warning(f"[TEAM] RECONNECT: Name mismatch - DB='{code_row['team_name']}', submitted='{team_name}'")
            return render_template('join.html',
                code=code,
                show_reconnect_form=True,
                existing_team=code_row['team_name'],
                error="❌ Team name doesn't match. This code belongs to another team. Get a new code from the host.")

        # Validation passed - use shared rejoin logic
        return _rejoin_team(conn, code, code_row, source="RECONNECT")


@team_bp.route('/join/submit', methods=['POST'])
def join_submit():
    """Step 2: Submit team name"""
    code_val = request.form.get('code', '').strip().upper()
    team_val = request.form.get('team_name', '').strip()
    logger.debug(f"[TEAM] join_submit() - code='{code_val}', team_name='{team_val}'")
    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")

    # Check if team registration is allowed
    if get_setting('allow_team_registration', 'true') == 'false':
        return render_template('join.html', error="🚫 Team registration is currently closed.")

    code = request.form.get('code', '').strip().upper()
    team_name = request.form.get('team_name', '').strip()

    # Validation: Check for empty code or team name
    if not code or not team_name:
        return render_template('join.html', code=code, error="Please enter both code and team name")

    # Validation: Check for whitespace-only team name
    if len(team_name.strip()) == 0:
        return render_template('join.html', code=code, error="Team name cannot be empty or just spaces")

    # Validation: Team name character limit (30 chars max)
    if len(team_name) > 30:
        return render_template('join.html', code=code, error="Team name too long! Maximum 30 characters.")

    with db_connect() as conn:
        # Validation: Check for duplicate team names (case-insensitive)
        existing_team = conn.execute(
            "SELECT team_name FROM team_codes WHERE LOWER(team_name) = LOWER(?) AND used = 1 AND code != ?",
            (team_name, code)
        ).fetchone()
        if existing_team:
            logger.warning(f"[TEAM] join_submit() - team name '{team_name}' already taken")
            # Suggest alternative names
            base_name = team_name if len(team_name) <= 27 else team_name[:27]  # Leave room for " 2"
            counter = 2
            suggested_name = f"{base_name} {counter}"
            while conn.execute(
                "SELECT team_name FROM team_codes WHERE LOWER(team_name) = LOWER(?) AND used = 1 AND code != ?",
                (suggested_name, code)
            ).fetchone():
                counter += 1
                suggested_name = f"{base_name} {counter}"

            return render_template('join.html', code=code, error=f'Team name "{team_name}" already taken! Try: "{suggested_name}"')

        code_row = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()

        if not code_row:
            return render_template('join.html', error="Invalid code")

        if code_row['used']:
            # Code is already used - check if it's the same team trying to rejoin
            if code_row['team_name'] and code_row['team_name'].lower() == team_name.lower():
                # Same team rejoining - use shared rejoin logic
                return _rejoin_team(conn, code, code_row, source="REJOIN")
            else:
                # Different team trying to use an already-used code
                logger.warning(f"[TEAM] REJOIN BLOCKED: Code {code} used by '{code_row['team_name']}', attempted by '{team_name}'")
                return render_template('join.html', error="Code already used by another team")

        # Code is unused - claim it
        conn.execute("UPDATE team_codes SET used = 1, team_name = ? WHERE code = ?", (team_name, code))
        conn.commit()
        logger.info(f"[TEAM] join_submit() - code '{code}' claimed by team '{team_name}', session created")

        # Store current startup_id and reset_counter in session
        # If server restarts or game resets, session becomes invalid
        session['code'] = code
        session['team_name'] = team_name
        session['startup_id'] = STARTUP_ID
        session['reset_counter'] = reset_state['counter']

        return redirect(url_for('team.team_play'))


# ============= PLAY ROUTES =============

@team_bp.route('/play')
@team_session_valid
def team_play():
    """Team answer submission page"""
    code = session.get('code')
    team_name = session.get('team_name')
    logger.debug(f"[TEAM] team_play() - code={code}, team={team_name}")

    if not code:
        logger.warning("[TEAM] team_play() - no code in session, redirecting to join")
        return redirect(url_for('team.join'))

    with db_connect() as conn:
        # DEFENSIVE: Verify team still exists in database
        team = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()

        if not team:
            # Team doesn't exist anymore - session is stale
            logger.error(f"[TEAM] team_play() - team {code} not found in database, clearing session")
            session.clear()
            return redirect(url_for('team.join'))

        # DEFENSIVE: Initialize last_heartbeat if NULL (for rejoining teams)
        if team['last_heartbeat'] is None:
            logger.debug(f"[TEAM] team_play() - initializing heartbeat for team {code} ({team_name})")
            conn.execute(
                "UPDATE team_codes SET last_heartbeat = CURRENT_TIMESTAMP WHERE code = ?",
                (code,)
            )
            conn.commit()

        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()

        if not active_round:
            logger.debug(f"[TEAM] team_play() - no active round, showing waiting screen")
            return render_template('play.html',
                                 team_name=team_name,
                                 code=code,
                                 no_active_round=True)

        submission = conn.execute("""
            SELECT * FROM submissions
            WHERE code = ? AND round_id = ?
        """, (code, active_round['id'])).fetchone()

        if submission:
            logger.debug(f"[TEAM] team_play() - round {active_round['round_number']}, already submitted")
            # Get last_submission from session (for answer preview)
            last_submission = session.pop('last_submission', None)

            return render_template('play.html',
                                 team_name=team_name,
                                 code=code,
                                 round_num=active_round['round_number'],
                                 question=active_round['question'],
                                 num_answers=active_round['num_answers'],
                                 already_submitted=True,
                                 submissions_closed=active_round['submissions_closed'],
                                 submission=dict(submission),
                                 last_submission=last_submission)

    logger.debug(f"[TEAM] team_play() - round {active_round['round_number']}, showing answer form ({active_round['num_answers']} answers)")
    return render_template('play.html',
                         team_name=team_name,
                         code=code,
                         round_num=active_round['round_number'],
                         question=active_round['question'],
                         num_answers=active_round['num_answers'],
                         round_id=active_round['id'],
                         submissions_closed=active_round['submissions_closed'])


@team_bp.route('/play/submit', methods=['POST'])
@team_session_valid
def submit_answers():
    """Submit team answers"""
    code = session.get('code')
    round_id = request.form.get('round_id')
    logger.info(f"[TEAM] submit_answers() - code={code}, round_id={round_id}")

    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        logger.warning(f"[TEAM] submit_answers() - system paused, rejecting from code={code}")
        flash('⏸️ System is currently paused. Submissions are disabled.', 'error')
        return redirect(url_for('team.team_play'))

    if not code:
        return redirect(url_for('team.join'))

    # Validation: Tiebreaker must be 0-100
    try:
        tiebreaker = int(request.form.get('tiebreaker', 0) or 0)
        if tiebreaker < 0 or tiebreaker > 100:
            flash('⚠️ Tiebreaker must be between 0 and 100', 'error')
            return redirect(url_for('team.team_play'))
    except ValueError:
        tiebreaker = 0

    with db_connect() as conn:
        # Validate that this is still the active round (prevent stale submissions)
        active_round = conn.execute("SELECT id, submissions_closed FROM rounds WHERE is_active = 1").fetchone()
        if not active_round or str(active_round['id']) != str(round_id):
            logger.warning(f"[TEAM] submit_answers() - stale round_id={round_id}, active={active_round['id'] if active_round else 'None'}")
            # Round has changed - redirect to play page to get current round
            return redirect(url_for('team.team_play'))

        # Check if round is closed
        if active_round['submissions_closed']:
            logger.warning(f"[TEAM] submit_answers() - round closed, rejecting submission from code={code}")
            flash('⏰ Round has ended. Submissions are closed.', 'error')
            return redirect(url_for('team.team_play'))

        # CRITICAL FIX: Check for duplicate submission BEFORE attempting insert
        existing_submission = conn.execute(
            "SELECT id FROM submissions WHERE code = ? AND round_id = ?",
            (code, round_id)
        ).fetchone()

        if existing_submission:
            logger.warning(f"[TEAM] submit_answers() - duplicate submission from code={code} for round_id={round_id}")
            flash('✅ You have already submitted for this round!', 'warning')
            return redirect(url_for('team.team_play'))

        round_info = conn.execute("SELECT num_answers FROM rounds WHERE id = ?", (round_id,)).fetchone()
        num_answers = round_info['num_answers']

        answers = {f'answer{i}': request.form.get(f'answer{i}', '').strip() for i in range(1, num_answers + 1)}

        try:
            fields = ['code', 'round_id', 'tiebreaker'] + [f'answer{i}' for i in range(1, num_answers + 1)]
            placeholders = ', '.join(['?'] * len(fields))
            values = [code, round_id, tiebreaker] + [answers[f'answer{i}'] for i in range(1, num_answers + 1)]

            conn.execute(f"INSERT INTO submissions ({', '.join(fields)}) VALUES ({placeholders})", values)
            conn.commit()
            logger.info(f"[TEAM] submit_answers() - submission saved for code={code}, round_id={round_id}, tiebreaker={tiebreaker}, answers={answers}")

            # Store submission for answer preview
            session['last_submission'] = {
                'round_id': round_id,
                'answers': answers,
                'tiebreaker': tiebreaker
            }
        except sqlite3.IntegrityError:
            # Fallback: UNIQUE constraint caught it
            logger.warning(f"[TEAM] submit_answers() - UNIQUE constraint caught duplicate from code={code}")
            flash('✅ You have already submitted for this round!', 'warning')

    return redirect(url_for('team.team_play'))


# ============= VIEW ROUTES =============

@team_bp.route('/view/<code>')
def team_view(code):
    """View-only page for manually-entered teams. Auth is the code in the URL."""
    code = code.strip().upper()
    logger.debug(f"[VIEW] team_view() - code={code}")

    with db_connect() as conn:
        team = conn.execute(
            "SELECT code, team_name, used FROM team_codes WHERE code = ?",
            (code,)
        ).fetchone()

        if not team:
            logger.warning(f"[VIEW] team_view() - code not found: {code}")
            return render_template('view.html',
                team_name=f"Code: {code}",
                code=code,
                state='code_not_found',
                round_num=0,
                question='')

        if not team['used'] or not team['team_name']:
            logger.debug(f"[VIEW] team_view() - code exists but not yet registered: {code}")
            return render_template('view.html',
                team_name=f"Code: {code}",
                code=code,
                state='waiting_for_registration',
                round_num=0,
                question='')

        team_name = team['team_name']

        active_round = conn.execute(
            "SELECT * FROM rounds WHERE is_active = 1"
        ).fetchone()

        if not active_round:
            return render_template('view.html',
                team_name=team_name,
                code=code,
                state='waiting_for_round',
                round_num=0,
                question='')

        submission = conn.execute(
            "SELECT * FROM submissions WHERE code = ? AND round_id = ?",
            (code, active_round['id'])
        ).fetchone()

        if not submission:
            return render_template('view.html',
                team_name=team_name,
                code=code,
                state='waiting_for_entry',
                round_num=active_round['round_number'],
                question=active_round['question'])

        if not submission['scored']:
            return render_template('view.html',
                team_name=team_name,
                code=code,
                state='waiting_for_scoring',
                round_num=active_round['round_number'],
                question=active_round['question'],
                num_answers=active_round['num_answers'],
                submission=dict(submission))

        return render_template('view.html',
            team_name=team_name,
            code=code,
            state='scored',
            round_num=active_round['round_number'],
            question=active_round['question'],
            num_answers=active_round['num_answers'],
            submission=dict(submission))
