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
# Optional dependencies — probed once at import time
try:
    import anthropic  # noqa: F401
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import openai  # noqa: F401
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

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
APP_VERSION = "v3.2.0 - Fission"

# Use environment variable for secret key in production, generate random for local dev
SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# WARNING: STARTUP_ID and reset_state live in process memory.
# They require a single-worker Gunicorn setup (--workers 1) to work correctly.
# If multiple workers are spawned, each gets its own copy — teams will randomly
# hit the wrong worker and get kicked to Game Over, and "Reset All" will only
# increment the counter in one worker's memory.
# The single-worker constraint is enforced in render.yaml (startCommand).
# SQLite also requires a single writer process, so this is doubly necessary.
# If multi-worker scaling is ever needed, migrate these values to the database.

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
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ENABLE_AI_SCORING = os.environ.get('ENABLE_AI_SCORING', 'false').lower() == 'true'

# Per-provider readiness flags
ANTHROPIC_READY = ANTHROPIC_AVAILABLE and bool(ANTHROPIC_API_KEY)
OPENAI_READY = OPENAI_AVAILABLE and bool(OPENAI_API_KEY)

# AI enabled if ENABLE_AI_SCORING=true AND at least one provider is configured
AI_SCORING_ENABLED = ENABLE_AI_SCORING and (ANTHROPIC_READY or OPENAI_READY)

if AI_SCORING_ENABLED:
    providers = []
    if ANTHROPIC_READY:
        providers.append('Anthropic')
    if OPENAI_READY:
        providers.append('OpenAI')
    logger.info(f"AI Scoring: ENABLED (providers: {', '.join(providers)})")
elif ENABLE_AI_SCORING:
    logger.warning("AI Scoring: DISABLED - no AI provider configured (need ANTHROPIC_API_KEY or OPENAI_API_KEY)")
else:
    logger.info("AI Scoring: DISABLED (ENABLE_AI_SCORING not set)")

