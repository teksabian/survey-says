from flask_socketio import emit, join_room, leave_room
from flask import session, request as flask_request
from extensions import socketio
from config import logger
from tv_state import get_tv_state, set_screen, reveal_answer, reset_for_round

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


@socketio.on('join_tv')
def handle_join_tv():
    """Any client can join the TV room to receive board updates."""
    join_room('tv')
    sid = getattr(flask_request, 'sid', 'unknown')
    logger.info(f"[WS] Client joined TV room (sid={sid})")
    emit('tv:state_update', get_tv_state())


@socketio.on('tv:set_screen')
def handle_tv_set_screen(data):
    """Host changes the TV screen."""
    if not session.get('host_authenticated'):
        return
    screen_name = data.get('screen') if data else None
    try:
        set_screen(screen_name)
        emit('tv:screen_change', {'screen': screen_name}, to='tv')
        emit('tv:state_update', get_tv_state(), to='tv')
    except ValueError as e:
        emit('tv:error', {'message': str(e)})


@socketio.on('tv:reveal_answer')
def handle_tv_reveal_answer(data):
    """Host reveals an answer on the TV board."""
    if not session.get('host_authenticated'):
        return
    answer_num = data.get('answer_num') if data else None
    try:
        if not isinstance(answer_num, int):
            answer_num = int(answer_num)
        answer_data = reveal_answer(answer_num)
        reveal_payload = {
            'answer_num': answer_num,
            'text': answer_data['text'],
            'count': answer_data['count'],
            'points': answer_data['num_answers'] - answer_num + 1,
        }
        emit('tv:reveal', reveal_payload, to='tv')
        emit('tv:reveal', reveal_payload, to='teams')
        emit('tv:state_update', get_tv_state(), to='tv')
        if answer_data.get('all_revealed'):
            emit('leaderboard:scores_revealed', {}, to='teams')
    except (ValueError, TypeError) as e:
        emit('tv:error', {'message': str(e)})


@socketio.on('tv:reset_round')
def handle_tv_reset_round(data):
    """Host resets the TV board for a new round."""
    if not session.get('host_authenticated'):
        return
    round_id = data.get('round_id') if data else None
    try:
        if not isinstance(round_id, int):
            round_id = int(round_id)
        reset_for_round(round_id)
        emit('tv:state_update', get_tv_state(), to='tv')
    except (ValueError, TypeError) as e:
        emit('tv:error', {'message': str(e)})
