"""
Database layer for Family Feud.

Owns all SQLite schema, migrations, connection management, and settings helpers.
Pure database operations — no Flask dependency.
"""

import os
import json
import sqlite3
import secrets

from config import logger, DB_PATH


def db_connect():
    logger.debug("[DB] Opening database connection")
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # Production SQLite settings for concurrent writes
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def generate_team_code():
    """Generate 4-letter code like BAJK (no numbers for easier mobile typing)"""
    # Only letters that are unambiguous in handwriting AND OCR
    # Removed: C/G (similar), D/O (similar), I/L (identical), O/Q (similar), U/V (similar)
    chars = 'ABEFHJKMNPRSTWXYZ'
    code = ''.join(secrets.choice(chars) for _ in range(4))
    logger.debug(f"[CODES] Generated team code: {code}")
    return code

def load_fixed_codes():
    """Load the fixed team codes from codes.json"""
    codes_file = os.path.join(os.path.dirname(__file__), 'codes.json')
    with open(codes_file, 'r') as f:
        codes = json.load(f)
    return codes

def ensure_fixed_codes():
    """Insert fixed codes from codes.json into the database if they don't exist.
    Also removes any codes NOT in the fixed list (leftover from old random generation).
    """
    codes = load_fixed_codes()
    with db_connect() as conn:
        # Remove codes not in the fixed list
        placeholders = ','.join(['?'] * len(codes))
        conn.execute(f"DELETE FROM team_codes WHERE code NOT IN ({placeholders})", codes)
        # Insert fixed codes if not already present
        for code in codes:
            try:
                conn.execute("INSERT INTO team_codes (code, used) VALUES (?, 0)", (code,))
            except sqlite3.IntegrityError:
                pass  # Already exists
        conn.commit()
    logger.info(f"[CODES] {len(codes)} fixed codes loaded from codes.json")

