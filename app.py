import os
import sqlite3
import secrets
import string
import time
import logging
from datetime import datetime
from functools import wraps
from flask import Flask, request, render_template, redirect, url_for, jsonify, session, send_file, flash
from difflib import SequenceMatcher

# ===== LOGGING CONFIGURATION =====
# For Render.com (cloud), logs go to stdout
# For local dev, logs go to both file and console
if os.environ.get('RENDER'):
    # Production on Render - log to stdout only
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.StreamHandler()]
    )
    logger = logging.getLogger(__name__)
    logger.info("="*50)
    logger.info("FAMILY FEUD - SERVER STARTING (RENDER)")
    logger.info("="*50)
else:
    # Local development - log to file and console
    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Create log filename with timestamp
    log_filename = datetime.now().strftime('%Y-%m-%d_%H-%M-%S.log')
    log_filepath = os.path.join(LOG_DIR, log_filename)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler(log_filepath),
            logging.StreamHandler()  # Also print to console
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # Log startup
    logger.info("="*50)
    logger.info("FAMILY FEUD - SERVER STARTING")
    logger.info(f"Log file: {log_filepath}")
    logger.info("NEW LOG FILE CREATED - Each server start creates a fresh log")
    logger.info("Previous logs are preserved in the /logs folder")
    logger.info("="*50)

app = Flask(__name__)
# Use environment variable for secret key in production, generate random for local dev
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Generate unique startup ID - changes on EVERY server restart
# This ensures old sessions are invalidated when server restarts
# SERVER RESTART = FRESH START (no data persistence)
STARTUP_ID = str(int(time.time() * 1000000))  # Unique timestamp
logger.info(f"Server startup ID: {STARTUP_ID}")
logger.info("All sessions from previous server runs are now invalid")

