"""
Authentication, session management, and request logging for Family Feud.

Owns: host_required/team_session_valid decorators, host login/logout routes,
session configuration, and request logging middleware.
"""

from functools import wraps
from flask import Blueprint, request, session, redirect, url_for, render_template, flash

from config import (
    logger, SECRET_KEY, STARTUP_ID, reset_state,
    HOST_PASSWORD, AI_SCORING_ENABLED, QUIET_PATHS,
)

auth_bp = Blueprint('auth', __name__)


def configure_session(app):
    """Set session secret key and cookie configuration on the Flask app."""
    app.secret_key = SECRET_KEY


@auth_bp.before_app_request
def log_request():
    """Log incoming requests - skip static files and high-frequency polling"""
    if request.path.startswith('/static'):
        return
    if request.path in QUIET_PATHS:
        return
    if request.path.startswith('/api/view-status/'):
        return
    code = session.get('code', '-')
    team = session.get('team_name', '-')
    logger.debug(f"[REQUEST] {request.method} {request.path} | code={code} team={team} ip={request.remote_addr}")


def host_required(f):
    """Decorator to protect host routes - requires password authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('host_authenticated'):
            if request.path in QUIET_PATHS:
                logger.debug(f"[HOST] Auth check FAILED for {request.path} - redirecting to login")
            else:
                logger.info(f"[HOST] Auth check FAILED for {request.path} - redirecting to login")
            return redirect(url_for('auth.host_login'))
        logger.debug(f"[HOST] Auth check passed for {request.path}")
        return f(*args, **kwargs)
    return decorated_function


def team_session_valid(f):
    """Decorator to validate team session - checks startup_id and reset_counter"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # CRITICAL: Check reset_counter and startup_id BEFORE checking if session exists
        # This ensures Game Over page shows even if session was cleared

        # Use DEBUG for polling endpoints to avoid log noise
        log = logger.debug if request.path in QUIET_PATHS else logger.info

        # Check if startup_id in session matches current server startup
        # If server restarted, STARTUP_ID changes = all old sessions invalid
        session_startup_id = session.get('startup_id')

        if session_startup_id is not None and session_startup_id != STARTUP_ID:
            # Server was restarted - show game over page
            log(f"Team session invalid - server restarted (session startup_id: {session_startup_id}, current: {STARTUP_ID})")
            session.clear()
            return render_template('game_over.html', reason='server_restart')

        # Check if reset_counter matches (Reset All button invalidates sessions)
        session_reset_counter = session.get('reset_counter', 0)

        if session_reset_counter != reset_state['counter']:
            # Game was reset - show game over page
            log(f"Team session invalid - game was reset (session counter: {session_reset_counter}, current: {reset_state['counter']})")
            session.clear()
            return render_template('game_over.html', reason='game_reset')

        # NOW check if team has a session (after checking reset/restart)
        if 'code' not in session:
            log("[TEAM] No team session found - redirecting to join")
            return redirect(url_for('join'))

        logger.debug(f"[TEAM] Session valid for code={session.get('code')} team={session.get('team_name')} path={request.path}")
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/host/login', methods=['GET', 'POST'])
def host_login():
    """Host login page - password authentication"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == HOST_PASSWORD:
            session['host_authenticated'] = True
            logger.info("Host authenticated successfully")
            # Check if user explicitly clicked the camera/scan button
            if request.form.get('action') == 'scan':
                logger.info("[HOST] Login via scan button — redirecting to photo scan")
                return redirect(url_for('photo_scan'))
            # On mobile, go straight to photo scan (if AI enabled)
            if AI_SCORING_ENABLED:
                ua = request.headers.get('User-Agent', '').lower()
                if any(m in ua for m in ['iphone', 'android', 'mobile']):
                    logger.info("[HOST] Mobile login — redirecting to photo scan")
                    return redirect(url_for('photo_scan'))
            return redirect(url_for('host.host_dashboard'))
        else:
            logger.warning("Failed host login attempt")
            return render_template('host_login.html', error=True, ai_scoring_available=AI_SCORING_ENABLED)
    return render_template('host_login.html', error=False, ai_scoring_available=AI_SCORING_ENABLED)


@auth_bp.route('/host/logout')
def host_logout():
    """Logout from host panel"""
    session.pop('host_authenticated', None)
    logger.info("Host logged out")
    return redirect(url_for('.host_login'))
