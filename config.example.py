"""
Configuration for the internship agent.

Copy this file to `config.py` and fill in your Telegram API credentials.
`config.py` is gitignored because it holds secrets.

Get API_ID / API_HASH from https://my.telegram.org -> API development tools.
"""
import os
_HERE = os.path.dirname(os.path.abspath(__file__))

# ── Telegram (secret) ──────────────────────────────────────────────
API_ID = 12345678
API_HASH = "your_api_hash_here"

# Telethon session name (a <name>.session file is created on first login).
SESSION_NAME = "faizan_session"

# ── Intelligence: Hermes (route B) ─────────────────────────────────
# We do not call any model directly. All extraction/scoring goes through
# the Hermes CLI one-shot mode, which owns the qwen3-coder-next provider.
HERMES_BIN = "hermes"          # resolved on PATH; override with abs path if needed
HERMES_MODEL = "qwen3-coder-next"
HERMES_TIMEOUT = 180           # seconds per inference call

# ── Storage ────────────────────────────────────────────────────────
# Absolute path so the collector AND the MCP server (launched by Hermes from a
# different working directory) always open the SAME database.
DB_PATH = os.path.join(_HERE, "jobs.db")

# Minimum relevance score (0-100) for a post to be stored as a job.
MIN_STORE_SCORE = 40