def init_db():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                used INTEGER DEFAULT 0,
                team_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_number INTEGER NOT NULL,
                question TEXT,
                num_answers INTEGER NOT NULL,
                answer1 TEXT,
                answer1_count INTEGER,
                answer2 TEXT,
                answer2_count INTEGER,
                answer3 TEXT,
                answer3_count INTEGER,
                answer4 TEXT,
                answer4_count INTEGER,
                answer5 TEXT,
                answer5_count INTEGER,
                answer6 TEXT,
                answer6_count INTEGER,
                is_active INTEGER DEFAULT 0,
                submissions_closed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                round_id INTEGER NOT NULL,
                answer1 TEXT,
                answer2 TEXT,
                answer3 TEXT,
                answer4 TEXT,
                answer5 TEXT,
                answer6 TEXT,
                tiebreaker INTEGER,
                score INTEGER DEFAULT 0,
                scored INTEGER DEFAULT 0,
                host_submitted INTEGER DEFAULT 0,
                scored_at TIMESTAMP,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (round_id) REFERENCES rounds (id),
                UNIQUE(code, round_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id INTEGER NOT NULL,
                submission_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                team_answer TEXT NOT NULL,
                survey_answer TEXT,
                survey_num INTEGER,
                correction_type TEXT NOT NULL,
                ai_reasoning TEXT,
                host_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()

        logger.info("Database tables initialized")

        # Migration: Add checked_answers column if it doesn't exist
        try:
            conn.execute("SELECT checked_answers FROM submissions LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding checked_answers column to submissions table...")
            conn.execute("ALTER TABLE submissions ADD COLUMN checked_answers TEXT")
            conn.commit()
            logger.info("Migration complete: checked_answers column added")

        # Migration: Add submissions_closed column to rounds table if it doesn't exist
        try:
            conn.execute("SELECT submissions_closed FROM rounds LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding submissions_closed column to rounds table...")
            conn.execute("ALTER TABLE rounds ADD COLUMN submissions_closed INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Migration complete: submissions_closed column added")

        # Migration: Add previous_score column to submissions table if it doesn't exist
        try:
            conn.execute("SELECT previous_score FROM submissions LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding previous_score column to submissions table...")
            conn.execute("ALTER TABLE submissions ADD COLUMN previous_score INTEGER DEFAULT NULL")
            conn.commit()
            logger.info("Migration complete: previous_score column added")

        # Migration: Add last_heartbeat column to team_codes table (v1.1.0)
        try:
            conn.execute("SELECT last_heartbeat FROM team_codes LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding last_heartbeat column to team_codes table...")
            conn.execute("ALTER TABLE team_codes ADD COLUMN last_heartbeat TIMESTAMP DEFAULT NULL")
            conn.commit()
            logger.info("Migration complete: last_heartbeat column added")

        # Migration: Add reconnected column to team_codes table (v1.1.0)
        try:
            conn.execute("SELECT reconnected FROM team_codes LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding reconnected column to team_codes table...")
            conn.execute("ALTER TABLE team_codes ADD COLUMN reconnected INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Migration complete: reconnected column added")

        # Migration: Add winner_code column to rounds table (v1.1.0)
        try:
            conn.execute("SELECT winner_code FROM rounds LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding winner_code column to rounds table...")
            conn.execute("ALTER TABLE rounds ADD COLUMN winner_code TEXT DEFAULT NULL")
            conn.commit()
            logger.info("Migration complete: winner_code column added")

        # Migration: Add host_reason column to ai_corrections table (v2.0.4)
        try:
            conn.execute("SELECT host_reason FROM ai_corrections LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding host_reason column to ai_corrections table...")
            conn.execute("ALTER TABLE ai_corrections ADD COLUMN host_reason TEXT DEFAULT NULL")
            conn.commit()
            logger.info("Migration complete: host_reason column added")

        # Migration: Add photo_path column to submissions table (for scorecard images)
        try:
            conn.execute("SELECT photo_path FROM submissions LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding photo_path column to submissions table...")
            conn.execute("ALTER TABLE submissions ADD COLUMN photo_path TEXT DEFAULT NULL")
            conn.commit()
            logger.info("Migration complete: photo_path column added")

        # Migration: Add ai_matches and ai_reasoning columns to submissions table (auto AI scoring)
        try:
            conn.execute("SELECT ai_matches FROM submissions LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding ai_matches column to submissions table...")
            conn.execute("ALTER TABLE submissions ADD COLUMN ai_matches TEXT DEFAULT NULL")
            conn.commit()
            logger.info("Migration complete: ai_matches column added")

        try:
            conn.execute("SELECT ai_reasoning FROM submissions LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding ai_reasoning column to submissions table...")
            conn.execute("ALTER TABLE submissions ADD COLUMN ai_reasoning TEXT DEFAULT NULL")
            conn.commit()
            logger.info("Migration complete: ai_reasoning column added")

        try:
            conn.execute("SELECT host_submitted FROM submissions LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding host_submitted column to submissions table...")
            conn.execute("ALTER TABLE submissions ADD COLUMN host_submitted INTEGER DEFAULT 0")
            conn.execute("UPDATE submissions SET host_submitted = 1 WHERE scored = 1")
            conn.commit()
            logger.info("Migration complete: host_submitted column added (backfilled from scored)")

        # Migration: Split ai_model into ai_ocr_model and ai_scoring_model
        existing_ai_model = conn.execute(
            "SELECT value FROM settings WHERE key = 'ai_model'"
        ).fetchone()
        if existing_ai_model and existing_ai_model['value']:
            old_model = existing_ai_model['value']
            for new_key in ('ai_ocr_model', 'ai_scoring_model'):
                existing_new = conn.execute(
                    "SELECT value FROM settings WHERE key = ?", (new_key,)
                ).fetchone()
                if not existing_new or not existing_new['value']:
                    conn.execute(
                        "INSERT OR REPLACE INTO settings (key, value, description, updated_at) "
                        "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                        (new_key, old_model,
                         'AI model for OCR' if 'ocr' in new_key else 'AI model for scoring')
                    )
                    logger.info(f"[MIGRATION] Migrated ai_model='{old_model}' -> {new_key}")
            conn.commit()

        # Initialize default settings if they don't exist
        default_settings = [
            ('allow_team_registration', 'true', 'Allow new teams to join'),
            ('system_paused', 'false', 'System pause status'),
            ('broadcast_message', '', 'Broadcast message to all teams'),
            ('server_sleep', 'false', 'Server sleep mode - stops auto-refresh'),
            ('ai_ocr_model', '', 'AI model for photo scanning / OCR'),
            ('ai_scoring_model', '', 'AI model for answer scoring'),
            ('extended_thinking_enabled', 'false', 'Enable extended thinking for AI calls'),
            ('thinking_budget_tokens', '10000', 'Token budget for extended thinking'),
            ('auto_ai_scoring', 'true', 'Auto AI score new submissions on the scoring queue'),
            ('ai_generation_model', '', 'AI model for round generation'),
            ('color_theme', 'gamenight', 'UI color theme'),
        ]

        for key, value, description in default_settings:
            existing = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO settings (key, value, description) VALUES (?, ?, ?)",
                    (key, value, description)
                )
        conn.commit()

        # Auto-generate 30 codes if table is empty
        codes_exist = conn.execute("SELECT COUNT(*) as cnt FROM team_codes").fetchone()['cnt']
        if codes_exist == 0:
            logger.info("Auto-generating 30 team codes...")
            generated = 0
            attempts = 0
            while generated < 30 and attempts < 100:
                code = generate_team_code()
                try:
                    conn.execute("INSERT INTO team_codes (code, used) VALUES (?, 0)", (code,))
                    conn.commit()
                    generated += 1
                except sqlite3.IntegrityError:
                    attempts += 1
                    continue
            logger.info(f"Generated {generated} team codes")
        else:
            logger.info(f"Database already has {codes_exist} team codes")

# ============= NUCLEAR RESET ON EVERY SERVER START =============
def nuke_all_data():
    """NUCLEAR OPTION: Clear ALL game data on server startup

    SERVER RESTART = FRESH START
    - No old teams
    - No old submissions
    - No old rounds
    - EVERYTHING IS BRAND NEW
    """
    logger.info("[RESET] Nuclear reset - clearing all game data")

    with db_connect() as conn:
        # DELETE EVERYTHING
        conn.execute("DELETE FROM submissions")
        conn.execute("DELETE FROM rounds")
        conn.execute("UPDATE team_codes SET used = 0, team_name = NULL")
        conn.commit()

    logger.info("[RESET] All data cleared - server is fresh, all teams must rejoin")

# ============= SETTINGS HELPERS =============

def get_setting(key, default=None):
    """Get a setting value from database, return default if not found"""
    try:
        with db_connect() as conn:
            result = conn.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,)
            ).fetchone()
            value = result['value'] if result else default
            logger.debug(f"[SETTINGS] get_setting('{key}') = '{value}'")
            return value
    except Exception as e:
        logger.warning(f"[SETTINGS] Failed to get setting '{key}': {e}")
        return default

def set_setting(key, value, description=''):
    """Save a setting to database"""
    try:
        with db_connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO settings (key, value, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, value, description))
            conn.commit()
            logger.debug(f"[SETTINGS] Setting updated: {key} = {value}")
            return True
    except Exception as e:
        logger.error(f"[SETTINGS] Failed to set setting '{key}': {e}")
        return False
