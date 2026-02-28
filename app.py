import os
import json
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, jsonify, session, flash

from config import (
    logger, APP_VERSION, STARTUP_ID, reset_state,
)
from auth import auth_bp, host_required, team_session_valid, configure_session
from routes.team import team_bp
from database import (
    db_connect,
    ensure_fixed_codes,
    init_db,
    nuke_all_data,
    get_setting,
)

from routes.host import host_bp
from routes.scoring import scoring_bp

app = Flask(__name__)
configure_session(app)
app.register_blueprint(auth_bp)
app.register_blueprint(host_bp)
app.register_blueprint(team_bp)
app.register_blueprint(scoring_bp)

@app.context_processor
def inject_version():
    """Make app version and cache buster available in all templates.

    {{ app_version }} - Display version string (e.g. "v2.0.0 - Fusion")
    {{ cache_bust }}  - Query param for static assets, changes every deploy
                        Usage: href="...?v={{ cache_bust }}"
    """
    return dict(app_version=APP_VERSION, cache_bust=STARTUP_ID)

@app.after_request
def add_cache_headers(response):
    """Prevent browsers from caching HTML pages after deployment.

    Static assets use ?v= query params for cache busting.
    HTML responses get no-cache so phones always get fresh pages on reload.
    """
    if 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

init_db()
nuke_all_data()  # NUKE EVERYTHING on every server start
ensure_fixed_codes()  # Load fixed codes from codes.json


@app.route('/api/heartbeat', methods=['POST'])
@team_session_valid
def heartbeat():
    """Update last heartbeat timestamp for active tab detection"""
    code = session.get('code')
    logger.debug(f"[API] heartbeat() - code={code}")

    if not code:
        return jsonify({"success": False}), 401

    with db_connect() as conn:
        conn.execute("""
            UPDATE team_codes
            SET last_heartbeat = CURRENT_TIMESTAMP
            WHERE code = ?
        """, (code,))
        conn.commit()

    return jsonify({"success": True})

@app.route('/host/team-status')
@host_required
def get_team_status():
    """Get status of all teams (online/offline) for host dashboard"""
    logger.debug("[API] get_team_status() called")
    with db_connect() as conn:
        teams = conn.execute("""
            SELECT code, team_name, used, last_heartbeat,
                   CASE
                       WHEN last_heartbeat IS NULL THEN 0
                       WHEN (julianday('now') - julianday(last_heartbeat)) * 86400 <= 15 THEN 1
                       ELSE 0
                   END as is_online
            FROM team_codes
            ORDER BY code
        """).fetchall()

        result = []
        for team in teams:
            team_dict = dict(team)
            # Calculate last seen time
            if team['last_heartbeat']:
                from datetime import datetime
                try:
                    last_seen = datetime.fromisoformat(team['last_heartbeat'].replace('Z', '+00:00'))
                    now = datetime.now(last_seen.tzinfo) if last_seen.tzinfo else datetime.now()
                    seconds_ago = int((now - last_seen).total_seconds())

                    if seconds_ago < 60:
                        team_dict['last_seen_text'] = f"{seconds_ago} seconds ago"
                    elif seconds_ago < 3600:
                        minutes = seconds_ago // 60
                        team_dict['last_seen_text'] = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
                    else:
                        hours = seconds_ago // 3600
                        team_dict['last_seen_text'] = f"{hours} hour{'s' if hours != 1 else ''} ago"
                except:
                    team_dict['last_seen_text'] = "Unknown"
            else:
                team_dict['last_seen_text'] = "Never"

            result.append(team_dict)

        online_count = sum(1 for t in result if t.get('is_online'))
        logger.debug(f"[API] get_team_status() -> {len(result)} teams, {online_count} online")
        return jsonify(result)

@app.route('/api/check-round-status')
def check_round_status():
    """API endpoint to check if there's an active round (for AJAX polling)"""
    code = session.get('code')
    logger.debug(f"[API] check_round_status() - code={code}")

    if not code:
        return jsonify({'error': 'No code in session'}), 401

    # Check if server was restarted (startup_id mismatch)
    session_startup_id = session.get('startup_id')
    if session_startup_id != STARTUP_ID:
        return jsonify({'error': 'Server restarted', 'reload': True}), 401

    # Check if game was reset (reset_counter mismatch)
    session_reset_counter = session.get('reset_counter', 0)
    if session_reset_counter != reset_state['counter']:
        return jsonify({'error': 'Game was reset', 'reload': True}), 401

    # Check if server is in sleep mode
    server_sleep = get_setting('server_sleep', 'false')
    if server_sleep == 'true':
        return jsonify({'sleep_mode': True, 'message': 'Server in sleep mode'}), 200

    with db_connect() as conn:
        # Check if there's an active round
        active_round = conn.execute("SELECT id, round_number, submissions_closed FROM rounds WHERE is_active = 1").fetchone()

        if active_round:
            # Check if this team already submitted for this round
            submission = conn.execute(
                "SELECT id FROM submissions WHERE code = ? AND round_id = ?",
                (code, active_round['id'])
            ).fetchone()

            result = {
                'has_active_round': True,
                'round_id': active_round['id'],
                'round_number': active_round['round_number'],
                'submissions_closed': bool(active_round['submissions_closed']),
                'already_submitted': submission is not None
            }

            # Include previous round's winner (for winner interstitial on round transition)
            prev_round = conn.execute("""
                SELECT r.round_number, r.winner_code, tc.team_name, s.score
                FROM rounds r
                LEFT JOIN team_codes tc ON r.winner_code = tc.code
                LEFT JOIN submissions s ON r.winner_code = s.code AND r.id = s.round_id
                WHERE r.round_number = ? - 1
            """, (active_round['round_number'],)).fetchone()

            if prev_round and prev_round['winner_code']:
                result['prev_winner_team'] = prev_round['team_name']
                result['prev_winner_score'] = prev_round['score']
                result['prev_round_number'] = prev_round['round_number']

            logger.debug(f"[API] check_round_status() -> round={active_round['round_number']}, closed={bool(active_round['submissions_closed'])}, submitted={submission is not None}")
            return jsonify(result)
        else:
            logger.debug("[API] check_round_status() -> no active round")
            return jsonify({
                'has_active_round': False
            })


