"""Broadcast messaging and game reset routes."""

import html
import json
import time
from flask import request, redirect, url_for, jsonify, flash

from config import logger, reset_state
from auth import host_required
from database import (
    db_connect,
    get_setting,
    set_setting,
)
from extensions import socketio

from routes.host import host_bp


@host_bp.route('/host/reset', methods=['POST'])
@host_required
def reset_game():
    """Reset game but keep codes and team names - for setup fixes"""
    logger.info("[HOST] reset_game() - resetting game (keeping teams)")
    with db_connect() as conn:
        conn.execute("DELETE FROM submissions")
        conn.execute("DELETE FROM rounds")
        # DO NOT touch team_codes table - keep teams joined!
        conn.commit()
    socketio.emit('game:reset', {'type': 'soft'}, to='teams')
    logger.info("[HOST] reset_game() - submissions and rounds deleted, team_codes untouched")
    flash('Game reset! Teams are still joined. Upload new questions to start fresh.', 'success')
    return redirect(url_for('.host_dashboard'))

@host_bp.route('/host/reset-all', methods=['POST'])
@host_required
def reset_all():
    """Reset everything - clear teams but keep code values"""
    with db_connect() as conn:
        conn.execute("DELETE FROM submissions")
        conn.execute("DELETE FROM rounds")
        # Reset codes to unused but keep the code values (HNCL, LZLX, etc)
        conn.execute("UPDATE team_codes SET used = 0, team_name = NULL")
        conn.commit()
    socketio.emit('game:reset', {'type': 'full'}, to='teams')

    # Increment reset counter to invalidate all team sessions
    reset_state['counter'] += 1
    logger.info(f"[HOST] reset_all() - reset counter incremented to {reset_state['counter']}")
    logger.info("[HOST] All team sessions are now invalid - teams will see Game Over page")

    flash('Everything reset! All codes are now unused and ready for new teams.', 'success')
    return redirect(url_for('.host_dashboard'))


@host_bp.route('/host/send-broadcast', methods=['POST'])
@host_required
def send_broadcast():
    """Send broadcast message to all teams"""
    message = request.form.get('message', '').strip()
    logger.info(f"[HOST] send_broadcast() - message='{message[:50]}' (len={len(message)})")

    if not message:
        flash('\u26a0\ufe0f Message cannot be empty!', 'error')
        return redirect(url_for('.settings'))

    # Security: Length limit (200 chars max)
    if len(message) > 200:
        flash('\u26a0\ufe0f Message too long! Maximum 200 characters.', 'error')
        return redirect(url_for('.settings'))

    # Security: HTML escape to prevent XSS
    message = html.escape(message)

    # Store message with timestamp
    broadcast_data = {
        'message': message,
        'timestamp': time.time()
    }

    set_setting('broadcast_message', json.dumps(broadcast_data), 'Broadcast message to all teams')
    socketio.emit('broadcast:message', broadcast_data, to='teams')
    flash('\ud83d\udce2 Message sent to all teams!', 'success')

    return redirect(url_for('.settings'))

@host_bp.route('/host/clear-broadcast', methods=['POST'])
@host_required
def clear_broadcast():
    """Clear broadcast message"""
    logger.info("[HOST] clear_broadcast() - broadcast message cleared")
    # Set empty broadcast with current timestamp
    broadcast_data = {
        'message': '',
        'timestamp': 0
    }
    set_setting('broadcast_message', json.dumps(broadcast_data), 'Broadcast message to all teams')
    socketio.emit('broadcast:message', broadcast_data, to='teams')
    flash('\ud83d\uddd1\ufe0f Broadcast message cleared', 'success')
    return redirect(url_for('.settings'))
