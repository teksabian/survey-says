"""
Configuration, constants, and environment variable setup for Family Feud.

Every other module imports from here. This module owns:
- Logging configuration (Render vs local)
- All os.environ reads
- Path constants
- AI / GitHub / auth settings
- Prompt constants
"""

import os
import secrets
import time
import logging
from datetime import datetime

# ===== AI SDK AVAILABILITY =====
# Optional dependency — probed once at import time
try:
    import anthropic  # noqa: F401
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ===== LOGGING CONFIGURATION =====
# Set LOG_LEVEL env var to control verbosity (default: INFO)
# Use LOG_LEVEL=DEBUG for verbose output when troubleshooting
log_level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)

IS_RENDER = bool(os.environ.get('RENDER'))

if IS_RENDER:
    # Production on Render - log to stdout only
    logging.basicConfig(
        level=log_level,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.StreamHandler()]
    )
    logger = logging.getLogger(__name__)
    logger.info("FAMILY FEUD - SERVER STARTING (RENDER)")
else:
    # Local development - log to file and console
    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(LOG_DIR, exist_ok=True)

    # Create log filename with timestamp
    log_filename = datetime.now().strftime('%Y-%m-%d_%H-%M-%S.log')
    log_filepath = os.path.join(LOG_DIR, log_filename)

    logging.basicConfig(
        level=log_level,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler(log_filepath),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"FAMILY FEUD - SERVER STARTING (log file: {log_filepath})")

# Suppress Flask/Werkzeug per-request logging noise
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logger.info(f"Log level: {logging.getLevelName(log_level)} (set LOG_LEVEL=DEBUG for verbose output)")

# ===== APP CONSTANTS =====
APP_VERSION = "v2.1.0 - Fusion"

# Use environment variable for secret key in production, generate random for local dev
SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Generate unique startup ID - changes on EVERY server restart
# This ensures old sessions are invalidated when server restarts
# SERVER RESTART = FRESH START (no data persistence)
STARTUP_ID = str(int(time.time() * 1000000))  # Unique timestamp
logger.info(f"Server startup ID: {STARTUP_ID}")
logger.info("All sessions from previous server runs are now invalid")

# ===== MUTABLE STATE =====
# Dict instead of plain int so cross-module mutation works without `global`.
# Access: reset_state['counter']   Mutate: reset_state['counter'] += 1
reset_state = {'counter': 0}
logger.info(f"Reset counter initialized: {reset_state['counter']}")

# ===== PATHS =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "feud.db")
CORRECTIONS_FILE = os.path.join(BASE_DIR, "corrections_history.json")

# ===== HOST AUTHENTICATION =====
HOST_PASSWORD = os.environ.get('HOST_PASSWORD', 'localdev')
if not os.environ.get('HOST_PASSWORD'):
    logger.warning("No HOST_PASSWORD env var set \u2014 using default development password")
else:
    logger.info("Host password protection enabled (custom password set)")

# ===== AI SCORING =====
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
ENABLE_AI_SCORING = os.environ.get('ENABLE_AI_SCORING', 'false').lower() == 'true'
AI_SCORING_ENABLED = ENABLE_AI_SCORING and ANTHROPIC_AVAILABLE and bool(ANTHROPIC_API_KEY)
if AI_SCORING_ENABLED:
    logger.info("AI Scoring: ENABLED (env var ON, SDK installed, API key configured)")
elif ENABLE_AI_SCORING and not ANTHROPIC_AVAILABLE:
    logger.warning("AI Scoring: DISABLED - anthropic SDK not installed")
elif ENABLE_AI_SCORING and not ANTHROPIC_API_KEY:
    logger.warning("AI Scoring: DISABLED - ANTHROPIC_API_KEY not set")
else:
    logger.info("AI Scoring: DISABLED (ENABLE_AI_SCORING not set)")

# AI Model selection - which Claude model to use
AI_MODEL_DEFAULT = os.environ.get('AI_MODEL', 'claude-sonnet-4-20250514')
logger.info(f"AI Model default: {AI_MODEL_DEFAULT}")

AI_MODEL_CHOICES = [
    {'id': 'claude-sonnet-4-20250514', 'name': 'Claude Sonnet 4', 'description': 'Balanced quality & cost', 'cost_note': '~$0.01/scoring'},
    {'id': 'claude-opus-4-20250514', 'name': 'Claude Opus 4', 'description': 'Highest quality, more expensive', 'cost_note': '~$0.05/scoring'},
    {'id': 'claude-haiku-4-5-20251001', 'name': 'Claude Haiku 4.5', 'description': 'Fastest & cheapest', 'cost_note': '~$0.002/scoring'},
]

# ===== GITHUB API =====
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'teksabian/family-feud')
if GITHUB_TOKEN:
    logger.info(f"GitHub API: ENABLED (repo: {GITHUB_REPO})")
else:
    logger.info("GitHub API: DISABLED (no GITHUB_TOKEN env var)")

# ===== QR / RENDER DEFAULTS =====
QR_BASE_URL_ENV = os.environ.get('QR_BASE_URL')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://pubfeud.gamenightguild.net')

