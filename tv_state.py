"""
In-memory TV board state for the Live TV Game Board.

State is ephemeral — resets on every server restart, consistent with
the nuclear-reset design of the rest of the app.
"""

from config import logger
from database import db_connect

ALLOWED_SCREENS = {'welcome', 'rules', 'question', 'board', 'halftime', 'closing'}

tv_state = {
    'screen': 'welcome',
    'round_id': None,
    'revealed': [],
    'scores_revealed': False,
}


def get_tv_state():
    """Return a copy of the current TV state."""
    return {
        'screen': tv_state['screen'],
        'round_id': tv_state['round_id'],
        'revealed': list(tv_state['revealed']),
        'scores_revealed': tv_state['scores_revealed'],
    }


def set_screen(screen_name):
    """Change the active screen. Resets revealed list when switching to 'board'."""
    if screen_name not in ALLOWED_SCREENS:
        raise ValueError(f"Invalid screen: {screen_name}. Allowed: {ALLOWED_SCREENS}")
    tv_state['screen'] = screen_name
    if screen_name == 'board':
        tv_state['revealed'] = []
        tv_state['scores_revealed'] = False
    logger.info(f"[TV] Screen changed to '{screen_name}'")


def reveal_answer(answer_num):
    """Mark an answer as revealed. Validates against the round's num_answers.
    Returns {'text': str, 'count': int} for the revealed answer."""
    round_id = tv_state['round_id']
    if round_id is None:
        raise ValueError("No round is set for the TV board")

    with db_connect() as conn:
        row = conn.execute(
            "SELECT * FROM rounds WHERE id = ?", (round_id,)
        ).fetchone()

    if not row:
        raise ValueError(f"Round {round_id} not found")

    num_answers = row['num_answers']
    if not isinstance(answer_num, int) or answer_num < 1 or answer_num > num_answers:
        raise ValueError(f"answer_num must be 1-{num_answers}, got {answer_num}")

    if answer_num not in tv_state['revealed']:
        tv_state['revealed'].append(answer_num)
        logger.info(f"[TV] Revealed answer {answer_num} for round {round_id}")

    all_revealed = len(tv_state['revealed']) >= num_answers
    if all_revealed:
        tv_state['scores_revealed'] = True
        logger.info(f"[TV] All {num_answers} answers revealed — scores now visible")

    return {
        'text': row[f'answer{answer_num}'],
        'count': row[f'answer{answer_num}_count'],
        'all_revealed': all_revealed,
        'num_answers': num_answers,
    }


def reset_for_round(round_id):
    """Prepare TV state for a new round."""
    tv_state['round_id'] = round_id
    tv_state['revealed'] = []
    tv_state['scores_revealed'] = False
    tv_state['screen'] = 'question'
    logger.info(f"[TV] Reset for round {round_id}, screen='question'")
