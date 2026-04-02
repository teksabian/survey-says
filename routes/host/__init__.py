"""
Host dashboard routes for Family Feud.

Owns: Host dashboard, round management, code management, settings,
broadcast, reset, training data, and all related host-facing endpoints.

Split into sub-modules:
  - dashboard.py  — main host view, settings, sleep mode, AI config
  - rounds.py     — create, activate, close, upload answers, edit answers
  - codes.py      — generate, reclaim, print QR sheets, answer sheets
  - broadcast.py  — send/clear broadcasts, reset, reset-all
  - training.py   — save/clear AI training corrections
"""

from flask import Blueprint

host_bp = Blueprint('host', __name__)

# Game configuration constants
MIN_ROUNDS = 4
MAX_ROUNDS = 12
MIN_ANSWERS = 3
MAX_ANSWERS = 6
DEFAULT_NUM_ROUNDS = 8
DEFAULT_ANSWERS_PER_ROUND = 4

# Default game configuration - 8 rounds
DEFAULT_ROUNDS_CONFIG = [
    {"round": 1, "answers": 4},
    {"round": 2, "answers": 5},
    {"round": 3, "answers": 6},
    {"round": 4, "answers": 4},
    {"round": 5, "answers": 5},
    {"round": 6, "answers": 3},
    {"round": 7, "answers": 5},
    {"round": 8, "answers": 4}
]

# Backward-compatible alias
ROUNDS_CONFIG = DEFAULT_ROUNDS_CONFIG


def build_rounds_config(num_rounds=DEFAULT_NUM_ROUNDS, default_answers=DEFAULT_ANSWERS_PER_ROUND, per_round_answers=None):
    """Build a rounds config list dynamically.

    Args:
        num_rounds: Number of rounds (4-12)
        default_answers: Default answers per round (3-6)
        per_round_answers: Optional dict {round_num: answer_count} for per-round overrides
    """
    num_rounds = max(MIN_ROUNDS, min(MAX_ROUNDS, int(num_rounds)))
    default_answers = max(MIN_ANSWERS, min(MAX_ANSWERS, int(default_answers)))
    config = []
    for i in range(1, num_rounds + 1):
        answers = default_answers
        if per_round_answers and i in per_round_answers:
            answers = max(MIN_ANSWERS, min(MAX_ANSWERS, int(per_round_answers[i])))
        config.append({"round": i, "answers": answers})
    return config

def get_rounds_config():
    """Return rounds config based on active game mode."""
    from database import get_game_mode
    from config import CROWDSAYS_ROUNDS_CONFIG
    mode = get_game_mode()
    if mode == 'crowdsays':
        return CROWDSAYS_ROUNDS_CONFIG
    return DEFAULT_ROUNDS_CONFIG


# Import sub-modules to register their routes on host_bp
from routes.host import dashboard, rounds, codes, broadcast, training
