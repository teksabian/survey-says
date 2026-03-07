"""
API and polling routes for Family Feud.

Owns: JSON endpoints used by JavaScript polling for real-time updates.
All clients poll these endpoints periodically (every 3-5 seconds).
"""

import json
from datetime import datetime
from flask import Blueprint, jsonify, session

from config import logger, STARTUP_ID, reset_state
from auth import host_required
from database import db_connect, get_setting

api_bp = Blueprint('api', __name__)


@api_bp.route('/host/team-status')
@host_required
def get_team_status():
    """Get status of all teams (online/offline) for host dashboard.
    Online status is based on heartbeat recency (polled every 5s by teams)."""
    logger.debug("[API] get_team_status() called")
    with db_connect() as conn:
        teams = conn.execute("""
            SELECT code, team_name, used, last_heartbeat
            FROM team_codes
            ORDER BY code
        """).fetchall()

        result = []
        now = datetime.now()
        for team in teams:
            team_dict = dict(team)
            # Team is online if heartbeat within last 15 seconds
            if team['last_heartbeat']:
                try:
                    last_seen = datetime.fromisoformat(team['last_heartbeat'].replace('Z', '+00:00'))
                    if last_seen.tzinfo:
                        last_seen = last_seen.replace(tzinfo=None)
                    seconds_ago = int((now - last_seen).total_seconds())
                    team_dict['is_online'] = 1 if seconds_ago < 15 else 0

                    if seconds_ago < 60:
                        team_dict['last_seen_text'] = f"{seconds_ago} seconds ago"
                    elif seconds_ago < 3600:
                        minutes = seconds_ago // 60
                        team_dict['last_seen_text'] = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
                    else:
                        hours = seconds_ago // 3600
                        team_dict['last_seen_text'] = f"{hours} hour{'s' if hours != 1 else ''} ago"
                except Exception:
                    team_dict['is_online'] = 0
                    team_dict['last_seen_text'] = "Unknown"
            else:
                team_dict['is_online'] = 0
                team_dict['last_seen_text'] = "Never"

            result.append(team_dict)

        online_count = sum(1 for t in result if t.get('is_online'))
        logger.debug(f"[API] get_team_status() -> {len(result)} teams, {online_count} online")
        return jsonify(result)

@api_bp.route('/api/check-round-status')
def check_round_status():
    """Round status polled by team clients every 3-5 seconds."""
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
        # Update heartbeat for online tracking
        conn.execute(
            "UPDATE team_codes SET last_heartbeat = CURRENT_TIMESTAMP WHERE code = ?",
            (code,)
        )
        conn.commit()

        # Check if there's an active round
        active_round = conn.execute("SELECT id, round_number, submissions_closed, winner_code FROM rounds WHERE is_active = 1").fetchone()

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

            # Include current round winner (for winner interstitial when all scored)
            if active_round['winner_code']:
                winner_team = conn.execute(
                    "SELECT team_name FROM team_codes WHERE code = ?",
                    (active_round['winner_code'],)
                ).fetchone()
                winner_score = conn.execute(
                    "SELECT score FROM submissions WHERE code = ? AND round_id = ?",
                    (active_round['winner_code'], active_round['id'])
                ).fetchone()
                result['winner_team'] = winner_team['team_name'] if winner_team else 'Unknown'
                result['winner_score'] = winner_score['score'] if winner_score else 0

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


@api_bp.route('/api/broadcast-message')
def api_broadcast_message():
    """Broadcast message polled by team/view clients."""
    logger.debug("[API] api_broadcast_message() called")

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

@api_bp.route('/api/view-status/<code>')
def api_view_status(code):
    """View-only status polled by view page clients."""
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
