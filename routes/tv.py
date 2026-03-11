"""
TV display routes for the Live TV Game Board.

Public routes — no authentication required. The TV display page
is opened in a browser window on the pub TV via HDMI.
"""

from flask import Blueprint, render_template

tv_bp = Blueprint('tv', __name__)


@tv_bp.route('/tv/board')
def tv_board():
    """Full-screen TV display page for answer reveals."""
    return render_template('tv_board.html')
