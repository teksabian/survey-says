"""
TV display routes for the Live TV Game Board.

Includes public TV display page and host-authenticated control pages.
"""

import secrets as _secrets

from flask import Blueprint, flash, redirect, render_template, session, url_for

from auth import host_required
from database import get_setting, get_game_mode

tv_bp = Blueprint('tv', __name__)


@tv_bp.route('/tv/board')
def tv_board():
    """Full-screen TV display page for answer reveals."""
    return render_template('tv_board.html', game_mode=get_game_mode())


@tv_bp.route('/reveal/<token>')
def reveal_token_entry(token):
    """QR code entry point — grants host session for reveal control without password."""
    stored_token = get_setting('scan_token')
    if not stored_token or not _secrets.compare_digest(token, stored_token):
        flash('Invalid or expired link.', 'error')
        return redirect(url_for('auth.host_login'))
    session['host_authenticated'] = True
    return redirect(url_for('tv.reveal_control'))


@tv_bp.route('/host/reveal-control')
@host_required
def reveal_control():
    """Mobile-friendly reveal control page for the host."""
    if get_setting('tv_board_enabled', 'true') != 'true':
        flash('TV Board is not enabled', 'error')
        return redirect(url_for('host.host_dashboard'))
    return render_template('reveal_control.html')