# AI Model selection - all available models across providers
# Only models whose provider is ready are included in the choices list
_ALL_MODEL_CHOICES = [
    # Anthropic
    {'id': 'claude-sonnet-4-20250514', 'name': 'Claude Sonnet 4', 'provider': 'anthropic', 'description': 'Balanced quality & cost', 'cost_note': '~$0.01/scoring'},
    {'id': 'claude-opus-4-20250514', 'name': 'Claude Opus 4', 'provider': 'anthropic', 'description': 'Highest quality, more expensive', 'cost_note': '~$0.05/scoring'},
    {'id': 'claude-haiku-4-5-20251001', 'name': 'Claude Haiku 4.5', 'provider': 'anthropic', 'description': 'Fastest & cheapest', 'cost_note': '~$0.002/scoring'},
    # OpenAI
    {'id': 'gpt-5.2', 'name': 'GPT-5.2', 'provider': 'openai', 'description': 'Flagship reasoning model', 'cost_note': '~$0.01/scoring'},
    {'id': 'gpt-4o', 'name': 'GPT-4o', 'provider': 'openai', 'description': 'Fast & vision capable', 'cost_note': '~$0.005/scoring'},
    {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini', 'provider': 'openai', 'description': 'Cheapest OpenAI option', 'cost_note': '~$0.001/scoring'},
]

AI_MODEL_CHOICES = [m for m in _ALL_MODEL_CHOICES
                    if (m['provider'] == 'anthropic' and ANTHROPIC_READY)
                    or (m['provider'] == 'openai' and OPENAI_READY)]

# Model env vars: specific > hardcoded purpose default > legacy AI_MODEL > other provider > none
_env_ocr_model = os.environ.get('AI_OCR_MODEL', '')
_env_scoring_model = os.environ.get('AI_SCORING_MODEL', '')
_env_legacy_model = os.environ.get('AI_MODEL', '')

# Default OCR model: specific env > Claude Sonnet (best vision) > legacy env > GPT-4o > none
if _env_ocr_model:
    AI_OCR_MODEL_DEFAULT = _env_ocr_model
elif ANTHROPIC_READY:
    AI_OCR_MODEL_DEFAULT = 'claude-sonnet-4-20250514'
elif _env_legacy_model:
    AI_OCR_MODEL_DEFAULT = _env_legacy_model
elif OPENAI_READY:
    AI_OCR_MODEL_DEFAULT = 'gpt-4o'
else:
    AI_OCR_MODEL_DEFAULT = ''
logger.info(f"AI OCR Model default: {AI_OCR_MODEL_DEFAULT}")

# Default scoring model: specific env > GPT-5.2 (strong reasoning) > legacy env > Claude Sonnet > none
if _env_scoring_model:
    AI_SCORING_MODEL_DEFAULT = _env_scoring_model
elif OPENAI_READY:
    AI_SCORING_MODEL_DEFAULT = 'gpt-5.2'
elif _env_legacy_model:
    AI_SCORING_MODEL_DEFAULT = _env_legacy_model
elif ANTHROPIC_READY:
    AI_SCORING_MODEL_DEFAULT = 'claude-sonnet-4-20250514'
else:
    AI_SCORING_MODEL_DEFAULT = ''
logger.info(f"AI Scoring Model default: {AI_SCORING_MODEL_DEFAULT}")

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

# ===== COLOR THEMES =====
DEFAULT_THEME = os.environ.get('DEFAULT_THEME', 'classic')

THEMES = {
    'classic': {
        'name':           'Classic',
        'font_url':       '',
        'font_family':    "'Arial Black', Arial, sans-serif",
        'bg_gradient':    'linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #1e3c72 100%)',
        'bg_color':       '#000000',
        'accent':         '#ffd700',
        'card_border':    '#1e3c72',
        'active_bg':      'linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)',
        'active_border':  '#ffd700',
        'text_primary':   '#ffffff',
        'text_accent':    '#ffd700',
        'text_muted':     '#aaaaaa',
        'success':        '#28a745',
        'btn_bg':         '#ffd700',
        'btn_text':       '#000000',
        'btn_blue_bg':    '#1e3c72',
        'btn_blue_text':  '#ffd700',
        'score_first_bg': 'linear-gradient(135deg, #ffd700 0%, #ffed4e 100%)',
        'score_first_text': '#000000',
        'code_border':    '#1e3c72',
    },
    'dark': {
        'name':           'Dark',
        'font_url':       '',
        'font_family':    "'Arial Black', Arial, sans-serif",
        'bg_gradient':    'linear-gradient(135deg, #0a0a1a 0%, #111133 100%)',
        'bg_color':       '#000000',
        'accent':         '#00d4ff',
        'card_border':    'rgba(0,212,255,0.35)',
        'active_bg':      'linear-gradient(135deg, #0a0a1a 0%, #111133 100%)',
        'active_border':  '#00d4ff',
        'text_primary':   '#ffffff',
        'text_accent':    '#00d4ff',
        'text_muted':     '#aaaaaa',
        'success':        '#00d4ff',
        'btn_bg':         '#00d4ff',
        'btn_text':       '#000000',
        'btn_blue_bg':    '#0a0a1a',
        'btn_blue_text':  '#00d4ff',
        'score_first_bg': 'linear-gradient(135deg, rgba(0,212,255,0.4) 0%, rgba(0,212,255,0.2) 100%)',
        'score_first_text': '#00d4ff',
        'code_border':    'rgba(0,212,255,0.25)',
    },
    'retro': {
        'name':           'Retro',
        'font_url':       'https://fonts.googleapis.com/css2?family=Special+Elite&display=swap',
        'font_family':    "'Special Elite', 'Arial Black', Arial, sans-serif",
        'bg_gradient':    'linear-gradient(135deg, #1a3320 0%, #2d5a2d 100%)',
        'bg_color':       '#0f1a0f',
        'accent':         '#f5c842',
        'card_border':    'rgba(44,90,44,0.8)',
        'active_bg':      'linear-gradient(135deg, #1a3320 0%, #2d5a2d 100%)',
        'active_border':  '#f5c842',
        'text_primary':   '#fff8e7',
        'text_accent':    '#f5c842',
        'text_muted':     '#8a7a4a',
        'success':        '#7bc67e',
        'btn_bg':         '#f5c842',
        'btn_text':       '#0f1a0f',
        'btn_blue_bg':    '#1a3320',
        'btn_blue_text':  '#f5c842',
        'score_first_bg': 'linear-gradient(135deg, #f5c842 0%, #e8b830 100%)',
        'score_first_text': '#0f1a0f',
        'code_border':    'rgba(245,200,66,0.25)',
    },
    'stadium': {
        'name':           'Stadium',
        'font_url':       'https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;900&display=swap',
        'font_family':    "'Barlow Condensed', 'Arial Black', Arial, sans-serif",
        'bg_gradient':    'linear-gradient(135deg, #1a1a1a 0%, #111111 100%)',
        'bg_color':       '#111111',
        'accent':         '#cc2200',
        'card_border':    '#333333',
        'active_bg':      'linear-gradient(135deg, #1a1a1a 0%, #111111 100%)',
        'active_border':  '#cc2200',
        'text_primary':   '#ffffff',
        'text_accent':    '#cc2200',
        'text_muted':     '#666666',
        'success':        '#28a745',
        'btn_bg':         '#cc2200',
        'btn_text':       '#ffffff',
        'btn_blue_bg':    '#1a1a1a',
        'btn_blue_text':  '#cc2200',
        'score_first_bg': 'linear-gradient(135deg, #cc2200 0%, #aa1a00 100%)',
        'score_first_text': '#ffffff',
        'code_border':    '#333333',
    },
}

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

# ===== SHARED UTILITY FUNCTIONS =====

def time_ago(timestamp_str):
    """Convert timestamp to 'X minutes ago' format"""
    if not timestamp_str:
        return "just now"
    try:
        dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        diff = datetime.now() - dt
        minutes = int(diff.total_seconds() / 60)
        if minutes < 1:
            return "just now"
        elif minutes == 1:
            return "1 minute ago"
        elif minutes < 60:
            return f"{minutes} minutes ago"
        else:
            hours = minutes // 60
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
    except:
        return "recently"

def format_timestamp(timestamp_str):
    """Format timestamp as '7:42:15 PM' for display"""
    if not timestamp_str:
        return ""
    try:
        dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%I:%M:%S %p')  # e.g., "07:42:15 PM"
    except:
        return ""
