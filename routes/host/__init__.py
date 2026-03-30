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

# Game configuration - 8 rounds (Showdown / Family Feud)
ROUNDS_CONFIG = [
    {"round": 1, "answers": 4},
    {"round": 2, "answers": 5},
    {"round": 3, "answers": 6},
    {"round": 4, "answers": 4},
    {"round": 5, "answers": 5},
    {"round": 6, "answers": 3},
    {"round": 7, "answers": 5},
    {"round": 8, "answers": 4}
]


def get_rounds_config():
    """Return the rounds config for the active game mode."""
    from database import get_game_mode
    from config import CROWDSAYS_ROUNDS_CONFIG
    mode = get_game_mode()
    if mode == 'crowdsays':
        return CROWDSAYS_ROUNDS_CONFIG
    return ROUNDS_CONFIG


# Import sub-modules to register their routes on host_bp
from routes.host import dashboard, rounds, codes, broadcast, training
