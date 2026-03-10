"""Host dashboard, settings, sleep mode, and AI configuration routes."""

import secrets
from datetime import datetime
from flask import request, render_template, redirect, url_for, jsonify, session, flash

from config import (
    logger,
    AI_SCORING_ENABLED, AI_MODEL_CHOICES,
    time_ago, format_timestamp,
)
from auth import host_required
from database import (
    db_connect,
    get_setting,
    set_setting,
)
from extensions import socketio
from ai import (
    load_corrections_history,
    get_current_ocr_model,
    get_current_scoring_model,
)

from routes.host import host_bp, ROUNDS_CONFIG


@host_bp.route('/host')
@host_required
def host_dashboard():
    """Main host dashboard"""
    logger.debug("[HOST] host_dashboard() - loading dashboard")
    with db_connect() as conn:
        codes_raw = conn.execute("""
            SELECT code, used, team_name, reconnected, last_heartbeat
            FROM team_codes
            ORDER BY id ASC
        """).fetchall()

        # Process codes to add active status
        codes = []
        for code in codes_raw:
            code_dict = dict(code)
            # Calculate if team is active (heartbeat within last 30 seconds)
            if code['last_heartbeat']:
                try:
                    # Parse timestamp
                    last_hb = datetime.fromisoformat(code['last_heartbeat'])
                    now = datetime.now()
                    time_diff = (now - last_hb).total_seconds()
                    code_dict['is_active'] = time_diff < 30
                except (ValueError, TypeError):
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
                WHERE round_id = ? AND host_submitted = 0
            """, (active_round['id'],)).fetchone()['cnt']

            # Total submissions for active round
            submission_count = conn.execute("""
                SELECT COUNT(*) as cnt FROM submissions
                WHERE round_id = ?
            """, (active_round['id'],)).fetchone()['cnt']

    # Generate or retrieve scan token for QR code
    scan_token = get_setting('scan_token')
    if not scan_token:
        scan_token = secrets.token_urlsafe(16)
        set_setting('scan_token', scan_token, 'Token for passwordless scanner QR code')

    from routes.host.codes import get_qr_base_url
    qr_base_url = get_qr_base_url()

    logger.debug(f"[HOST] host_dashboard() - {len(codes)} codes, {len(rounds)} rounds, "
                 f"active_round={'R'+str(active_round['round_number']) if active_round else 'None'}, "
                 f"submissions={submission_count}, unscored={unscored_count}")
    return render_template('host.html',
                         codes=codes,
                         rounds=[dict(r) for r in rounds],
                         active_round=dict(active_round) if active_round else None,
                         unscored_count=unscored_count,
                         submission_count=submission_count,
                         rounds_config=ROUNDS_CONFIG,
                         ai_scoring_available=AI_SCORING_ENABLED,
                         scan_token=scan_token,
                         qr_base_url=qr_base_url)


@host_bp.route('/host/settings', methods=['GET', 'POST'])
@host_required
def settings():
    """Settings page for configuring game options"""
    if request.method == 'POST':
        # Get form data
        qr_base_url = request.form.get('qr_base_url', '').strip()
        logger.info(f"[SETTINGS] settings() POST - qr_base_url='{qr_base_url}'")

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

        return redirect(url_for('.settings'))

   # GET - show form with current settings
    from routes.host.codes import get_qr_base_url
    current_qr_url = get_qr_base_url()
    allow_team_registration = get_setting('allow_team_registration', 'true') == 'true'
    system_paused = get_setting('system_paused', 'false') == 'true'
    broadcast_message = get_setting('broadcast_message', '')
    ai_scoring_enabled = get_setting('ai_scoring_enabled', 'true') == 'true'
    extended_thinking_enabled = get_setting('extended_thinking_enabled', 'false') == 'true'
    thinking_budget_tokens = int(get_setting('thinking_budget_tokens', '10000'))
    mobile_experience = get_setting('mobile_experience', 'advanced_no_pp')

    # Count corrections in current session
    corrections_count = len(load_corrections_history())

    return render_template('settings.html',
                         qr_base_url=current_qr_url,
                         allow_team_registration=allow_team_registration,
                         system_paused=system_paused,
                         mobile_experience=mobile_experience,
                         broadcast_message=broadcast_message,
                         ai_scoring_available=AI_SCORING_ENABLED,
                         ai_scoring_enabled=ai_scoring_enabled,
                         corrections_count=corrections_count,
                         ai_model_choices=AI_MODEL_CHOICES,
                         current_ocr_model=get_current_ocr_model(),
                         current_scoring_model=get_current_scoring_model(),
                         extended_thinking_enabled=extended_thinking_enabled,
                         thinking_budget_tokens=thinking_budget_tokens)


@host_bp.route('/host/toggle-setting', methods=['POST'])
@host_required
def toggle_setting():
    """Toggle a boolean setting"""
    setting_key = request.form.get('setting_key')

    if setting_key in ['allow_team_registration', 'system_paused', 'ai_scoring_enabled', 'extended_thinking_enabled', 'auto_ai_scoring']:
        current_value = get_setting(setting_key, 'true' if setting_key == 'ai_scoring_enabled' else 'false')
        new_value = 'false' if current_value == 'true' else 'true'
        logger.info(f"[SETTINGS] toggle_setting() - {setting_key}: '{current_value}' -> '{new_value}'")

        set_setting(setting_key, new_value, '')

        # User-friendly messages
        if setting_key == 'allow_team_registration':
            if new_value == 'true':
                flash('\u2705 Team registration enabled - New teams can join!', 'success')
            else:
                flash('\ud83d\udead Team registration disabled - No new teams can join', 'success')
        elif setting_key == 'system_paused':
            if new_value == 'true':
                # Auto-disable registration when pausing
                set_setting('allow_team_registration', 'false', '')
                flash('\u23f8\ufe0f System PAUSED - Team registration also disabled', 'success')
            else:
                flash('\u25b6\ufe0f System RESUMED - Remember to re-enable registration if needed', 'success')
        elif setting_key == 'ai_scoring_enabled':
            if new_value == 'true':
                flash('\ud83e\udd16 AI Scoring enabled - AI button will appear on scoring queue', 'success')
            else:
                flash('\ud83e\udd16 AI Scoring disabled - AI button hidden from scoring queue', 'success')
        elif setting_key == 'extended_thinking_enabled':
            if new_value == 'true':
                flash('\ud83e\udde0 Extended Thinking enabled - AI will think deeper (higher cost)', 'success')
            else:
                flash('\ud83e\udde0 Extended Thinking disabled - Using standard mode', 'success')
        elif setting_key == 'auto_ai_scoring':
            if new_value == 'true':
                flash('\ud83e\udd16 Auto AI Scoring enabled - new submissions will be scored automatically', 'success')
            else:
                flash('\ud83e\udd16 Auto AI Scoring disabled', 'success')

    return redirect(url_for('.settings'))


@host_bp.route('/host/set-mobile-experience', methods=['POST'])
@host_required
def set_mobile_experience():
    """Set the mobile experience mode"""
    mode = request.form.get('mode', 'advanced_no_pp')
    if mode in ('basic', 'advanced_no_pp', 'advanced_pp'):
        set_setting('mobile_experience', mode, 'Mobile experience mode for team screens')
        labels = {'basic': 'Basic', 'advanced_no_pp': 'Advanced (No PP Display)', 'advanced_pp': 'Advanced (PP Display)'}
        flash(f'Mobile experience set to: {labels.get(mode, mode)}', 'success')
        logger.info(f"[SETTINGS] set_mobile_experience() - mode={mode}")
    return redirect(url_for('.settings'))


@host_bp.route('/host/set-ai-model', methods=['POST'])
@host_required
def set_ai_model():
    """Set an AI model for OCR or scoring"""
    model_id = request.form.get('ai_model', '').strip()
    purpose = request.form.get('purpose', '').strip()

    valid_ids = [m['id'] for m in AI_MODEL_CHOICES]
    if model_id not in valid_ids:
        flash('Invalid model selection.', 'error')
        return redirect(url_for('.settings'))

    if purpose == 'ocr':
        setting_key = 'ai_ocr_model'
        label = 'OCR'
    elif purpose == 'scoring':
        setting_key = 'ai_scoring_model'
        label = 'Scoring'
    else:
        flash('Invalid model purpose.', 'error')
        return redirect(url_for('.settings'))

    set_setting(setting_key, model_id, f'AI model for {label.lower()}')

    model_name = next((m['name'] for m in AI_MODEL_CHOICES if m['id'] == model_id), model_id)
    logger.info(f"[SETTINGS] AI {label} model changed to: {model_id}")
    flash(f'{label} Model set to {model_name}', 'success')

    return redirect(url_for('.settings'))


@host_bp.route('/host/set-thinking-budget', methods=['POST'])
@host_required
def set_thinking_budget():
    """Set the token budget for extended thinking"""
    budget_str = request.form.get('thinking_budget', '').strip()

    try:
        budget = int(budget_str)
    except (ValueError, TypeError):
        flash('Invalid budget value. Must be a number.', 'error')
        return redirect(url_for('.settings'))

    if budget < 1024:
        flash('Thinking budget must be at least 1,024 tokens.', 'error')
        return redirect(url_for('.settings'))

    if budget > 128000:
        flash('Thinking budget cannot exceed 128,000 tokens.', 'error')
        return redirect(url_for('.settings'))

    set_setting('thinking_budget_tokens', str(budget), 'Token budget for extended thinking')

    logger.info(f"[SETTINGS] Thinking budget changed to: {budget}")
    flash(f'Thinking budget set to {budget:,} tokens', 'success')

    return redirect(url_for('.settings'))


@host_bp.route('/host/set-theme', methods=['POST'])
@host_required
def set_theme():
    """Set the color theme"""
    from config import THEMES
    color_theme = request.form.get('color_theme', 'classic')
    if color_theme in THEMES:
        set_setting('color_theme', color_theme, 'UI color theme')
        logger.info(f"[SETTINGS] Theme changed to: {color_theme}")
        flash(f'Theme set to {THEMES[color_theme]["name"]}', 'success')
    return redirect(url_for('.settings'))


@host_bp.route('/host/toggle-sleep', methods=['POST'])
@host_required
def toggle_sleep():
    """Toggle server sleep mode"""
    current_value = get_setting('server_sleep', 'false')
    new_value = 'false' if current_value == 'true' else 'true'

    set_setting('server_sleep', new_value, 'Server sleep mode - stops auto-refresh')
    socketio.emit('sleep:toggled', {'is_sleeping': new_value == 'true'}, to='teams')

    if new_value == 'true':
        logger.info("[SETTINGS] Server sleep mode ENABLED - team auto-refresh will stop")
        flash('\ud83d\udca4 Server sleep mode enabled - All auto-refresh stopped', 'success')
    else:
        logger.info("[SETTINGS] Server sleep mode DISABLED - team auto-refresh resumed")
        flash('\u23f0 Server awake - Auto-refresh resumed', 'success')

    return jsonify({'success': True, 'sleep_mode': new_value})


@host_bp.route('/host/get-sleep-status')
@host_required
def get_sleep_status():
    """Get current sleep mode status"""
    sleep_mode = get_setting('server_sleep', 'false')
    logger.debug(f"[API] get_sleep_status() -> {sleep_mode}")
    return jsonify({'sleep_mode': sleep_mode})
