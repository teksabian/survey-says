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
    logger.info("SURVEY SAYS - SERVER STARTING (RENDER)")
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
    logger.info(f"SURVEY SAYS - SERVER STARTING (log file: {log_filepath})")

# Suppress Flask/Werkzeug per-request logging noise
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Filter out noisy socket.io polling requests from gunicorn access logs.
# These fire every ~250ms per connected client and drown out useful log lines.
class _SocketIOPollingFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if '/socket.io/' in msg and 'transport=polling' in msg:
            return False
        return True

_sio_filter = _SocketIOPollingFilter()
logging.getLogger('gunicorn.access').addFilter(_sio_filter)
# Also apply to root logger in case access lines propagate there directly
logging.getLogger().addFilter(_sio_filter)
logger.info(f"Log level: {logging.getLevelName(log_level)} (set LOG_LEVEL=DEBUG for verbose output)")

# ===== APP CONSTANTS =====
APP_VERSION = "v4.1.0 - Plasma"

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

# ===== CROWD SAYS CONSTANTS =====
CROWDSAYS_TIMER_SECONDS = 45
CROWDSAYS_POINTS_PER_ANSWER = 100
CROWDSAYS_MAX_SPEED_BONUS = 200
CROWDSAYS_PERFECT_BONUS = 300
CROWDSAYS_NUM_ANSWERS = 7
CROWDSAYS_ROUNDS_CONFIG = [{"round": i, "answers": 7} for i in range(1, 9)]

CROWDSAYS_QUESTIONS_PROMPT = """You are a game show writer for "The Crowd Says" — a fill-in-the-blank survey game. Generate {num_rounds} fill-in-the-blank prompts.

Requirements:
- Each prompt should be a fill-in-the-blank statement like "The crowd says... the worst thing to forget on a road trip is ____"
- Prompts should be fun, relatable, and work for a pub game audience
- Every prompt MUST start with "The crowd says..."
- Topics should be everyday life, pop culture, food, travel, relationships, work, etc.
- Avoid controversial, political, or offensive topics
- Each prompt should have many possible common answers (at least 7 obvious ones)

{past_questions_block}

Respond with ONLY valid JSON (no markdown, no explanation):
{{"questions": [{questions_json_example}]}}"""

CROWDSAYS_ANSWERS_PROMPT = """You are a game show writer for "The Crowd Says" — a fill-in-the-blank survey game. Generate 7 common survey answers for each of the following {num_rounds} prompts.

{questions_block}

Requirements:
- Generate EXACTLY 7 answers per prompt
- Answers should be the most common/obvious responses people would give
- Keep answers concise (1-3 words)
- No duplicate answers within a prompt
- All answers should start with a DIFFERENT first letter (this is critical — each answer must begin with a unique letter so letter clues work)
- Answers are all worth equal points (100 each), so no point values needed — just use 100 for all

{past_questions_block}

Respond with ONLY valid JSON in this exact format (no markdown, no explanation):
{{
  "rounds": [
    {{
      "question": "The crowd says... the worst thing to forget on a road trip is ____",
      "answers": [
        {{"text": "Phone", "points": 100}},
        {{"text": "Wallet", "points": 100}},
        {{"text": "Charger", "points": 100}},
        {{"text": "Snacks", "points": 100}},
        {{"text": "Keys", "points": 100}},
        {{"text": "Toothbrush", "points": 100}},
        {{"text": "Directions", "points": 100}}
      ]
    }}
  ]
}}

Generate exactly {num_rounds} rounds. Use the exact prompts provided above. Each answer object must have "text" and "points" keys (all points = 100)."""

# ===== PATHS =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "feud.db")
CORRECTIONS_FILE = os.path.join(BASE_DIR, "corrections_history.json")
SURVEY_HISTORY_FILE = os.path.join(BASE_DIR, "survey_history.json")

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
    {'id': 'gpt-5.4', 'name': 'GPT-5.4', 'provider': 'openai', 'description': 'Latest flagship reasoning model', 'cost_note': '~$0.01/scoring'},
    {'id': 'gpt-5.3-chat-latest', 'name': 'GPT-5.3 Instant', 'provider': 'openai', 'description': 'Fast & natural, low hallucination', 'cost_note': '~$0.002/scoring'},
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

# Default scoring model: specific env > GPT-5.4 (flagship reasoning) > legacy env > Claude Sonnet > none
if _env_scoring_model:
    AI_SCORING_MODEL_DEFAULT = _env_scoring_model
