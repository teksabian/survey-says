from flask_socketio import emit, join_room, leave_room
from flask import session, request as flask_request
from extensions import socketio
from config import logger

# In-memory set of online team codes (replaces heartbeat DB queries)
online_teams = set()


@socketio.on('connect')
def handle_connect():
    code = session.get('code')
    is_host = session.get('host_authenticated')
    sid = getattr(flask_request, 'sid', 'unknown')

    if is_host:
        join_room('hosts')
        logger.info(f"[WS] Host connected (sid={sid})")
    elif code:
        join_room('teams')
        join_room(f'team:{code}')
        online_teams.add(code)
        emit('team:status', {'code': code, 'is_online': True}, to='hosts')
        logger.info(f"[WS] Team {code} connected (sid={sid})")
    else:
        logger.debug(f"[WS] Anonymous connection (sid={sid})")


@socketio.on('disconnect')
def handle_disconnect():
    code = session.get('code')
    is_host = session.get('host_authenticated')

    if is_host:
        logger.info("[WS] Host disconnected")
    elif code:
        online_teams.discard(code)
        emit('team:status', {'code': code, 'is_online': False}, to='hosts')
        logger.info(f"[WS] Team {code} disconnected")


@socketio.on('join_viewers')
def handle_join_viewers(data):
    """View-only pages don't have a normal team session, so they explicitly join rooms."""
    code = data.get('code', '').strip().upper() if data else None
    if code:
        join_room('teams')
        join_room('viewers')
        join_room(f'team:{code}')
        logger.info(f"[WS] Viewer joined for team {code}")


def get_online_teams():
    """Return set of currently connected team codes. Used by host status endpoint."""
    return online_teams.copy()
