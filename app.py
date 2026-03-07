from gevent import monkey
monkey.patch_all()

from flask import Flask
from markupsafe import Markup

from config import APP_VERSION, STARTUP_ID, THEMES, DEFAULT_THEME
from extensions import socketio
from auth import auth_bp, configure_session
from routes.team import team_bp
from routes.host import host_bp
from routes.scoring import scoring_bp
from routes.api import api_bp
from database import (
    ensure_fixed_codes,
    get_setting,
    init_db,
    nuke_all_data,
)

app = Flask(__name__)
configure_session(app)
socketio.init_app(app, cors_allowed_origins="*", async_mode="gevent",
                  ping_interval=5, ping_timeout=3)
app.register_blueprint(auth_bp)
app.register_blueprint(host_bp)
app.register_blueprint(team_bp)
app.register_blueprint(scoring_bp)
app.register_blueprint(api_bp)

@app.context_processor
def inject_version():
    """Make app version and cache buster available in all templates.

    {{ app_version }} - Display version string (e.g. "v2.0.0 - Fusion")
    {{ cache_bust }}  - Query param for static assets, changes every deploy
                        Usage: href="...?v={{ cache_bust }}"
    """
    return dict(app_version=APP_VERSION, cache_bust=STARTUP_ID)

@app.context_processor
def inject_theme():
    key = get_setting('color_theme', DEFAULT_THEME)
    theme = THEMES.get(key, THEMES['classic'])
    safe_theme = {k: Markup(v) if isinstance(v, str) else v for k, v in theme.items()}
    return dict(theme=safe_theme, theme_key=key, themes=THEMES)

@app.after_request
def add_cache_headers(response):
    """Prevent browsers from caching HTML pages after deployment.

    Static assets use ?v= query params for cache busting.
    HTML responses get no-cache so phones always get fresh pages on reload.
    """
    if 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

init_db()
nuke_all_data()  # NUKE EVERYTHING on every server start
ensure_fixed_codes()  # Load fixed codes from codes.json

import sockets  # noqa: F401 — registers connect/disconnect event handlers

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

    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