elif OPENAI_READY:
    AI_SCORING_MODEL_DEFAULT = 'gpt-5.4'
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
DEFAULT_THEME = os.environ.get('DEFAULT_THEME', 'gamenight')

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
        'success_text':   '#ffffff',
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
        'success_text':   '#000000',
        'btn_bg':         '#00d4ff',
        'btn_text':       '#000000',
        'btn_blue_bg':    '#0a0a1a',
        'btn_blue_text':  '#00d4ff',
        'score_first_bg': 'linear-gradient(135deg, rgba(0,212,255,0.4) 0%, rgba(0,212,255,0.2) 100%)',
        'score_first_text': '#00d4ff',
        'code_border':    'rgba(0,212,255,0.25)',
    },
    'forest': {
        'name':           'Forest',
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
        'success_text':   '#000000',
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
        'success_text':   '#ffffff',
        'btn_bg':         '#cc2200',
        'btn_text':       '#ffffff',
        'btn_blue_bg':    '#1a1a1a',
        'btn_blue_text':  '#cc2200',
        'score_first_bg': 'linear-gradient(135deg, #cc2200 0%, #aa1a00 100%)',
        'score_first_text': '#ffffff',
        'code_border':    '#333333',
    },
    'gamenight': {
        'name':           'Game Night',
        'font_url':       'https://fonts.googleapis.com/css2?family=Lilita+One&display=swap',
        'font_family':    "'Lilita One', 'Arial Black', Arial, sans-serif",
        'bg_gradient':    'linear-gradient(135deg, #1a1040 0%, #2d1b69 50%, #1a1040 100%)',
        'bg_color':       '#110b2e',
        'accent':         '#facc15',
        'card_border':    '#2d1b69',
        'active_bg':      'linear-gradient(135deg, #2d1b69 0%, #3b2580 100%)',
        'active_border':  '#facc15',
        'text_primary':   '#ffffff',
        'text_accent':    '#facc15',
        'text_muted':     '#a78bfa',
        'success':        '#2dd4bf',
        'success_text':   '#000000',
        'btn_bg':         '#facc15',
        'btn_text':       '#1a1040',
        'btn_blue_bg':    '#2d1b69',
        'btn_blue_text':  '#2dd4bf',
        'score_first_bg': 'linear-gradient(135deg, #facc15 0%, #fde68a 100%)',
        'score_first_text': '#1a1040',
        'code_border':    '#2d1b69',
    },

    # ===== EASY-READ THEMES (elderly / low-vision friendly) =====
    'sunny': {
        'name':           'Sunny Day',
        'elderly':        True,
        'font_url':       '',
        'font_family':    "Verdana, Geneva, 'Trebuchet MS', sans-serif",
        'bg_gradient':    'linear-gradient(135deg, #FFF8E8 0%, #FFFDF5 100%)',
        'bg_color':       '#FFF8E8',
        'accent':         '#D2691E',
        'card_border':    '#D2B48C',
        'active_bg':      'linear-gradient(135deg, #FFF0D0 0%, #FFE8B8 100%)',
        'active_border':  '#D2691E',
        'text_primary':   '#2C1810',
        'text_accent':    '#8B4513',
        'text_muted':     '#6B4226',
        'success':        '#2E7D32',
        'success_text':   '#FFFFFF',
        'btn_bg':         '#D2691E',
        'btn_text':       '#FFFFFF',
        'btn_blue_bg':    '#5D4037',
        'btn_blue_text':  '#FFFFFF',
        'score_first_bg': 'linear-gradient(135deg, #FFD700 0%, #FFA000 100%)',
        'score_first_text': '#2C1810',
        'code_border':    '#D2B48C',
    },
    'clearsky': {
        'name':           'Clear Sky',
        'elderly':        True,
        'font_url':       '',
        'font_family':    "Verdana, Geneva, 'Trebuchet MS', sans-serif",
        'bg_gradient':    'linear-gradient(135deg, #F0F6FF 0%, #E8F0FE 100%)',
        'bg_color':       '#F0F6FF',
        'accent':         '#1565C0',
        'card_border':    '#90CAF9',
        'active_bg':      'linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%)',
        'active_border':  '#1565C0',
        'text_primary':   '#1A237E',
        'text_accent':    '#0D47A1',
        'text_muted':     '#37474F',
        'success':        '#2E7D32',
        'success_text':   '#FFFFFF',
        'btn_bg':         '#1565C0',
        'btn_text':       '#FFFFFF',
        'btn_blue_bg':    '#0D47A1',
        'btn_blue_text':  '#FFFFFF',
        'score_first_bg': 'linear-gradient(135deg, #1565C0 0%, #1976D2 100%)',
        'score_first_text': '#FFFFFF',
        'code_border':    '#90CAF9',
    },
    'garden': {
        'name':           'Garden',
        'elderly':        True,
        'font_url':       '',
        'font_family':    "Verdana, Geneva, 'Trebuchet MS', sans-serif",
        'bg_gradient':    'linear-gradient(135deg, #F2F8F0 0%, #E8F5E9 100%)',
        'bg_color':       '#F2F8F0',
        'accent':         '#2E7D32',
        'card_border':    '#A5D6A7',
        'active_bg':      'linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%)',
        'active_border':  '#2E7D32',
        'text_primary':   '#1B3A1B',
        'text_accent':    '#1B5E20',
        'text_muted':     '#33691E',
        'success':        '#2E7D32',
        'success_text':   '#FFFFFF',
        'btn_bg':         '#2E7D32',
        'btn_text':       '#FFFFFF',
        'btn_blue_bg':    '#1B5E20',
        'btn_blue_text':  '#FFFFFF',
        'score_first_bg': 'linear-gradient(135deg, #2E7D32 0%, #43A047 100%)',
        'score_first_text': '#FFFFFF',
        'code_border':    '#A5D6A7',
    },
}