# Reset counter - increments when host clicks "Reset All" button
# This invalidates all team sessions without restarting server
RESET_COUNTER = 0
logger.info(f"Reset counter initialized: {RESET_COUNTER}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "feud.db")

# Host PIN protection - set via environment variable or use default
HOST_PIN = os.environ.get('HOST_PIN', '6551')
logger.info(f"Host PIN protection enabled (PIN: {'custom' if os.environ.get('HOST_PIN') else 'default 6551'})")

def host_required(f):
    """Decorator to protect host routes - requires PIN authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('host_authenticated'):
            return redirect(url_for('host_login'))
        return f(*args, **kwargs)
    return decorated_function

def team_session_valid(f):
    """Decorator to validate team session - checks startup_id and reset_counter"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # CRITICAL: Check reset_counter and startup_id BEFORE checking if session exists
        # This ensures Game Over page shows even if session was cleared
        
        # Check if startup_id in session matches current server startup
        # If server restarted, STARTUP_ID changes = all old sessions invalid
        session_startup_id = session.get('startup_id')
        
        if session_startup_id is not None and session_startup_id != STARTUP_ID:
            # Server was restarted - show game over page
            logger.info(f"Team session invalid - server restarted (session startup_id: {session_startup_id}, current: {STARTUP_ID})")
            session.clear()
            return render_template('game_over.html', reason='server_restart')
        
        # Check if reset_counter matches (Reset All button invalidates sessions)
        session_reset_counter = session.get('reset_counter', 0)
        
        if session_reset_counter != RESET_COUNTER:
            # Game was reset - show game over page
            logger.info(f"Team session invalid - game was reset (session counter: {session_reset_counter}, current: {RESET_COUNTER})")
            session.clear()
            return render_template('game_over.html', reason='game_reset')
        
        # NOW check if team has a session (after checking reset/restart)
        if 'code' not in session:
            logger.info("No team session found - redirecting to join")
            return redirect(url_for('join'))
        
        return f(*args, **kwargs)
    return decorated_function

# Game configuration - 8 rounds
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

def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # Production SQLite settings for concurrent writes
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def generate_team_code():
    """Generate 4-letter code like BAJK (no numbers for easier mobile typing)"""
    # Only uppercase letters, excluding confusing ones (I, O look like 1, 0)
    chars = string.ascii_uppercase.replace('I', '').replace('O', '')
    return ''.join(secrets.choice(chars) for _ in range(4))

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
        
        conn.commit()
        
        logger.info("Database tables initialized")
        
        # Migration: Add checked_answers column if it doesn't exist
        try:
            conn.execute("SELECT checked_answers FROM submissions LIMIT 1")
        except:
            logger.info("Adding checked_answers column to submissions table...")
            conn.execute("ALTER TABLE submissions ADD COLUMN checked_answers TEXT")
            conn.commit()
            logger.info("Migration complete: checked_answers column added")
        
        # Migration: Add submissions_closed column to rounds table if it doesn't exist
        try:
            conn.execute("SELECT submissions_closed FROM rounds LIMIT 1")
        except:
            logger.info("Adding submissions_closed column to rounds table...")
            conn.execute("ALTER TABLE rounds ADD COLUMN submissions_closed INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Migration complete: submissions_closed column added")
        
        # Migration: Add previous_score column to submissions table if it doesn't exist
        try:
            conn.execute("SELECT previous_score FROM submissions LIMIT 1")
        except:
            logger.info("Adding previous_score column to submissions table...")
            conn.execute("ALTER TABLE submissions ADD COLUMN previous_score INTEGER DEFAULT NULL")
            conn.commit()
            logger.info("Migration complete: previous_score column added")
        
        # Migration: Add last_heartbeat column to team_codes table (v1.1.0)
        try:
            conn.execute("SELECT last_heartbeat FROM team_codes LIMIT 1")
        except:
            logger.info("Adding last_heartbeat column to team_codes table...")
            conn.execute("ALTER TABLE team_codes ADD COLUMN last_heartbeat TIMESTAMP DEFAULT NULL")
            conn.commit()
            logger.info("Migration complete: last_heartbeat column added")
        
        # Migration: Add reconnected column to team_codes table (v1.1.0)
        try:
            conn.execute("SELECT reconnected FROM team_codes LIMIT 1")
        except:
            logger.info("Adding reconnected column to team_codes table...")
            conn.execute("ALTER TABLE team_codes ADD COLUMN reconnected INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Migration complete: reconnected column added")
        
        # Migration: Add winner_code column to rounds table (v1.1.0)
        try:
            conn.execute("SELECT winner_code FROM rounds LIMIT 1")
        except:
            logger.info("Adding winner_code column to rounds table...")
            conn.execute("ALTER TABLE rounds ADD COLUMN winner_code TEXT DEFAULT NULL")
            conn.commit()
            logger.info("Migration complete: winner_code column added")
        
        # Initialize default settings if they don't exist
        default_settings = [
            ('allow_team_registration', 'true', 'Allow new teams to join'),
            ('system_paused', 'false', 'System pause status'),
            ('broadcast_message', '', 'Broadcast message to all teams'),
            ('server_sleep', 'false', 'Server sleep mode - stops auto-refresh')
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
    logger.info("="*50)
    logger.info("🔥 NUCLEAR RESET ON SERVER STARTUP 🔥")
    logger.info("Clearing ALL game data for fresh start...")
    logger.info("="*50)
    
    with db_connect() as conn:
        # DELETE EVERYTHING
        conn.execute("DELETE FROM submissions")
        conn.execute("DELETE FROM rounds")
        conn.execute("UPDATE team_codes SET used = 0, team_name = NULL")
        conn.commit()
    
    logger.info("✅ ALL DATA CLEARED - Server is FRESH")
    logger.info("✅ All teams must join again")
    logger.info("✅ All old sessions are DEAD")
    logger.info("="*50)

init_db()
nuke_all_data()  # NUKE EVERYTHING on every server start

# ============= SETTINGS HELPERS =============

def get_setting(key, default=None):
    """Get a setting value from database, return default if not found"""
    try:
        with db_connect() as conn:
            result = conn.execute(
                "SELECT value FROM settings WHERE key = ?", 
                (key,)
            ).fetchone()
            return result['value'] if result else default
    except Exception as e:
        logger.warning(f"Failed to get setting '{key}': {e}")
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
            logger.info(f"Setting updated: {key} = {value}")
            return True
    except Exception as e:
        logger.error(f"Failed to set setting '{key}': {e}")
        return False

# ============= HELPERS =============

def similar(a, b):
    """Check if answers are similar (for auto-checking)"""
    if not a or not b:
        return False
    a = a.lower().strip()
    b = b.lower().strip()
    if a == b:
        return True
    if SequenceMatcher(None, a, b).ratio() > 0.9:
        return True
    return False

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

# ============= HOST ROUTES =============

@app.route('/')
def index():
    return redirect(url_for('host_dashboard'))

@app.route('/host/login', methods=['GET', 'POST'])
def host_login():
    """Host login page - PIN authentication"""
    if request.method == 'POST':
        pin = request.form.get('pin', '')
        if pin == HOST_PIN:
            session['host_authenticated'] = True
            logger.info("Host authenticated successfully")
            return redirect(url_for('host_dashboard'))
        else:
            logger.warning(f"Failed host login attempt with PIN: {pin}")
            return render_template('host_login.html', error=True)
    return render_template('host_login.html', error=False)

@app.route('/host/logout')
def host_logout():
    """Logout from host panel"""
    session.pop('host_authenticated', None)
    logger.info("Host logged out")
    return redirect(url_for('host_login'))

@app.route('/host')
@host_required
def host_dashboard():
    """Main host dashboard"""
    with db_connect() as conn:
        codes_raw = conn.execute("""
            SELECT code, used, team_name, reconnected, last_heartbeat 
            FROM team_codes 
            ORDER BY id DESC
        """).fetchall()
        
        # Process codes to add active status
        codes = []
        for code in codes_raw:
            code_dict = dict(code)
            # Calculate if team is active (heartbeat within last 30 seconds)
            if code['last_heartbeat']:
                from datetime import datetime, timedelta
                try:
                    # Parse timestamp
                    last_hb = datetime.fromisoformat(code['last_heartbeat'])
                    now = datetime.now()
                    time_diff = (now - last_hb).total_seconds()
                    code_dict['is_active'] = time_diff < 30
                except:
                    code_dict['is_active'] = False
            else:
                code_dict['is_active'] = False
            codes.append(code_dict)
        
        rounds = conn.execute("SELECT * FROM rounds ORDER BY round_number ASC").fetchall()
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()
        
        # Count unscored submissions for active round
        unscored_count = 0
        submission_count = 0
        if active_round:
            unscored_count = conn.execute("""
                SELECT COUNT(*) as cnt FROM submissions 
                WHERE round_id = ? AND scored = 0
            """, (active_round['id'],)).fetchone()['cnt']
            
            # Total submissions for active round
            submission_count = conn.execute("""
                SELECT COUNT(*) as cnt FROM submissions 
                WHERE round_id = ?
            """, (active_round['id'],)).fetchone()['cnt']
    
    return render_template('host.html', 
                         codes=codes,
                         rounds=[dict(r) for r in rounds],
                         active_round=dict(active_round) if active_round else None,
                         unscored_count=unscored_count,
                         submission_count=submission_count,
                         rounds_config=ROUNDS_CONFIG)

@app.route('/host/codes-status')
@host_required
def codes_status():
    """API endpoint - returns code statuses as JSON for auto-refresh"""
    logger.info("Codes status API called")
    with db_connect() as conn:
        codes = conn.execute("""
            SELECT code, used, team_name 
            FROM team_codes 
            ORDER BY id DESC
        """).fetchall()
        
        codes_data = []
        for code in codes:
            codes_data.append({
                'code': code['code'],
                'used': bool(code['used']),
                'team_name': code['team_name'] if code['team_name'] else None
            })
        
        used_count = sum(1 for c in codes_data if c['used'])
        
        logger.info(f"Codes status: {len(codes_data)} total, {used_count} used")
        
        return jsonify({
            'codes': codes_data,
            'total': len(codes_data),
            'used': used_count
        })

@app.route('/host/generate-codes', methods=['POST'])
@host_required
def generate_codes():
    """Generate 30 team codes"""
    count = 30
    with db_connect() as conn:
        generated = []
        for _ in range(count):
            for attempt in range(100):
                code = generate_team_code()
                try:
                    conn.execute("INSERT INTO team_codes (code, used) VALUES (?, 0)", (code,))
                    conn.commit()
                    generated.append(code)
                    break
                except sqlite3.IntegrityError:
                    continue
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Codes Generated</title>
        <style>
            body {{ 
                font-family: Arial; 
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: #ffd700;
                text-align: center;
                padding: 50px;
            }}
            .box {{
                background: #000;
                border: 3px solid #ffd700;
                padding: 40px;
                border-radius: 15px;
                max-width: 500px;
                margin: 0 auto;
            }}
            h1 {{ font-size: 3em; margin-bottom: 20px; }}
            button {{
                background: #ffd700;
                color: #000;
                border: none;
                padding: 20px 40px;
                font-size: 1.5em;
                font-weight: bold;
                border-radius: 10px;
                cursor: pointer;
                margin-top: 20px;
            }}
            button:hover {{ background: #ffed4e; }}
        </style>
    </head>
    <body>
        <div class="box">
            <h1>✅ Success!</h1>
            <p style="font-size: 1.5em;">{len(generated)} team codes generated!</p>
            <button onclick="window.location.href='/host'">Back to Dashboard</button>
        </div>
    </body>
    </html>
    """

@app.route('/host/reclaim-code/<code>', methods=['POST'])
@host_required
def reclaim_code(code):
    """Reclaim a used code - removes team and frees code for reuse"""
    code = code.upper()
    
    with db_connect() as conn:
        code_row = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()
        
        if not code_row:
            return jsonify({"success": False, "message": "Code not found"}), 404
        
        if not code_row['used']:
            return jsonify({"success": False, "message": "Code is not in use"}), 400
        
        team_name = code_row['team_name']
        
        # Delete all submissions for this team
        conn.execute("DELETE FROM submissions WHERE code = ?", (code,))
        
        # Reset the code (mark as unused, clear team name and reconnect flag)
        conn.execute("""
            UPDATE team_codes 
            SET used = 0, team_name = NULL, reconnected = 0, last_heartbeat = NULL 
            WHERE code = ?
        """, (code,))
        
        conn.commit()
        
        logger.info(f"Code reclaimed: {code} (was used by {team_name})")
        
        return jsonify({
            "success": True, 
            "message": f"Code {code} reclaimed. Team '{team_name}' removed."
        })

@app.route('/host/print-codes')
@host_required
def print_codes():
    """Generate HTML page with codes for printing"""
    with db_connect() as conn:
        codes = conn.execute("SELECT code FROM team_codes WHERE used = 0 ORDER BY id DESC LIMIT 25").fetchall()
    
    if not codes:
        return "No unused codes available. Generate codes first!", 400
    
    server_url = request.url_root + 'join'
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Team Codes</title>
        <style>
            body {{ font-family: Arial; margin: 0; padding: 20px; }}
            .grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }}
            .card {{ 
                border: 2px solid #000; 
                padding: 15px; 
                text-align: center;
                page-break-inside: avoid;
            }}
            .qr {{ margin: 10px 0; }}
            .code {{ 
                font-size: 24px; 
                font-weight: bold; 
                font-family: monospace;
                background: #ffd700;
                padding: 10px;
                margin: 10px 0;
            }}
            @media print {{
                .card {{ page-break-inside: avoid; }}
            }}
        </style>
    </head>
    <body>
        <h1>Family Feud - Team Codes (Cut & Hand to Tables)</h1>
        <p><strong>QR Code URL:</strong> {server_url}</p>
        <hr>
        <div class="grid">
    """
    
    for code_row in codes:
        code = code_row['code']
        html += f"""
            <div class="card">
                <div style="font-weight: bold;">Scan to Join:</div>
                <div class="qr">
                    <img src="https://api.qrserver.com/v1/create-qr-code/?size=120x120&data={server_url}" alt="QR">
                </div>
                <div style="font-size: 12px;">Team Code:</div>
                <div class="code">{code}</div>
            </div>
        """
    
    html += """
        </div>
    </body>
    </html>
    """
    
    return html

@app.route('/host/print-codes-landscape')
@host_required
def print_codes_landscape():
    """Generate landscape HTML page with codes for printing - 12 codes per page"""
    with db_connect() as conn:
        # Get first 24 codes (2 pages of 12)
        codes = conn.execute("SELECT code FROM team_codes ORDER BY id LIMIT 24").fetchall()
    
    if not codes:
        return "No codes available. Generate codes first!", 400
    
    if len(codes) < 24:
        # Pad with empty slots if less than 24 codes
        while len(codes) < 24:
            codes.append({'code': ''})
    
   # Get QR base URL from settings
    # Check for QR_BASE_URL environment variable first
    qr_url_from_env = os.environ.get('QR_BASE_URL')
    if qr_url_from_env:
        default_url = qr_url_from_env
    elif os.environ.get('RENDER'):
        default_url = 'https://pubfeud.gamenightguild.net'
    else:
        default_url = 'http://localhost:5000'
    
    qr_base_url = get_setting('qr_base_url', default_url)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Team Codes - Landscape</title>
        <style>
            @page {{
                size: 11in 8.5in landscape;
                margin: 0.25in;
            }}
            
            * {{
                box-sizing: border-box;
            }}
            
            body {{ 
                font-family: Arial; 
                margin: 0; 
                padding: 0;
            }}
            
            .page {{
                width: 100%;
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                grid-template-rows: repeat(3, 1fr);
                gap: 0;
                min-height: 7.5in;
            }}
            
            .page:first-child {{
                page-break-after: always;
            }}
            
            .card {{ 
                border: 1px dashed #000; 
                padding: 15px; 
                text-align: center;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
            }}
            
            .card.empty {{
                visibility: hidden;
            }}
            
            .code-header {{
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            
            .code-number {{
                font-size: 14px;
                color: #666;
            }}
            
            .qr {{ 
                margin: 10px 0;
            }}
            
            .qr img {{
                width: 150px;
                height: 150px;
            }}
            
            .instruction {{ 
                font-size: 12px;
                margin-top: 10px;
                line-height: 1.4;
            }}
            
            @media print {{
                body {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
                .page {{
                    page-break-inside: avoid;
                }}
            }}
        </style>
    </head>
    <body>
    """
    
    # Generate 2 pages (12 codes each)
    for page_num in range(2):
        html += '<div class="page">'
        
        start_idx = page_num * 12
        end_idx = start_idx + 12
        page_codes = codes[start_idx:end_idx]
        
        for slot_num, code_row in enumerate(page_codes, start=start_idx + 1):
            code = code_row['code']
            
            if code:  # Only show card if code exists
                # QR code points to /join page only (team must enter code manually)
                qr_url = f"{qr_base_url}/join"
                
                html += f"""
            <div class="card">
                <div class="code-header">
                    CODE: <strong>{code}</strong>
                    <span class="code-number">#{slot_num}</span>
                </div>
                <div class="qr">
                    <img src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={qr_url}" alt="QR Code">
                </div>
                <div class="instruction">
                    Scan the Code to Join<br>
                    and Enter the Code.
                </div>
            </div>
            """
            else:
                # Empty slot
                html += '<div class="card empty"></div>'
        
        html += '</div>'  # Close page
    
    html += """
    </body>
    </html>
    """
    
    return html

def parse_pptx(filepath):
    """Parse PowerPoint file and extract questions/answers
    
    IMPROVED VERSION - Handles text boxes with answer/count pairs
    Correctly distinguishes rank indicators (1,2,3) from answer counts (10,20,43)
    """
    from pptx import Presentation
    
    prs = Presentation(filepath)
    slides = list(prs.slides)
    
    rounds_data = []
    
    # Strategy: Find question slides, then parse the next slide as answers
    i = 0
    while i < len(slides):
        slide = slides[i]
        
        # Extract all text from current slide
        all_text = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text = shape.text.strip()
                if text:
                    all_text.append(text)
        
        # Check if this is a question slide
        is_question_slide = False
        question_text = ""
        
        for text in all_text:
            # Look for question markers
            if 'Survey Has' in text and 'Responses' in text:
                is_question_slide = True
            # Extract actual question (not the metadata)
            elif len(text) > 10 and 'Round #' not in text and 'Survey Has' not in text:
                if not question_text:  # Take first substantial text
                    question_text = text
        
        if is_question_slide and i + 1 < len(slides):
            # Next slide should have answers
            answer_slide = slides[i + 1]
            answers = []
            
            # Extract all text from answer slide
            answer_text_elements = []
            for shape in answer_slide.shapes:
                if hasattr(shape, "text"):
                    text = shape.text.strip()
                    if text:
                        answer_text_elements.append(text)
            
            # Parse answer/count pairs from text
            j = 0
            while j < len(answer_text_elements):
                text = answer_text_elements[j]
                
                # Skip UI elements
                skip_keywords = ['Round:', 'ROUND', 'Score Multiplier:', 'BACK TO SCORES', 
                               'NEXT ROUND', 'And The Survey Says', 'X', '«', '»',
                               'type only', '(type', 'Click', 'Press']
                
                if any(keyword in text for keyword in skip_keywords):
                    j += 1
                    continue
                
                # Skip rank indicators (single-digit numbers 1-8)
                if text.isdigit() and len(text) <= 2 and int(text) <= 8:
                    j += 1
                    continue
                
                # If it's text (potential answer), look for count
                if not text.isdigit() and len(text) > 1:
                    answer_text = text
                    count = 0
                    
                    # Look ahead for count
                    if j + 1 < len(answer_text_elements):
                        next_text = answer_text_elements[j + 1]
                        if next_text.isdigit():
                            try:
                                count_value = int(next_text)
                                # Count numbers are typically 5+ (answer counts, not ranks)
                                # But also accept low counts (some answers might have count of 1-4)
                                # The key is: if we just read answer text, next number IS the count
                                if count_value > 0:
                                    answers.append({'answer': answer_text, 'count': count_value})
                                    j += 1  # Skip the count
                            except ValueError:
                                pass
                
                j += 1
            
            # Add round if we found answers
            if answers:
                rounds_data.append({
                    'question': question_text,
                    'answers': answers
                })
            
            # Skip the answer slide
            i += 2
        else:
            i += 1
    
    return rounds_data

@app.route('/host/upload-answers', methods=['POST'])
@host_required
def upload_answers():
    """Upload DOCX or PPTX answer sheet and auto-create all rounds"""
    try:
        if 'file' not in request.files:
            flash('No file uploaded!', 'error')
            return redirect(url_for('host_dashboard'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected!', 'error')
            return redirect(url_for('host_dashboard'))
        
        # Accept .docx, .pptx, and .pptm files
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ['.docx', '.pptx', '.pptm']:
            flash('Please upload a .docx, .pptx, or .pptm file!', 'error')
            return redirect(url_for('host_dashboard'))
        
        # Save temp file
        temp_path = os.path.join(BASE_DIR, f'temp_answers_{int(time.time())}{file_ext}')
        file.save(temp_path)
        
        # Parse based on file type
        rounds_data = []
        
        if file_ext == '.docx':
            # DOCX parsing (existing code)
            from docx import Document
            doc = Document(temp_path)
            
            # ROBUST: Extract questions with flexible matching (handles both - and – dashes)
            questions = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text and len(text) > 0 and text[0].isdigit():
                    # Match both regular dash (-) and em-dash (–)
                    if '-' in text or '–' in text:
                        # Split on either dash type
                        separator = '–' if '–' in text else '-'
                        parts = text.split(separator, 1)
                        if len(parts) > 1:
                            question = parts[1].strip()
                            questions.append(question)
            
            # ROBUST: Parse ALL 8 tables regardless of question count
            for table_idx, table in enumerate(doc.tables):
                if table_idx >= 8:
                    break
                    
                answers = []
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    if len(cells) >= 3:
                        # Skip header rows - only process if first cell is a number (rank)
                        if not cells[0] or not cells[0].strip().isdigit():
                            continue
                        
                        answer = cells[1]
                        points_count = cells[2]
                        
                        # ROBUST: Flexible count parsing (handles various spacing)
                        count = 0
                        if points_count:
                            # Try both dash types
                            for separator in ['-', '–']:
                                if separator in points_count:
                                    parts = points_count.split(separator)
                                    if len(parts) > 1:
                                        try:
                                            # Extract just the digits from the second part
                                            count_str = ''.join(filter(str.isdigit, parts[1]))
                                            if count_str:
                                                count = int(count_str)
                                            break
                                        except ValueError:
                                            count = 0
                        
                        answers.append({'answer': answer, 'count': count})
                
                # Use question by index, or empty string if not found
                question = questions[table_idx] if table_idx < len(questions) else ''
                
                rounds_data.append({
                    'question': question,
                    'answers': answers
                })
        
        elif file_ext in ['.pptx', '.pptm']:
            # PowerPoint parsing (new code)
            rounds_data = parse_pptx(temp_path)
        
        # Always create all rounds found (should be 8)
        with db_connect() as conn:
            conn.execute("DELETE FROM rounds")
            conn.execute("DELETE FROM submissions")
            
            for idx, round_data in enumerate(rounds_data):
                round_num = idx + 1
                config = ROUNDS_CONFIG[idx]
                num_answers = config['answers']
                
                fields = ['round_number', 'question', 'num_answers', 'is_active']
                values = [round_num, round_data['question'], num_answers, 0]
                
                for i in range(1, num_answers + 1):
                    if i <= len(round_data['answers']):
                        fields.append(f'answer{i}')
                        fields.append(f'answer{i}_count')
                        values.append(round_data['answers'][i-1]['answer'])
                        values.append(round_data['answers'][i-1]['count'])
                
                placeholders = ','.join(['?'] * len(values))
                conn.execute(f"INSERT INTO rounds ({','.join(fields)}) VALUES ({placeholders})", values)
            
            conn.commit()
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        rounds_created = len(rounds_data)
        flash(f'✅ Success! {rounds_created} rounds created!', 'success')
        return redirect(url_for('host_dashboard'))
        
    except FileNotFoundError as e:
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass
        flash(f'❌ File error: Could not read the uploaded file. Please try again.', 'error')
        return redirect(url_for('host_dashboard'))
    except ImportError as e:
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass
        flash(f'❌ Missing library: {str(e)}. Please install required dependencies.', 'error')
        return redirect(url_for('host_dashboard'))
    except Exception as e:
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass
        
        # Provide helpful error messages based on the error type
        error_msg = str(e)
        if 'pptx' in error_msg.lower() or 'presentation' in error_msg.lower():
            flash(f'❌ PowerPoint parsing error: The file format may be corrupted or unsupported. Details: {error_msg}', 'error')
        elif 'docx' in error_msg.lower() or 'document' in error_msg.lower():
            flash(f'❌ Word document parsing error: The file format may be corrupted. Details: {error_msg}', 'error')
        elif 'table' in error_msg.lower():
            flash(f'❌ Table parsing error: Could not read answer tables. Make sure your file has the correct format. Details: {error_msg}', 'error')
        else:
            flash(f'❌ Upload failed: {error_msg}', 'error')
        
        return redirect(url_for('host_dashboard'))

@app.route('/host/round/create', methods=['POST'])
@host_required
def create_round():
    """Create a round manually"""
    round_num = int(request.form.get('round_number'))
    question = request.form.get('question', '').strip()
    
    config = next((r for r in ROUNDS_CONFIG if r['round'] == round_num), None)
    if not config:
        return "Invalid round number", 400
    
    with db_connect() as conn:
        conn.execute("UPDATE rounds SET is_active = 0")
        conn.execute("""
            INSERT INTO rounds (round_number, question, num_answers, is_active)
            VALUES (?, ?, ?, 1)
        """, (round_num, question, config['answers']))
        conn.commit()
    
    return redirect(url_for('host_dashboard'))

@app.route('/host/round/<int:round_id>/activate', methods=['POST'])
@host_required
def activate_round(round_id):
    """Activate a specific round"""
    with db_connect() as conn:
        # CRITICAL FIX: Validate that round has answers before activating
        round_data = conn.execute(
            "SELECT answer1, question FROM rounds WHERE id = ?", 
            (round_id,)
        ).fetchone()
        
        if not round_data:
            flash('❌ Round not found!', 'error')
            return redirect(url_for('host_dashboard'))
        
        if not round_data['answer1']:
            flash('❌ Cannot activate round without answers! Please set answers first.', 'error')
            return redirect(url_for('host_dashboard'))
        
        # CRITICAL FIX: Use transaction to prevent race conditions
        # Deactivate ALL rounds, then activate the selected one atomically
        conn.execute("BEGIN IMMEDIATE")  # Lock database to prevent race conditions
        try:
            conn.execute("UPDATE rounds SET is_active = 0")
            conn.execute("UPDATE rounds SET is_active = 1 WHERE id = ?", (round_id,))
            conn.commit()
            flash(f'✅ Round activated: {round_data["question"]}', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'❌ Error activating round: {str(e)}', 'error')
    
    return redirect(url_for('host_dashboard'))

@app.route('/host/round/<int:round_id>/answers', methods=['POST'])
@host_required
def set_answers(round_id):
    """Set correct answers for a round"""
    with db_connect() as conn:
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
        num_answers = round_info['num_answers']
        
        fields = []
        values = []
        for i in range(1, 7):
            if i <= num_answers:
                fields.append(f'answer{i} = ?')
                if i == 1:
                    fields.append(f'answer{i}_count = ?')
                    values.append(request.form.get(f'answer{i}', '').strip())
                    values.append(int(request.form.get(f'answer{i}_count', 0) or 0))
                else:
                    values.append(request.form.get(f'answer{i}', '').strip())
        
        values.append(round_id)
        conn.execute(f"UPDATE rounds SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    
    return redirect(url_for('host_dashboard'))

@app.route('/host/scoring-queue')
@host_required
def scoring_queue():
    """Manual scoring page - shows unscored submissions"""
    with db_connect() as conn:
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()
        
        if not active_round:
            flash('No active round!', 'error'); return redirect(url_for('host_dashboard'))
        
        # Get unscored submissions
        submissions = conn.execute("""
            SELECT s.*, tc.team_name
            FROM submissions s
            JOIN team_codes tc ON s.code = tc.code
            WHERE s.round_id = ? AND s.scored = 0
            ORDER BY s.submitted_at ASC
        """, (active_round['id'],)).fetchall()
        
        submissions_data = []
        for sub in submissions:
            sub_dict = dict(sub)
            sub_dict['time_ago'] = time_ago(sub['submitted_at'])
            sub_dict['submitted_time'] = format_timestamp(sub['submitted_at'])
            
            # Auto-check matches regardless of position
            auto_checks = {}
            for i in range(1, active_round['num_answers'] + 1):
                correct_answer = active_round[f'answer{i}']
                auto_checks[i] = False  # Default to unchecked
                
                # Search through ALL their submitted answers
                if correct_answer:
                    for j in range(1, active_round['num_answers'] + 1):
                        their_answer = sub[f'answer{j}']
                        if their_answer and similar(their_answer, correct_answer):
                            auto_checks[i] = True  # Found a match!
                            break  # Stop searching for this correct answer
            
            sub_dict['auto_checks'] = auto_checks
            submissions_data.append(sub_dict)
    
    return render_template('scoring_queue.html',
                         round=dict(active_round),
                         submissions=submissions_data)

@app.route('/host/check-active-round')
@host_required
def check_active_round():
    """API endpoint to check if there's an active round (for AJAX polling)"""
    with db_connect() as conn:
        active_round = conn.execute("SELECT id FROM rounds WHERE is_active = 1").fetchone()
        return jsonify({'has_active_round': active_round is not None})

@app.route('/host/count-unscored')
@host_required
def count_unscored():
    """API endpoint to get count of unscored submissions"""
    with db_connect() as conn:
        active_round = conn.execute("SELECT id FROM rounds WHERE is_active = 1").fetchone()
        
        if not active_round:
            return jsonify({'count': 0})
        
        count = conn.execute("""
            SELECT COUNT(*) as cnt FROM submissions 
            WHERE round_id = ? AND scored = 0
        """, (active_round['id'],)).fetchone()['cnt']
        
        return jsonify({'count': count})

@app.route('/host/score-team/<int:submission_id>', methods=['POST'])
@host_required
def score_team(submission_id):
    """Submit score for a single team"""
    checked_answers = []
    for key in request.form:
        if key.startswith('answer_'):
            checked_answers.append(int(key.split('_')[1]))
    
    with db_connect() as conn:
        submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)).fetchone()
        
        # Get team name
        team_info = conn.execute("SELECT team_name FROM team_codes WHERE code = ?", (submission['code'],)).fetchone()
        team_name = team_info['team_name'] if team_info else 'Unknown Team'
        
        # Calculate score based on checked boxes
        score = 0
        for ans_num in checked_answers:
            points = round_info['num_answers'] - ans_num + 1
            score += points
        
        # Store which answers were checked (e.g., "1,3,5")
        checked_answers_str = ','.join(map(str, sorted(checked_answers))) if checked_answers else ''
        
        # Store current score as previous_score before updating (for undo functionality)
        current_score = submission['score']
        
        # Update submission with new score and save previous
        conn.execute("""
            UPDATE submissions 
            SET score = ?, scored = 1, scored_at = CURRENT_TIMESTAMP, checked_answers = ?, previous_score = ?
            WHERE id = ?
        """, (score, checked_answers_str, current_score, submission_id))
        conn.commit()
        
        # Check if all submissions for this round are scored
        total_subs = conn.execute("SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ?", 
                                   (submission['round_id'],)).fetchone()['cnt']
        scored_subs = conn.execute("SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ? AND scored = 1", 
                                    (submission['round_id'],)).fetchone()['cnt']
        
        # If all scored, find winner and update round
        if total_subs > 0 and scored_subs == total_subs:
            winner = conn.execute("""
                SELECT code, score FROM submissions 
                WHERE round_id = ? 
                ORDER BY score DESC, tiebreaker DESC 
                LIMIT 1
            """, (submission['round_id'],)).fetchone()
            
            if winner:
                conn.execute("UPDATE rounds SET winner_code = ? WHERE id = ?", 
                           (winner['code'], submission['round_id']))
                conn.commit()
                logger.info(f"Round {submission['round_id']} winner: {winner['code']} with {winner['score']} points")
    
    # Check if AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return JSON for AJAX
        return jsonify({
            'success': True,
            'score': score,
            'team_name': team_name
        })
    else:
        # Traditional form submit (fallback)
        flash(f'{team_name} scored {score} points!', 'success')
        return redirect(url_for('scoring_queue'))

@app.route('/host/undo-score/<int:submission_id>', methods=['POST'])
@host_required
def undo_score(submission_id):
    """Undo the last score for a submission"""
    with db_connect() as conn:
        submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        
        if not submission:
            return jsonify({"success": False, "message": "Submission not found"}), 404
        
        if submission['previous_score'] is None:
            return jsonify({"success": False, "message": "No previous score to restore"}), 400
        
        # Get team name
        team_info = conn.execute("SELECT team_name FROM team_codes WHERE code = ?", (submission['code'],)).fetchone()
        team_name = team_info['team_name'] if team_info else 'Unknown Team'
        
        # Restore previous score
        previous_score = submission['previous_score']
        conn.execute("""
            UPDATE submissions 
            SET score = ?, previous_score = NULL
            WHERE id = ?
        """, (previous_score, submission_id))
        conn.commit()
        
        logger.info(f"Undo score: {team_name} reverted from {submission['score']} to {previous_score}")
        
        return jsonify({
            "success": True,
            "message": f"{team_name}'s score restored to {previous_score}",
            "new_score": previous_score
        })

@app.route('/host/round-summary')
@host_required
def round_summary():
    """Show round summary after all teams scored"""
    logger.info("="*50)
    logger.info("ROUND SUMMARY REQUESTED")
    try:
        with db_connect() as conn:
            active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()
            
            if not active_round:
                logger.warning("No active round found")
                flash('No active round!', 'error'); return redirect(url_for('host_dashboard'))
            
            logger.info(f"Active Round: {active_round['round_number']}, ID: {active_round['id']}")
            logger.info(f"Question: {active_round['question']}")
            logger.info(f"Answer #1: {active_round['answer1']}, Count: {active_round['answer1_count']}")
            
            # Get all scored submissions for this round
            submissions = conn.execute("""
                SELECT s.*, tc.team_name
                FROM submissions s
                JOIN team_codes tc ON s.code = tc.code
                WHERE s.round_id = ? AND s.scored = 1
                ORDER BY s.score DESC, 
                         ABS(COALESCE(s.tiebreaker, 0) - ?) ASC,
                         s.submitted_at ASC
            """, (active_round['id'], active_round['answer1_count'] or 0)).fetchall()
            
            if not submissions:
                logger.warning("No scored teams found")
                flash('No scored teams yet!', 'warning'); return redirect(url_for('scoring_queue'))
            
            logger.info(f"Found {len(submissions)} scored teams")
            for i, sub in enumerate(submissions):
                logger.info(f"  {i+1}. {sub['team_name']} ({sub['code']}) - Score: {sub['score']}, TB: {sub['tiebreaker']}")
            
            # Get winner (first in sorted list)
            winner = dict(submissions[0])
            
            # Check if there was a tie
            tied = False
            tiebreaker_info = None
            ultimate_tie = False
            
            if len(submissions) > 1:
                second = submissions[1]
                if winner['score'] == second['score']:
                    tied = True
                    logger.info(f"TIE DETECTED! Both teams have {winner['score']} points")
                    actual_count = active_round['answer1_count'] or 0
                    winner_diff = abs((winner['tiebreaker'] or 0) - actual_count)
                    second_diff = abs((second['tiebreaker'] or 0) - actual_count)
                    
                    logger.info(f"  Winner TB: {winner['tiebreaker']}, Diff: {winner_diff}")
                    logger.info(f"  Second TB: {second['tiebreaker']}, Diff: {second_diff}")
                    logger.info(f"  Actual count: {actual_count}")
                    
                    # Check if tiebreaker guesses are also the same
                    if winner_diff == second_diff:
                        ultimate_tie = True
                        logger.info("ULTIMATE TIE! Same score AND same tiebreaker difference!")
                        logger.info(f"  Winner submitted: {winner['submitted_at']}")
                        logger.info(f"  Second submitted: {second['submitted_at']}")
                        
                        # Calculate time difference
                        try:
                            winner_time = datetime.strptime(winner['submitted_at'], '%Y-%m-%d %H:%M:%S')
                            second_time = datetime.strptime(second['submitted_at'], '%Y-%m-%d %H:%M:%S')
                            time_diff_seconds = abs((winner_time - second_time).total_seconds())
                            logger.info(f"  Time difference: {time_diff_seconds} seconds")
                        except:
                            time_diff_seconds = 0
                        
                        tiebreaker_info = {
                            'winner_guess': winner['tiebreaker'] or 0,
                            'second_guess': second['tiebreaker'] or 0,
                            'actual_count': actual_count,
                            'difference': (winner['tiebreaker'] or 0) - actual_count,
                            'tied_score': winner['score'],
                            'ultimate_tie': True,
                            'winner_time': format_timestamp(winner['submitted_at']),
                            'second_time': format_timestamp(second['submitted_at']),
                            'second_name': second['team_name'],
                            'time_diff_seconds': int(time_diff_seconds)
                        }
                    else:
                        # Regular tiebreaker (different guesses)
                        tiebreaker_info = {
                            'winner_guess': winner['tiebreaker'] or 0,
                            'actual_count': actual_count,
                            'difference': (winner['tiebreaker'] or 0) - actual_count,
                            'tied_score': winner['score'],
                            'ultimate_tie': False
                        }
                else:
                    logger.info(f"Clear winner: {winner['team_name']} with {winner['score']} points")
        
        logger.info("Round summary generated successfully")
        logger.info("="*50)
        return render_template('round_summary.html',
                             round=dict(active_round),
                             winner=winner,
                             tied=tied,
                             tiebreaker_info=tiebreaker_info,
                             total_teams=len(submissions))
    except Exception as e:
        logger.error("="*50)
        logger.error(f"ERROR in round_summary(): {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        logger.error("="*50)
        flash(f'Error loading summary: {str(e)}', 'error'); return redirect(url_for('host_dashboard'))

@app.route('/host/start-next-round', methods=['POST'])
@host_required
def start_next_round():
    """Move to next round"""
    with db_connect() as conn:
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()
        
        if active_round:
            current_num = active_round['round_number']
            # Deactivate current
            conn.execute("UPDATE rounds SET is_active = 0 WHERE id = ?", (active_round['id'],))
            
            # Activate next round
            next_round = conn.execute("""
                SELECT * FROM rounds WHERE round_number = ?
            """, (current_num + 1,)).fetchone()
            
            if next_round:
                conn.execute("UPDATE rounds SET is_active = 1 WHERE id = ?", (next_round['id'],))
                conn.commit()
            else:
                # No more rounds - game over
                conn.commit()
                flash('All rounds complete!', 'info'); return redirect(url_for('host_dashboard'))
        
        conn.commit()
    
    return redirect(url_for('host_dashboard'))

@app.route('/host/scored-teams')
@host_required
def scored_teams():
    """View all scored teams"""
    with db_connect() as conn:
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()
        
        if not active_round:
            flash('No active round!', 'error'); return redirect(url_for('host_dashboard'))
        
        submissions = conn.execute("""
            SELECT s.*, tc.team_name
            FROM submissions s
            JOIN team_codes tc ON s.code = tc.code
            WHERE s.round_id = ? AND s.scored = 1
            ORDER BY s.score DESC, 
                     ABS(COALESCE(s.tiebreaker, 0) - ?) ASC
        """, (active_round['id'], active_round['answer1_count'] or 0)).fetchall()
        
        # Add formatted timestamps
        submissions_data = []
        for sub in submissions:
            sub_dict = dict(sub)
            sub_dict['submitted_time'] = format_timestamp(sub['submitted_at'])
            submissions_data.append(sub_dict)
    
    return render_template('scored_teams.html',
                         round=dict(active_round),
                         submissions=submissions_data)

@app.route('/host/edit-score/<int:submission_id>')
@host_required
def edit_score(submission_id):
    """Edit an already-scored submission"""
    with db_connect() as conn:
        submission = conn.execute("""
            SELECT s.*, tc.team_name
            FROM submissions s
            JOIN team_codes tc ON s.code = tc.code
            WHERE s.id = ?
        """, (submission_id,)).fetchone()
        
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)).fetchone()
        
        # Use stored checked_answers if available
        checked_set = set()
        if submission['checked_answers']:
            # Parse "1,3,5" into set {1, 3, 5}
            checked_set = set(map(int, submission['checked_answers'].split(',')))
        else:
            # Fallback: Figure out which answers should be checked by similarity
            for i in range(1, round_info['num_answers'] + 1):
                correct_answer = round_info[f'answer{i}']
                
                # Search through ALL their submitted answers
                if correct_answer:
                    for j in range(1, round_info['num_answers'] + 1):
                        their_answer = submission[f'answer{j}']
                        if their_answer and similar(their_answer, correct_answer):
                            checked_set.add(i)
                            break
        
        # Convert to dict for template
        auto_checks = {i: (i in checked_set) for i in range(1, round_info['num_answers'] + 1)}
    
    return render_template('edit_score.html',
                         round=dict(round_info),
                         submission=dict(submission),
                         auto_checks=auto_checks)

@app.route('/host/update-score/<int:submission_id>', methods=['POST'])
@host_required
def update_score(submission_id):
    """Update score for edited submission"""
    checked_answers = []
    for key in request.form:
        if key.startswith('answer_'):
            checked_answers.append(int(key.split('_')[1]))
    
    # Get tiebreaker if provided
    tiebreaker = request.form.get('tiebreaker', type=int)
    
    with db_connect() as conn:
        submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (submission['round_id'],)).fetchone()
        
        # Store previous score before updating
        previous_score = submission['score'] if submission['score'] is not None else 0
        
        score = 0
        for ans_num in checked_answers:
            points = round_info['num_answers'] - ans_num + 1
            score += points
        
        # Store which answers were checked
        checked_answers_str = ','.join(map(str, sorted(checked_answers))) if checked_answers else ''
        
        # Update score, tiebreaker, checked_answers, and previous_score
        if tiebreaker is not None:
            conn.execute("UPDATE submissions SET score = ?, tiebreaker = ?, checked_answers = ?, previous_score = ? WHERE id = ?", 
                        (score, tiebreaker, checked_answers_str, previous_score, submission_id))
        else:
            conn.execute("UPDATE submissions SET score = ?, checked_answers = ?, previous_score = ? WHERE id = ?", 
                        (score, checked_answers_str, previous_score, submission_id))
        conn.commit()
    
    return redirect(url_for('scored_teams'))

@app.route('/host/revert-score/<int:submission_id>')
@host_required
def revert_score(submission_id):
    """Revert score to previous value"""
    with db_connect() as conn:
        submission = conn.execute("SELECT previous_score FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        
        if submission and submission['previous_score'] is not None:
            # Swap current and previous scores
            current_previous = submission['previous_score']
            conn.execute("UPDATE submissions SET score = ?, previous_score = score WHERE id = ?", 
                        (current_previous, submission_id))
            conn.commit()
    
    return redirect(url_for('scored_teams'))

@app.route('/host/manual-entry')
@host_required
def manual_entry():
    """Manual entry form for paper submissions"""
    with db_connect() as conn:
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()
        
        if not active_round:
            flash('No active round! Please activate a round first.', 'error')
            return redirect(url_for('host_dashboard'))
        
        # Get ALL codes (both used and unused)
        all_codes = conn.execute("""
            SELECT code, team_name, used FROM team_codes 
            ORDER BY code ASC
        """).fetchall()
    
    return render_template('manual_entry.html',
                         round=dict(active_round),
                         codes=all_codes)

@app.route('/host/manual-entry/submit', methods=['POST'])
@host_required
def manual_entry_submit():
    """Process manual paper submission"""
    code = request.form.get('code')
    team_name = request.form.get('team_name', '').strip()
    round_id = request.form.get('round_id')
    tiebreaker = int(request.form.get('tiebreaker', 0) or 0)
    
    if not code or not team_name:
        # Check if AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Please fill in all required fields!'}), 400
        else:
            flash('Please fill in all required fields!', 'error')
            return redirect(url_for('manual_entry'))
    
    with db_connect() as conn:
        # Mark code as used with team name
        conn.execute("UPDATE team_codes SET used = 1, team_name = ? WHERE code = ?", (team_name, code))
        
        # Get round info
        round_info = conn.execute("SELECT num_answers FROM rounds WHERE id = ?", (round_id,)).fetchone()
        num_answers = round_info['num_answers']
        
        # Collect answers
        answers = {f'answer{i}': request.form.get(f'answer{i}', '').strip() for i in range(1, num_answers + 1)}
        
        # Insert submission
        fields = ['code', 'round_id', 'tiebreaker'] + [f'answer{i}' for i in range(1, num_answers + 1)]
        placeholders = ', '.join(['?'] * len(fields))
        values = [code, round_id, tiebreaker] + [answers[f'answer{i}'] for i in range(1, num_answers + 1)]
        
        try:
            conn.execute(f"INSERT INTO submissions ({', '.join(fields)}) VALUES ({placeholders})", values)
            conn.commit()
        except sqlite3.IntegrityError:
            # Check if AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'This code has already submitted for this round!'}), 400
            else:
                flash('This code has already submitted for this round!', 'error')
                return redirect(url_for('manual_entry'))
    
    # Check if AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return JSON for AJAX
        return jsonify({
            'success': True,
            'team_name': team_name
        })
    else:
        # Traditional form submit (fallback)
        flash('✅ Manual entry submitted successfully!', 'success')
        return redirect(url_for('host_dashboard'))

@app.route('/host/round/<int:round_id>/edit-answer/<int:answer_num>')
@host_required
def edit_single_answer(round_id, answer_num):
    """Edit a single answer"""
    with db_connect() as conn:
        round_info = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
        
        if not round_info:
            flash('Round not found!', 'error'); return redirect(url_for('host_dashboard'))
        
        current_answer = round_info[f'answer{answer_num}']
        current_count = round_info['answer1_count'] if answer_num == 1 else None
    
    return render_template('edit_answer.html',
                         round=dict(round_info),
                         answer_num=answer_num,
                         current_answer=current_answer,
                         current_count=current_count)

@app.route('/host/round/<int:round_id>/update-answer/<int:answer_num>', methods=['POST'])
@host_required
def update_single_answer(round_id, answer_num):
    """Update a single answer"""
    new_answer = request.form.get('answer', '').strip()
    
    with db_connect() as conn:
        if answer_num == 1:
            new_count = int(request.form.get('count', 0) or 0)
            conn.execute("""
                UPDATE rounds 
                SET answer1 = ?, answer1_count = ?
                WHERE id = ?
            """, (new_answer, new_count, round_id))
        else:
            conn.execute(f"""
                UPDATE rounds 
                SET answer{answer_num} = ?
                WHERE id = ?
            """, (new_answer, round_id))
        
        conn.commit()
    
    flash('✅ Answer updated!', 'success'); return redirect(url_for('host_dashboard'))

@app.route('/host/create-round-manual')
@host_required
def create_round_manual_form():
    """Show manual round creation form"""
    return render_template('create_round_manual.html',
                         rounds_config=ROUNDS_CONFIG)

@app.route('/host/create-round-manual/submit', methods=['POST'])
@host_required
def create_round_manual_submit():
    """Process manual round creation for ALL 8 rounds"""
    try:
        with db_connect() as conn:
            # Delete any existing rounds and submissions
            conn.execute("DELETE FROM rounds")
            conn.execute("DELETE FROM submissions")
            
            # Create all 8 rounds
            for config in ROUNDS_CONFIG:
                round_num = config['round']
                num_answers = config['answers']
                
                # Get question for this round
                question = request.form.get(f'question{round_num}', '').strip()
                
                # Build insert for this round
                fields = ['round_number', 'question', 'num_answers', 'is_active']
                # Activate only Round 1
                is_active = 1 if round_num == 1 else 0
                values = [round_num, question, num_answers, is_active]
                
                # Get answers for this round
                for i in range(1, num_answers + 1):
                    answer = request.form.get(f'round{round_num}_answer{i}', '').strip()
                    fields.append(f'answer{i}')
                    values.append(answer)
                    
                    # Get count only for answer #1
                    if i == 1:
                        count = int(request.form.get(f'round{round_num}_answer1_count', 0) or 0)
                        fields.append(f'answer{i}_count')
                        values.append(count)
                
                # Insert this round
                placeholders = ','.join(['?'] * len(values))
                conn.execute(f"INSERT INTO rounds ({','.join(fields)}) VALUES ({placeholders})", values)
            
            conn.commit()
        
        flash('✅ All 8 rounds created! Round 1 is now active.', 'success'); return redirect(url_for('host_dashboard'))
        
    except Exception as e:
        flash(f'Error creating rounds: {str(e)}', 'error'); return redirect(url_for('host_dashboard'))


@app.route('/host/reset', methods=['POST'])
@host_required
def reset_game():
    """Reset game but keep codes and team names - for setup fixes"""
    with db_connect() as conn:
        conn.execute("DELETE FROM submissions")
        conn.execute("DELETE FROM rounds")
        # DO NOT touch team_codes table - keep teams joined!
        conn.commit()
    
    flash('Game reset! Teams are still joined. Upload new questions to start fresh.', 'success')
    return redirect(url_for('host_dashboard'))

@app.route('/host/reset-all', methods=['POST'])
@host_required
def reset_all():
    """Reset everything - clear teams but keep code values"""
    global RESET_COUNTER
    
    with db_connect() as conn:
        conn.execute("DELETE FROM submissions")
        conn.execute("DELETE FROM rounds")
        # Reset codes to unused but keep the code values (HNCL, LZLX, etc)
        conn.execute("UPDATE team_codes SET used = 0, team_name = NULL")
        conn.commit()
    
    # Increment reset counter to invalidate all team sessions
    RESET_COUNTER += 1
    logger.info(f"Reset All clicked - RESET_COUNTER incremented to {RESET_COUNTER}")
    logger.info("All team sessions are now invalid - teams will see Game Over page")
    
    flash('Everything reset! All codes are now unused and ready for new teams.', 'success')
    return redirect(url_for('host_dashboard'))

@app.route('/host/settings', methods=['GET', 'POST'])
@host_required
def settings():
    """Settings page for configuring game options"""
    if request.method == 'POST':
        # Get form data
        qr_base_url = request.form.get('qr_base_url', '').strip()
        
        # Basic validation
        if not qr_base_url:
            flash('QR Base URL cannot be empty!', 'error')
        elif ' ' in qr_base_url:
            flash('URL cannot contain spaces!', 'error')
        else:
            # Save setting
            if set_setting('qr_base_url', qr_base_url, 'Base URL for QR codes on printed sheets'):
                flash('Settings saved successfully!', 'success')
            else:
                flash('Failed to save settings. Please try again.', 'error')
        
        return redirect(url_for('settings'))
    
   # GET - show form with current settings
    # Check for QR_BASE_URL environment variable first
    qr_url_from_env = os.environ.get('QR_BASE_URL')
    if qr_url_from_env:
        default_url = qr_url_from_env
    elif os.environ.get('RENDER'):
        default_url = 'https://pubfeud.gamenightguild.net'
    else:
        default_url = 'http://localhost:5000'
    
    current_qr_url = get_setting('qr_base_url', default_url)
    allow_team_registration = get_setting('allow_team_registration', 'true') == 'true'
    system_paused = get_setting('system_paused', 'false') == 'true'
    broadcast_message = get_setting('broadcast_message', '')
    
    return render_template('settings.html', 
                         qr_base_url=current_qr_url,
                         allow_team_registration=allow_team_registration,
                         system_paused=system_paused,
                         broadcast_message=broadcast_message)

@app.route('/host/toggle-setting', methods=['POST'])
@host_required
def toggle_setting():
    """Toggle a boolean setting"""
    setting_key = request.form.get('setting_key')
    
    if setting_key in ['allow_team_registration', 'system_paused']:
        current_value = get_setting(setting_key, 'false')
        new_value = 'false' if current_value == 'true' else 'true'
        
        set_setting(setting_key, new_value, '')
        
        # User-friendly messages
        if setting_key == 'allow_team_registration':
            if new_value == 'true':
                flash('✅ Team registration enabled - New teams can join!', 'success')
            else:
                flash('🚫 Team registration disabled - No new teams can join', 'success')
        elif setting_key == 'system_paused':
            if new_value == 'true':
                # Auto-disable registration when pausing
                set_setting('allow_team_registration', 'false', '')
                flash('⏸️ System PAUSED - Team registration also disabled', 'success')
            else:
                flash('▶️ System RESUMED - Remember to re-enable registration if needed', 'success')
    
    return redirect(url_for('settings'))

@app.route('/host/toggle-sleep', methods=['POST'])
@host_required
def toggle_sleep():
    """Toggle server sleep mode"""
    current_value = get_setting('server_sleep', 'false')
    new_value = 'false' if current_value == 'true' else 'true'
    
    set_setting('server_sleep', new_value, 'Server sleep mode - stops auto-refresh')
    
    if new_value == 'true':
        logger.info("Server sleep mode ENABLED - team auto-refresh will stop")
        flash('💤 Server sleep mode enabled - All auto-refresh stopped', 'success')
    else:
        logger.info("Server sleep mode DISABLED - team auto-refresh resumed")
        flash('⏰ Server awake - Auto-refresh resumed', 'success')
    
    return jsonify({'success': True, 'sleep_mode': new_value})

@app.route('/host/get-sleep-status')
@host_required
def get_sleep_status():
    """Get current sleep mode status"""
    sleep_mode = get_setting('server_sleep', 'false')
    return jsonify({'sleep_mode': sleep_mode})

@app.route('/host/send-broadcast', methods=['POST'])
@host_required
def send_broadcast():
    """Send broadcast message to all teams"""
    import html
    import json
    import time
    
    message = request.form.get('message', '').strip()
    
    if not message:
        flash('⚠️ Message cannot be empty!', 'error')
        return redirect(url_for('settings'))
    
    # Security: Length limit (200 chars max)
    if len(message) > 200:
        flash('⚠️ Message too long! Maximum 200 characters.', 'error')
        return redirect(url_for('settings'))
    
    # Security: HTML escape to prevent XSS
    message = html.escape(message)
    
    # Store message with timestamp
    broadcast_data = {
        'message': message,
        'timestamp': time.time()
    }
    
    set_setting('broadcast_message', json.dumps(broadcast_data), 'Broadcast message to all teams')
    flash(f'📢 Message sent to all teams!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/host/clear-broadcast', methods=['POST'])
@host_required
def clear_broadcast():
    """Clear broadcast message"""
    import json
    # Set empty broadcast with current timestamp
    broadcast_data = {
        'message': '',
        'timestamp': 0
    }
    set_setting('broadcast_message', json.dumps(broadcast_data), 'Broadcast message to all teams')
    flash('🗑️ Broadcast message cleared', 'success')
    return redirect(url_for('settings'))

@app.route('/host/close-round', methods=['POST'])
@host_required
def close_round():
    """Close submissions for the active round and move to scoring"""
    with db_connect() as conn:
        # Get active round
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()
        
        if not active_round:
            flash('⚠️ No active round to close', 'error')
            return redirect(url_for('host_dashboard'))
        
        # Mark round as closed
        conn.execute("UPDATE rounds SET submissions_closed = 1 WHERE id = ?", (active_round['id'],))
        conn.commit()
        
        # Count submissions
        sub_count = conn.execute("SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ?", 
                                (active_round['id'],)).fetchone()['cnt']
        
        # Check if all submissions are already scored
        unscored_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM submissions WHERE round_id = ? AND scored = 0",
            (active_round['id'],)
        ).fetchone()['cnt']
        
        flash(f'🔒 Round {active_round["round_number"]} closed! {sub_count} teams submitted.', 'success')
        
        # If all teams are already scored, skip scoring queue and go straight to winner announcement
        if unscored_count == 0 and sub_count > 0:
            logger.info(f"All {sub_count} teams already scored - skipping scoring queue")
            return redirect(url_for('round_summary'))
        
        return redirect(url_for('scoring_queue'))

# ============= TEAM ROUTES =============

@app.route('/join')
def join():
    """Team join page - step 1"""
    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")
    
    # Check if team registration is allowed
    if get_setting('allow_team_registration', 'true') == 'false':
        return render_template('join.html', error="🚫 Team registration is currently closed.")
    
    return render_template('join.html')

@app.route('/terms')
def terms():
    """Terms and conditions page"""
    return render_template('terms.html')

@app.route('/join/validate-code', methods=['POST'])
def validate_code():
    """Step 1: Validate team code"""
    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")
    
    # Check if team registration is allowed
    if get_setting('allow_team_registration', 'true') == 'false':
        return render_template('join.html', error="🚫 Team registration is currently closed.")
    
    code = request.form.get('code', '').strip().upper()
    
    if not code:
        return render_template('join.html', error="Please enter a code")
    
    with db_connect() as conn:
        code_row = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()
        
        if not code_row:
            return render_template('join.html', error="Invalid code. Check your code and try again.")
        
        if code_row['used']:
            # Code is in use - show reconnection form
            return render_template('join.html', code=code, show_reconnect_form=True, existing_team=code_row['team_name'])
    
    return render_template('join.html', code=code, show_team_form=True)

@app.route('/join/reconnect', methods=['POST'])
def join_reconnect():
    """Reconnect with existing team code"""
    logger.info(f"🔄 RECONNECT: Attempt started")

    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        logger.info(f"🔄 RECONNECT: Blocked - system paused")
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")

    code = request.form.get('code', '').strip().upper()
    team_name = request.form.get('team_name', '').strip()

    logger.info(f"🔄 RECONNECT: code='{code}', team_name='{team_name}'")

    if not code or not team_name:
        logger.warning(f"🔄 RECONNECT: Missing code or team_name")
        return render_template('join.html', error="Please enter both code and team name")

    with db_connect() as conn:
        code_row = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()

        if not code_row:
            logger.warning(f"🔄 RECONNECT: Code '{code}' not found in database")
            return render_template('join.html', error="Invalid code")

        logger.info(f"🔄 RECONNECT: Code found - used={code_row['used']}, team_name='{code_row['team_name']}'")

        if not code_row['used']:
            logger.warning(f"🔄 RECONNECT: Code '{code}' not yet used, rejecting reconnect")
            return render_template('join.html', error="This code hasn't been used yet. Use regular join.")

        # Case-insensitive team name comparison
        if code_row['team_name'].lower() != team_name.lower():
            logger.warning(f"🔄 RECONNECT: Name mismatch - DB='{code_row['team_name']}', submitted='{team_name}'")
            return render_template('join.html',
                code=code,
                show_reconnect_form=True,
                existing_team=code_row['team_name'],
                error="❌ Team name doesn't match. This code belongs to another team. Get a new code from the host.")

        # Team name matches - mark as reconnected, init heartbeat, and create session
        logger.info(f"🔄 RECONNECT: Name matches! Updating DB and creating session")
        conn.execute(
            "UPDATE team_codes SET reconnected = 1, last_heartbeat = CURRENT_TIMESTAMP WHERE code = ?",
            (code,)
        )
        conn.commit()

        # Create session
        session['code'] = code
        session['team_name'] = code_row['team_name']  # Use original capitalization
        session['startup_id'] = STARTUP_ID
        session['reset_counter'] = RESET_COUNTER

        logger.info(f"✅ RECONNECT: Session created for '{code_row['team_name']}' (Code: {code}), redirecting to team_play")

        return redirect(url_for('team_play'))

@app.route('/join/submit', methods=['POST'])
def join_submit():
    """Step 2: Submit team name"""
    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        return render_template('join.html', error="⏸️ System is currently paused. Please wait for the host to resume.")
    
    # Check if team registration is allowed
    if get_setting('allow_team_registration', 'true') == 'false':
        return render_template('join.html', error="🚫 Team registration is currently closed.")
    
    code = request.form.get('code', '').strip().upper()
    team_name = request.form.get('team_name', '').strip()
    
    # Validation: Check for empty code or team name
    if not code or not team_name:
        return render_template('join.html', code=code, error="Please enter both code and team name")
    
    # Validation: Check for whitespace-only team name
    if len(team_name.strip()) == 0:
        return render_template('join.html', code=code, error="Team name cannot be empty or just spaces")
    
    # Validation: Team name character limit (30 chars max)
    if len(team_name) > 30:
        return render_template('join.html', code=code, error="Team name too long! Maximum 30 characters.")
    
    with db_connect() as conn:
        # Validation: Check for duplicate team names (case-insensitive)
        existing_team = conn.execute(
            "SELECT team_name FROM team_codes WHERE LOWER(team_name) = LOWER(?) AND used = 1 AND code != ?",
            (team_name, code)
        ).fetchone()
        if existing_team:
            # Suggest alternative names
            base_name = team_name if len(team_name) <= 27 else team_name[:27]  # Leave room for " 2"
            counter = 2
            suggested_name = f"{base_name} {counter}"
            while conn.execute(
                "SELECT team_name FROM team_codes WHERE LOWER(team_name) = LOWER(?) AND used = 1 AND code != ?",
                (suggested_name, code)
            ).fetchone():
                counter += 1
                suggested_name = f"{base_name} {counter}"
            
            return render_template('join.html', code=code, error=f'Team name "{team_name}" already taken! Try: "{suggested_name}"')
        
        code_row = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()
        
        if not code_row:
            return render_template('join.html', error="Invalid code")
        
        if code_row['used']:
            # Code is already used - check if it's the same team trying to rejoin
            if code_row['team_name'] and code_row['team_name'].lower() == team_name.lower():
                # Same team rejoining - allow it and restore session
                logger.info(f"✅ REJOIN: Team '{team_name}' rejoining with code {code}")
                
                # Initialize heartbeat for rejoining team
                conn.execute(
                    "UPDATE team_codes SET last_heartbeat = CURRENT_TIMESTAMP WHERE code = ?",
                    (code,)
                )
                conn.commit()
                
                session['code'] = code
                session['team_name'] = team_name
                session['startup_id'] = STARTUP_ID
                session['reset_counter'] = RESET_COUNTER
                
                logger.info(f"✅ REJOIN: Session restored for {team_name}, redirecting to /play")
                return redirect(url_for('team_play'))
            else:
                # Different team trying to use an already-used code
                logger.warning(f"❌ REJOIN BLOCKED: Code {code} used by '{code_row['team_name']}', attempted by '{team_name}'")
                return render_template('join.html', error="Code already used by another team")
        
        # Code is unused - claim it
        conn.execute("UPDATE team_codes SET used = 1, team_name = ? WHERE code = ?", (team_name, code))
        conn.commit()
        
        # Store current startup_id and reset_counter in session
        # If server restarts or game resets, session becomes invalid
        session['code'] = code
        session['team_name'] = team_name
        session['startup_id'] = STARTUP_ID
        session['reset_counter'] = RESET_COUNTER
        
        return redirect(url_for('team_play'))

@app.route('/api/heartbeat', methods=['POST'])
@team_session_valid
def heartbeat():
    """Update last heartbeat timestamp for active tab detection"""
    code = session.get('code')
    
    if not code:
        return jsonify({"success": False}), 401
    
    with db_connect() as conn:
        conn.execute("""
            UPDATE team_codes 
            SET last_heartbeat = CURRENT_TIMESTAMP 
            WHERE code = ?
        """, (code,))
        conn.commit()
    
    return jsonify({"success": True})

@app.route('/host/team-status')
@host_required
def get_team_status():
    """Get status of all teams (online/offline) for host dashboard"""
    with db_connect() as conn:
        teams = conn.execute("""
            SELECT code, team_name, used, last_heartbeat,
                   CASE 
                       WHEN last_heartbeat IS NULL THEN 0
                       WHEN (julianday('now') - julianday(last_heartbeat)) * 86400 <= 15 THEN 1
                       ELSE 0
                   END as is_online
            FROM team_codes
            ORDER BY code
        """).fetchall()
        
        result = []
        for team in teams:
            team_dict = dict(team)
            # Calculate last seen time
            if team['last_heartbeat']:
                from datetime import datetime
                try:
                    last_seen = datetime.fromisoformat(team['last_heartbeat'].replace('Z', '+00:00'))
                    now = datetime.now(last_seen.tzinfo) if last_seen.tzinfo else datetime.now()
                    seconds_ago = int((now - last_seen).total_seconds())
                    
                    if seconds_ago < 60:
                        team_dict['last_seen_text'] = f"{seconds_ago} seconds ago"
                    elif seconds_ago < 3600:
                        minutes = seconds_ago // 60
                        team_dict['last_seen_text'] = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
                    else:
                        hours = seconds_ago // 3600
                        team_dict['last_seen_text'] = f"{hours} hour{'s' if hours != 1 else ''} ago"
                except:
                    team_dict['last_seen_text'] = "Unknown"
            else:
                team_dict['last_seen_text'] = "Never"
            
            result.append(team_dict)
        
        return jsonify(result)

@app.route('/api/check-round-status')
def check_round_status():
    """API endpoint to check if there's an active round (for AJAX polling)"""
    code = session.get('code')
    
    if not code:
        return jsonify({'error': 'No code in session'}), 401
    
    # Check if server was restarted (startup_id mismatch)
    session_startup_id = session.get('startup_id')
    if session_startup_id != STARTUP_ID:
        return jsonify({'error': 'Server restarted', 'reload': True}), 401
    
    # Check if game was reset (reset_counter mismatch)
    session_reset_counter = session.get('reset_counter', 0)
    if session_reset_counter != RESET_COUNTER:
        return jsonify({'error': 'Game was reset', 'reload': True}), 401
    
    # Check if server is in sleep mode
    server_sleep = get_setting('server_sleep', 'false')
    if server_sleep == 'true':
        return jsonify({'sleep_mode': True, 'message': 'Server in sleep mode'}), 200
    
    with db_connect() as conn:
        # Check if there's an active round
        active_round = conn.execute("SELECT id, round_number, submissions_closed FROM rounds WHERE is_active = 1").fetchone()
        
        if active_round:
            # Check if this team already submitted for this round
            submission = conn.execute(
                "SELECT id FROM submissions WHERE code = ? AND round_id = ?",
                (code, active_round['id'])
            ).fetchone()
            
            return jsonify({
                'has_active_round': True,
                'round_id': active_round['id'],
                'round_number': active_round['round_number'],
                'submissions_closed': bool(active_round['submissions_closed']),
                'already_submitted': submission is not None
            })
        else:
            return jsonify({
                'has_active_round': False
            })

@app.route('/play')
@team_session_valid
def team_play():
    """Team answer submission page"""
    code = session.get('code')
    team_name = session.get('team_name')
    
    if not code:
        logger.warning("team_play: No code in session, redirecting to join")
        return redirect(url_for('join'))
    
    with db_connect() as conn:
        # DEFENSIVE: Verify team still exists in database
        team = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()
        
        if not team:
            # Team doesn't exist anymore - session is stale
            logger.error(f"team_play: Team {code} not found in database, clearing session")
            session.clear()
            return redirect(url_for('join'))
        
        # DEFENSIVE: Initialize last_heartbeat if NULL (for rejoining teams)
        if team['last_heartbeat'] is None:
            logger.info(f"team_play: Initializing heartbeat for team {code} ({team_name})")
            conn.execute(
                "UPDATE team_codes SET last_heartbeat = CURRENT_TIMESTAMP WHERE code = ?",
                (code,)
            )
            conn.commit()
        
        active_round = conn.execute("SELECT * FROM rounds WHERE is_active = 1").fetchone()
        
        if not active_round:
            return render_template('play.html', 
                                 team_name=team_name,
                                 code=code,
                                 no_active_round=True)
        
        submission = conn.execute("""
            SELECT * FROM submissions 
            WHERE code = ? AND round_id = ?
        """, (code, active_round['id'])).fetchone()
        
        if submission:
            # Get last_submission from session (for answer preview)
            last_submission = session.pop('last_submission', None)
            
            return render_template('play.html',
                                 team_name=team_name,
                                 code=code,
                                 round_num=active_round['round_number'],
                                 question=active_round['question'],
                                 num_answers=active_round['num_answers'],
                                 already_submitted=True,
                                 submissions_closed=active_round['submissions_closed'],
                                 submission=dict(submission),
                                 last_submission=last_submission)
    
    return render_template('play.html',
                         team_name=team_name,
                         code=code,
                         round_num=active_round['round_number'],
                         question=active_round['question'],
                         num_answers=active_round['num_answers'],
                         round_id=active_round['id'],
                         submissions_closed=active_round['submissions_closed'])

@app.route('/play/submit', methods=['POST'])
@team_session_valid
def submit_answers():
    """Submit team answers"""
    # Check if system is paused
    if get_setting('system_paused', 'false') == 'true':
        flash('⏸️ System is currently paused. Submissions are disabled.', 'error')
        return redirect(url_for('team_play'))
    
    code = session.get('code')
    
    if not code:
        return redirect(url_for('join'))
    
    round_id = request.form.get('round_id')
    
    # Validation: Tiebreaker must be 0-100
    try:
        tiebreaker = int(request.form.get('tiebreaker', 0) or 0)
        if tiebreaker < 0 or tiebreaker > 100:
            flash('⚠️ Tiebreaker must be between 0 and 100', 'error')
            return redirect(url_for('team_play'))
    except ValueError:
        tiebreaker = 0
    
    with db_connect() as conn:
        # Validate that this is still the active round (prevent stale submissions)
        active_round = conn.execute("SELECT id, submissions_closed FROM rounds WHERE is_active = 1").fetchone()
        if not active_round or str(active_round['id']) != str(round_id):
            # Round has changed - redirect to play page to get current round
            return redirect(url_for('team_play'))
        
        # Check if round is closed
        if active_round['submissions_closed']:
            flash('⏰ Round has ended. Submissions are closed.', 'error')
            return redirect(url_for('team_play'))
        
        # CRITICAL FIX: Check for duplicate submission BEFORE attempting insert
        existing_submission = conn.execute(
            "SELECT id FROM submissions WHERE code = ? AND round_id = ?",
            (code, round_id)
        ).fetchone()
        
        if existing_submission:
            flash('✅ You have already submitted for this round!', 'warning')
            return redirect(url_for('team_play'))
        
        round_info = conn.execute("SELECT num_answers FROM rounds WHERE id = ?", (round_id,)).fetchone()
        num_answers = round_info['num_answers']
        
        answers = {f'answer{i}': request.form.get(f'answer{i}', '').strip() for i in range(1, num_answers + 1)}
        
        try:
            fields = ['code', 'round_id', 'tiebreaker'] + [f'answer{i}' for i in range(1, num_answers + 1)]
            placeholders = ', '.join(['?'] * len(fields))
            values = [code, round_id, tiebreaker] + [answers[f'answer{i}'] for i in range(1, num_answers + 1)]
            
            conn.execute(f"INSERT INTO submissions ({', '.join(fields)}) VALUES ({placeholders})", values)
            conn.commit()
            
            # Store submission for answer preview
            session['last_submission'] = {
                'round_id': round_id,
                'answers': answers,
                'tiebreaker': tiebreaker
            }
        except sqlite3.IntegrityError:
            # Fallback: UNIQUE constraint caught it
            flash('✅ You have already submitted for this round!', 'warning')
    
    return redirect(url_for('team_play'))

@app.route('/api/broadcast-message')
def api_broadcast_message():
    """API endpoint for teams to get current broadcast message"""
    import json
    
    broadcast_json = get_setting('broadcast_message', '')
    
    # Handle legacy format (plain string) or new format (JSON)
    try:
        if broadcast_json:
            broadcast_data = json.loads(broadcast_json)
            return jsonify({
                'message': broadcast_data.get('message', ''),
                'timestamp': broadcast_data.get('timestamp', 0)
            })
        else:
            return jsonify({'message': '', 'timestamp': 0})
    except (json.JSONDecodeError, TypeError):
        # Legacy format - just a plain string
        return jsonify({'message': broadcast_json, 'timestamp': 0})

if __name__ == '__main__':
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("\n" + "="*60)
    print("🎮 FAMILY FEUD - PRODUCTION SERVER")
    print("="*60)
    print(f"\n📱 Team Join: http://{local_ip}:5000/join")
    print(f"🖥️  Host Dashboard: http://localhost:5000/host")
    print(f"🏆 Scoring Queue: http://localhost:5000/host/scoring-queue")
    print(f"\n💡 Upload answer sheet, generate codes, start playing!")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