# Pre-compute the default QR URL from env vars
if QR_BASE_URL_ENV:
    QR_DEFAULT_URL = QR_BASE_URL_ENV
elif IS_RENDER:
    QR_DEFAULT_URL = RENDER_EXTERNAL_URL
else:
    QR_DEFAULT_URL = 'http://localhost:5000'

# ===== REQUEST LOGGING =====
# Polling endpoints that fire every 5s per client - never log these
QUIET_PATHS = frozenset([
    '/api/heartbeat',
    '/api/check-round-status',
    '/api/broadcast-message',
    '/host/codes-status',
    '/host/check-active-round',
    '/host/count-unscored',
    '/host/team-status',
    '/host/get-sleep-status',
    '/host/photo-scan/team-count',
])

# ===== AI PROMPT CONSTANTS =====

PHOTO_SCAN_PROMPT = """You are extracting handwritten answers from a Family Feud paper answer sheet.

The page contains up to 4 team answer blocks arranged in a 2x2 grid. Each block has this layout:

LAYOUT OF EACH BLOCK:
- "Team Name:" label on the left, followed by a handwritten team name on the line
- A 4-LETTER CODE (like "ABAR", "HJNK", "XMPR") is written separately in the TOP RIGHT CORNER of the block, AWAY from the team name. The code is NOT part of the team name \u2014 it is a separate identifier. It is always exactly 4 uppercase letters with no numbers.
- "Answer 1:" through "Answer 6:" \u2014 handwritten answers on labeled lines
- "Tie Breaker #" \u2014 a number (typically 0-100)

CRITICAL: The 4-letter code and the team name are TWO SEPARATE THINGS. The code is in the top-right corner of the block. The team name is on the "Team Name:" line. Do NOT combine them. For example, if you see "Tina" written after "Team Name:" and "ABAR" written in the corner, the team_name is "Tina" and the code is "ABAR".

Extract ALL team blocks visible on the page that have at least a team name filled in. Skip completely blank blocks.

Rules:
- The code is ALWAYS exactly 4 uppercase letters (A-Z). No numbers, no spaces.
- The code uses only these letters: A B E F H J K M N P R S T W X Y Z
- Read handwriting as accurately as possible, even if messy
- If a field is blank/empty, use an empty string ""
- The tiebreaker should be an integer. If unclear or blank, use 0
- Team names may be creative/unusual \u2014 transcribe exactly what is written
- Answers may contain multiple words, abbreviations, or slang \u2014 transcribe as-is
- If you cannot find the 4-letter code, use "" but look carefully in the top-right area first
- List any fields where you are NOT confident in the "low_confidence_fields" array

Respond with ONLY valid JSON in this exact format (no markdown, no explanation):
{
  "teams": [
    {
      "code": "ABAR",
      "team_name": "Tina",
      "answers": ["chicken", "pizza", "broccoli", "", "", ""],
      "tiebreaker": 42,
      "low_confidence_fields": ["answers.2"]
    }
  ]
}

Always return exactly 6 entries in the answers array per team (use "" for blank ones).
For low_confidence_fields, use: "code", "team_name", "tiebreaker", or "answers.0" through "answers.5"."""

PHOTO_SCAN_SINGLE_PROMPT = """You are extracting handwritten answers from a photo of a SINGLE team's Family Feud paper answer sheet.

This photo shows ONE team's answer block with this layout:
- "Team Name:" label followed by a handwritten team name
- A 4-LETTER CODE (like "ABAR", "HJNK", "XMPR") written in the TOP RIGHT CORNER, separate from the team name. Always exactly 4 uppercase letters.
- "Answer 1:" through "Answer 6:" \u2014 handwritten answers on labeled lines
- "Tie Breaker #" \u2014 a number (typically 0-100)

CRITICAL: The 4-letter code and the team name are TWO SEPARATE THINGS. The code is in the top-right corner. The team name is on the "Team Name:" line. Do NOT combine them.

Rules:
- The code is ALWAYS exactly 4 uppercase letters (A-Z). No numbers, no spaces.
- The code uses only these letters: A B E F H J K M N P R S T W X Y Z
- Read handwriting as accurately as possible, even if messy
- If a field is blank/empty, use an empty string ""
- The tiebreaker should be an integer. If unclear or blank, use 0
- Team names may be creative/unusual \u2014 transcribe exactly what is written
- Answers may contain multiple words, abbreviations, or slang \u2014 transcribe as-is
- If you cannot find the 4-letter code, use "" but look carefully in the top-right area first
- If you CANNOT confidently read a field, leave it as "" (blank) \u2014 do NOT guess
- List any fields where you are NOT confident in the "low_confidence_fields" array

Respond with ONLY valid JSON in this exact format (no markdown, no explanation):
{
  "code": "ABAR",
  "team_name": "Tina",
  "answers": ["chicken", "pizza", "broccoli", "", "", ""],
  "tiebreaker": 42,
  "low_confidence_fields": ["answers.2"]
}

Always return exactly 6 entries in the answers array (use "" for blank ones).
For low_confidence_fields, use: "code", "team_name", "tiebreaker", or "answers.0" through "answers.5"."""