# ===== REQUEST LOGGING =====
# Endpoints to suppress from debug logs. With WebSocket push, most former
# polling endpoints are now only hit on reconnect-sync (infrequent).
QUIET_PATHS = frozenset([
    '/host/get-sleep-status',
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

FEUD_QUESTIONS_PROMPT = """You are a Family Feud game writer. Generate {num_rounds} survey-style questions for a pub Family Feud night.

Requirements:
- Questions must start with "Name something...", "Name a...", "Name a place...", "Name a reason...", "Tell me something...", or similar Family Feud phrasing
- Questions should be fun, debatable, and have many possible answers
- Mix of topics: relationships, food, work, home, holidays, pop culture, everyday life, etc.
- Avoid overly niche or obscure topics — everyone at a pub table should be able to contribute
- Keep questions concise (under 15 words ideally)
- Questions should work for adults at a pub (not a kids' show)

{past_questions_block}

Respond with ONLY valid JSON (no markdown, no explanation):
{{"questions": [{questions_json_example}]}}"""

FEUD_ANSWERS_PROMPT = """You are a Family Feud game writer. Generate realistic survey answers for each of the following {num_rounds} Family Feud questions.

{questions_block}

Requirements:
- Each round has a specific number of answers (shown in parentheses above). Generate EXACTLY that many answers per question.
- Answers should be ranked from most popular (#1) to least popular
- Point values should sum to approximately 93-97 per question (NOT 100 — in a real survey of 100 people, some give unique answers that don't match anyone else, so the board total is always under 100)
- The #1 answer should typically have 25-50 points
- The lowest answer should typically have 2-8 points
- Answers should feel like real survey results — common answers that many people would give
- Keep answers concise (1-4 words)
- No duplicate answers within a question

{past_questions_block}

Respond with ONLY valid JSON in this exact format (no markdown, no explanation):
{{
  "rounds": [
    {{
      "question": "Name something you take on vacation",
      "answers": [
        {{"text": "Clothes", "points": 40}},
        {{"text": "Sunscreen", "points": 27}},
        {{"text": "Camera", "points": 17}},
        {{"text": "Snacks", "points": 11}}
      ]
    }}
  ]
}}

Generate exactly {num_rounds} rounds. Use the exact questions provided above. Each answer object must have "text" and "points" keys."""

FEUD_REGEN_QUESTION_PROMPT = """You are a Family Feud game writer. Generate realistic survey answers for this Family Feud question:

Question: "{question}"
Number of answers needed: {num_answers}

Requirements:
- Generate EXACTLY {num_answers} answers
- Answers ranked from most popular to least popular
- Point values sum to approximately 93-97 (NOT 100 — some survey respondents give unique answers that don't match anyone, so the board total is always under 100)
- The #1 answer should typically have 25-50 points
- Keep answers concise (1-4 words)
- Answers should feel like real survey results

Do NOT use any of these answers (from other rounds):
{existing_answers}

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "question": "{question}",
  "answers": [
    {{"text": "Answer text", "points": 42}},
    {{"text": "Another answer", "points": 28}}
  ]
}}"""

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
    except (ValueError, TypeError):
        return "recently"

def format_timestamp(timestamp_str):
    """Format timestamp as '7:42:15 PM' for display"""
    if not timestamp_str:
        return ""
    try:
        dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%I:%M:%S %p')  # e.g., "07:42:15 PM"
    except (ValueError, TypeError):
        return ""
