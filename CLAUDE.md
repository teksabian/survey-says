# CLAUDE.md

## Project

Family Feud — a pub trivia game built with Python 3.11 and Flask. Deployed on Render.com.

## Git Workflow

- **Never push directly to main.** Always create a feature branch.
- Name branches with the Jira key: `FEUD-<number>/<short-description>` (e.g., `FEUD-12/add-host-dashboard`)
- Include the Jira key in commit messages: `FEUD-12: Add host dashboard scoring view`
- Include the Jira key in PR titles: `FEUD-12: Add host dashboard`
- Open a PR when work is complete and request review.

## Development

```bash
pip install -r requirements.txt   # Install dependencies
python app.py                     # Run locally on port 5000
python -m unittest discover tests/ # Run tests
```

## Architecture

- Modular Flask app: `app.py` (entry point), `config.py`, `database.py`, `auth.py`, `ai.py`, `parsers.py`, with route blueprints in `routes/` and Jinja2 templates in `templates/`.
- All state is ephemeral — SQLite on ephemeral filesystem, wiped on every server restart (nuclear reset design).
- AI scoring via Anthropic Claude API is optional (`ENABLE_AI_SCORING` env var).
- Environment variables are documented in `.env.example` and in `README.md`.
- Tests use Python `unittest` in `tests/`.