@app.route('/api/broadcast-message')
def api_broadcast_message():
    """API endpoint for teams to get current broadcast message"""
    logger.debug("[API] api_broadcast_message() called")
    import json

    broadcast_json = get_setting('broadcast_message', '')

    # Handle legacy format (plain string) or new format (JSON)
    try:
        if broadcast_json:
            broadcast_data = json.loads(broadcast_json)
            return jsonify({
                'message': broadcast_data.get('message', ''),
                'timestamp': broadcast_data.get('timestamp', 0)
            })
        else:
            return jsonify({'message': '', 'timestamp': 0})
    except (json.JSONDecodeError, TypeError):
        # Legacy format - just a plain string
        return jsonify({'message': broadcast_json, 'timestamp': 0})

@app.route('/api/view-status/<code>')
def api_view_status(code):
    """API endpoint for view-only page polling. Returns round + scoring state."""
    code = code.strip().upper()
    logger.debug(f"[API] api_view_status() - code={code}")

    server_sleep = get_setting('server_sleep', 'false')
    if server_sleep == 'true':
        return jsonify({'sleep_mode': True}), 200

    with db_connect() as conn:
        team = conn.execute(
            "SELECT code, team_name, used FROM team_codes WHERE code = ?",
            (code,)
        ).fetchone()

        if not team:
            return jsonify({'state': 'code_not_found', 'has_active_round': False})

        if not team['used'] or not team['team_name']:
            return jsonify({'state': 'waiting_for_registration', 'has_active_round': False})

        active_round = conn.execute(
            "SELECT * FROM rounds WHERE is_active = 1"
        ).fetchone()

        if not active_round:
            result = {
                'has_active_round': False,
                'state': 'waiting_for_round'
            }

            last_round = conn.execute("""
                SELECT r.round_number, r.winner_code, tc.team_name, s.score
                FROM rounds r
                LEFT JOIN team_codes tc ON r.winner_code = tc.code
                LEFT JOIN submissions s ON r.winner_code = s.code AND r.id = s.round_id
                ORDER BY r.round_number DESC LIMIT 1
            """).fetchone()

            if last_round and last_round['winner_code']:
                result['prev_winner_team'] = last_round['team_name']
                result['prev_winner_score'] = last_round['score']
                result['prev_round_number'] = last_round['round_number']

            return jsonify(result)

        submission = conn.execute(
            "SELECT * FROM submissions WHERE code = ? AND round_id = ?",
            (code, active_round['id'])
        ).fetchone()

        result = {
            'has_active_round': True,
            'round_id': active_round['id'],
            'round_number': active_round['round_number'],
            'question': active_round['question'],
            'num_answers': active_round['num_answers'],
            'submissions_closed': bool(active_round['submissions_closed'])
        }

        if not submission:
            result['state'] = 'waiting_for_entry'
        elif not submission['scored']:
            result['state'] = 'waiting_for_scoring'
            result['answers'] = {
                f'answer{i}': submission[f'answer{i}']
                for i in range(1, active_round['num_answers'] + 1)
            }
            result['tiebreaker'] = submission['tiebreaker']
        else:
            # Players only see their submitted answers - no scoring data
            result['state'] = 'scored'
            result['answers'] = {
                f'answer{i}': submission[f'answer{i}']
                for i in range(1, active_round['num_answers'] + 1)
            }
            result['tiebreaker'] = submission['tiebreaker']

        prev_round = conn.execute("""
            SELECT r.round_number, r.winner_code, tc.team_name, s.score
            FROM rounds r
            LEFT JOIN team_codes tc ON r.winner_code = tc.code
            LEFT JOIN submissions s ON r.winner_code = s.code AND r.id = s.round_id
            WHERE r.round_number = ? - 1
        """, (active_round['round_number'],)).fetchone()

        if prev_round and prev_round['winner_code']:
            result['prev_winner_team'] = prev_round['team_name']
            result['prev_winner_score'] = prev_round['score']
            result['prev_round_number'] = prev_round['round_number']

        return jsonify(result)

if __name__ == '__main__':
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print("\n" + "="*60)
    print("🎮 FAMILY FEUD - PRODUCTION SERVER")
    print("="*60)
    print(f"\n📱 Team Join: http://{local_ip}:5000/join")
    print(f"🖥️  Host Dashboard: http://localhost:5000/host")
    print(f"🏆 Scoring Queue: http://localhost:5000/host/scoring-queue")
    print(f"\n💡 Upload answer sheet, generate codes, start playing!")
    print("="*60 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=False)
