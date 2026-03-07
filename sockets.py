"""WebSocket connection lifecycle and room management for Family Feud.

Room structure:
    hosts           — Host dashboard, scoring queue, photo scan
    teams           — All team players + view pages
    team:<CODE>     — Individual team by code
    viewers         — View-only pages
"""

from collections import defaultdict

from flask_socketio import emit, join_room
from flask import request, session

from extensions import socketio
from config import logger

# In-memory tracking of online team codes, keyed by code -> set of SIDs.
# A team is online as long as it has at least one connected SID.
_team_sids = defaultdict(set)


@socketio.on('connect')
def handle_connect():
    code = session.get('code')
    is_host = session.get('host_authenticated')
    sid = request.sid

    if is_host:
        join_room('hosts')
        logger.info(f"[WS] Host connected (sid={sid})")
    elif code:
        join_room('teams')
        join_room(f'team:{code}')
        was_offline = len(_team_sids[code]) == 0
        _team_sids[code].add(sid)
        if was_offline:
            emit('team:status', {'code': code, 'is_online': True}, to='hosts')
        logger.info(f"[WS] Team {code} connected (sid={sid}, connections={len(_team_sids[code])})")
    else:
        logger.debug("[WS] Anonymous connection (no session)")


@socketio.on('disconnect')
def handle_disconnect():
    code = session.get('code')
    is_host = session.get('host_authenticated')
    sid = request.sid

    if is_host:
        logger.info("[WS] Host disconnected")
    elif code:
        _team_sids[code].discard(sid)
        remaining = len(_team_sids[code])
        if remaining == 0:
            _team_sids.pop(code, None)
            emit('team:status', {'code': code, 'is_online': False}, to='hosts')
        logger.info(f"[WS] Team {code} disconnected (sid={sid}, remaining={remaining})")


@socketio.on('join_viewers')
def handle_join_viewers(data):
    """View-only pages don't have a normal team session, so they explicitly join."""
    code = data.get('code', '').strip().upper() if data else None
    if code:
        join_room('teams')
        join_room('viewers')
        join_room(f'team:{code}')
        logger.info(f"[WS] Viewer joined for team {code}")


def get_online_teams():
    """Return set of currently connected team codes. Used by host status endpoint."""
    return {code for code, sids in _team_sids.items() if sids}
