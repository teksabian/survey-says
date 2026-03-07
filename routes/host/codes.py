"""Team code management, QR code generation, and answer sheet printing routes."""

import secrets
from flask import request, render_template, redirect, url_for, jsonify, session, flash, has_request_context

from config import logger, QR_DEFAULT_URL
from auth import host_required
from database import (
    db_connect,
    load_fixed_codes,
    ensure_fixed_codes,
    get_setting,
    set_setting,
)
from extensions import socketio

from routes.host import host_bp, ROUNDS_CONFIG


def get_qr_base_url():
    """Get QR code base URL from settings, auto-detect from request, or config defaults."""
    saved = get_setting('qr_base_url')
    if saved:
        return saved
    # Auto-detect from current request (works for review apps, local dev, etc.)
    if has_request_context():
        return request.url_root.rstrip('/')
    return QR_DEFAULT_URL


@host_bp.route('/')
def index():
    return redirect(url_for('auth.host_login'))


@host_bp.route('/scan/<token>')
def scan_qr_entry(token):
    """QR code entry point — grants scanner session without password."""
    stored_token = get_setting('scan_token')
    if not stored_token or not secrets.compare_digest(token, stored_token):
        logger.warning("[SCAN-AUTH] Invalid scan token attempted")
        flash('Invalid or expired scan link.', 'error')
        return redirect(url_for('auth.host_login'))
    session['host_authenticated'] = True
    logger.info("[SCAN-AUTH] Scan token validated — granting host session")
    return redirect(url_for('scoring.photo_scan'))


@host_bp.route('/host/codes-status')
@host_required
def codes_status():
    """API endpoint - returns code statuses as JSON for auto-refresh"""
    logger.debug("[CODES] codes_status() called")
    with db_connect() as conn:
        codes = conn.execute("""
            SELECT code, used, team_name
            FROM team_codes
            ORDER BY id ASC
        """).fetchall()

        codes_data = []
        for code in codes:
            codes_data.append({
                'code': code['code'],
                'used': bool(code['used']),
                'team_name': code['team_name'] if code['team_name'] else None
            })

        used_count = sum(1 for c in codes_data if c['used'])

        logger.debug(f"[CODES] codes_status() returning {len(codes_data)} total, {used_count} used")

        return jsonify({
            'codes': codes_data,
            'total': len(codes_data),
            'used': used_count
        })

@host_bp.route('/host/generate-codes', methods=['POST'])
@host_required
def generate_codes():
    """Reload fixed team codes from codes.json"""
    logger.info("[CODES] generate_codes() - reloading fixed codes from codes.json")
    ensure_fixed_codes()
    codes = load_fixed_codes()
    logger.info(f"[CODES] generate_codes() - {len(codes)} fixed codes loaded")
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
            <h1>\u2705 Success!</h1>
            <p style="font-size: 1.5em;">{len(codes)} fixed team codes loaded!</p>
            <button onclick="window.location.href='/host'">Back to Dashboard</button>
        </div>
    </body>
    </html>
    """

@host_bp.route('/host/reclaim-code/<code>', methods=['POST'])
@host_required
def reclaim_code(code):
    """Reclaim a used code - removes team and frees code for reuse"""
    code = code.upper()
    logger.debug(f"[CODES] reclaim_code() - attempting to reclaim code={code}")

    with db_connect() as conn:
        code_row = conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()

        if not code_row:
            logger.warning(f"[CODES] reclaim_code() - code={code} not found")
            return jsonify({"success": False, "message": "Code not found"}), 404

        if not code_row['used']:
            logger.warning(f"[CODES] reclaim_code() - code={code} is not in use")
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

        # Emit updated codes list to host dashboard
        codes = conn.execute("SELECT code, used, team_name FROM team_codes ORDER BY id ASC").fetchall()
        codes_data = [{'code': c['code'], 'used': bool(c['used']), 'team_name': c['team_name']} for c in codes]
        socketio.emit('codes:updated', {'codes': codes_data}, to='hosts')

        logger.info(f"[CODES] reclaim_code() - code={code} reclaimed from team='{team_name}', submissions deleted")

        return jsonify({
            "success": True,
            "message": f"Code {code} reclaimed. Team '{team_name}' removed."
        })

@host_bp.route('/host/print-codes')
@host_required
def print_codes():
    """Generate landscape HTML page with QR codes for mobile play (replaces paper)"""
    logger.debug("[CODES] print_codes() - generating mobile play QR code page")
    codes = load_fixed_codes()
    if not codes:
        return "No codes available. Generate codes first!", 400
    qr_base_url = get_qr_base_url()
    return render_template('print_qr_codes.html', codes=codes, qr_base_url=qr_base_url,
                           mode='play', title='Mobile Play \u2014 Scan to Play on Your Phone')

@host_bp.route('/host/print-codes-landscape')
@host_required
def print_codes_landscape():
    """Generate landscape HTML page with QR codes for view-only status (companion to paper)"""
    logger.debug("[CODES] print_codes_landscape() - generating view-only QR code page")
    codes = load_fixed_codes()
    if not codes:
        return "No codes available. Generate codes first!", 400
    qr_base_url = get_qr_base_url()
    return render_template('print_qr_codes.html', codes=codes, qr_base_url=qr_base_url,
                           mode='view', title='View Only \u2014 See Your Submitted Answers')

@host_bp.route('/host/print-answer-sheets')
@host_required
def print_answer_sheets():
    """Generate printable answer sheets with pre-printed codes.
    Accepts ?group=1 (codes 1-30) or ?group=2 (codes 31-60).
    """
    all_codes = load_fixed_codes()
    group = request.args.get('group', '1')
    if group == '2':
        codes = all_codes[30:60]
        group_label = 'Group 2 (31-60)'
    else:
        codes = all_codes[0:30]
        group_label = 'Group 1 (1-30)'
    logger.info(f"[CODES] print_answer_sheets() - generating {group_label} ({len(codes)} codes)")
    qr_base_url = get_qr_base_url()

    return render_template('print_answer_sheets.html', codes=codes, group_label=group_label, rounds_config=ROUNDS_CONFIG, qr_base_url=qr_base_url)
