"""
API and polling routes for Survey Says.

Owns: JSON endpoints used by JavaScript polling — round status,
broadcast messages, view-only status, and host team status.
These endpoints serve as reconnect-sync fallbacks; primary updates are via WebSocket.
"""

import json
from flask import Blueprint, jsonify, session

from config import logger, STARTUP_ID, reset_state
from auth import host_required
from database import db_connect, get_setting
from sockets import get_online_teams
from tv_state import get_tv_state

api_bp = Blueprint('api', __name__)


@api_bp.route('/host/team-status')
@host_required
def get_team_status():
    """Get status of all teams (online/offline) for host dashboard. Primary updates via WebSocket."""
    logger.debug("[API] get_team_status() called")
    online = get_online_teams()
    with db_connect() as conn:
        teams = conn.execute("""
            SELECT code, team_name, used
            FROM team_codes
            ORDER BY code
        """).fetchall()

        result = []
        for team in teams:
            team_dict = dict(team)
            team_dict['is_online'] = 1 if team['code'] in online else 0
            result.append(team_dict)

        online_count = sum(1 for t in result if t.get('is_online'))
        logger.debug(f"[API] get_team_status() -> {len(result)} teams, {online_count} online")
        return jsonify(result)

@api_bp.route('/api/check-round-status')
def check_round_status():
    """Round status for client reconnect-sync. Primary updates via WebSocket."""
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

            # Submission and team counts for live counter
            submission_count = conn.execute(
                "SELECT COUNT(*) FROM submissions WHERE round_id = ?",
                (active_round['id'],)
            ).fetchone()[0]

            result = {
                'has_active_round': True,
                'round_id': active_round['id'],
                'round_number': active_round['round_number'],
                'submissions_closed': bool(active_round['submissions_closed']),
                'already_submitted': submission is not None,
                'submission_count': submission_count
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


@api_bp.route('/api/broadcast-message')
def api_broadcast_message():
    """Broadcast message for client reconnect-sync. Primary updates via WebSocket."""
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

@api_bp.route('/api/leaderboard')
def api_leaderboard():
    """Cumulative leaderboard across all scored rounds. No answer data exposed."""
    code = session.get('code')
    if not code:
        return jsonify({'error': 'No code in session'}), 401

    with db_connect() as conn:
        active_round = conn.execute("SELECT id FROM rounds WHERE is_active = 1").fetchone()
        active_round_id = active_round['id'] if active_round else -1

        teams = conn.execute("""
            SELECT tc.team_name, tc.code,
                   COALESCE(SUM(CASE WHEN s.host_submitted = 1 THEN s.score ELSE 0 END), 0) as total_score,
                   MAX(CASE WHEN s.round_id = ? AND s.host_submitted = 1 THEN 1 ELSE 0 END) as current_round_scored,
                   MAX(CASE WHEN s.host_submitted = 1 THEN 1 ELSE 0 END) as has_been_scored
            FROM team_codes tc
            LEFT JOIN submissions s ON tc.code = s.code
            WHERE tc.used = 1 AND tc.team_name IS NOT NULL
            GROUP BY tc.code
            ORDER BY total_score DESC, tc.team_name ASC
        """, (active_round_id,)).fetchall()

        leaderboard = []
        for i, row in enumerate(teams):
            leaderboard.append({
                'team_name': row['team_name'],
                'total_score': row['total_score'],
                'rank': i + 1,
                'is_you': row['code'] == code,
                'pending': bool(
                    (active_round and not row['current_round_scored']) or
                    (not active_round and not row['has_been_scored'])
                )
            })

        return jsonify({
            'leaderboard': leaderboard,
            'scores_revealed': get_tv_state().get('scores_revealed', False),
        })


@api_bp.route('/api/view-status/<code>')
def api_view_status(code):
    """View-only status for client reconnect-sync. Primary updates via WebSocket."""
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


@api_bp.route('/api/tv-state')
def api_tv_state():
    """Full TV state plus round data for the TV display page. No auth required."""
    state = get_tv_state()
    round_id = state.get('round_id')

    result = dict(state)
    result['round'] = None

    # Fall back to DB active round if tv_state has no round set
    if round_id is None:
        with db_connect() as conn:
            active = conn.execute(
                "SELECT id FROM rounds WHERE is_active = 1"
            ).fetchone()
            if active:
                round_id = active['id']

    if round_id is not None:
        with db_connect() as conn:
            row = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
            if row:
                round_data = {
                    'id': row['id'],
                    'round_number': row['round_number'],
                    'question': row['question'],
                    'num_answers': row['num_answers'],
                    'answers': [],
                }
                is_host = session.get('host_authenticated', False)
                for i in range(1, row['num_answers'] + 1):
                    revealed = i in state['revealed']
                    round_data['answers'].append({
                        'num': i,
                        'text': row[f'answer{i}'] if (revealed or is_host) else None,
                        'count': row[f'answer{i}_count'] if (revealed or is_host) else None,
                        'revealed': revealed,
                    })
                result['round'] = round_data

    return jsonify(result)
