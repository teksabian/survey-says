import os

# Use GeventWebSocketWorker for real WebSocket support (not polling fallback).
# Gunicorn auto-loads this file even when Render runs bare 'gunicorn app:app'.
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"

# Single worker — ephemeral SQLite DB is not shared across processes.
workers = 1

# Long-lived WebSocket connections need a generous timeout.
timeout = 120

# Render assigns port via $PORT env var.
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
