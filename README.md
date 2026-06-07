# Tele-ship Agent — Personal Internship Agent

An AI-powered internship agent. It continuously monitors Telegram job channels,
uses an LLM to understand and score each opportunity against your profile, and
lets you ask about jobs in natural language through Telegram — powered by
[Hermes](https://github.com/NousResearch/Hermes).

It is **not** a scraper, a command bot, or a keyword filter. It is an agent with
memory, reasoning, monitoring, ranking, and a conversational interface.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  HERMES  (qwen3-coder-next · Telegram gateway · routing)      │
│  Does ALL natural-language chat & ranking narrative           │
└───────────────┬──────────────────────────────────────────────┘
                │ MCP (stdio)
                ▼
┌──────────────────────────────────────────────────────────────┐
│  mcp_server.py — tools: get_today_jobs, search_jobs,          │
│  get_job, mark_applied, get_profile, update_profile, stats    │
└───────────────┬──────────────────────────────────────────────┘
                │ shared SQLite (jobs.db)
                ▲
┌───────────────┴──────────────────────────────────────────────┐
│  collector.py (background)                                    │
│  Telethon multi-channel → intelligence.py → jobs.db          │
│  intelligence.py scores each post via Hermes (route B)        │
└──────────────────────────────────────────────────────────────┘
```

**Route B:** no model is called directly. All extraction/scoring goes through
the Hermes CLI (`hermes -z ... -t "" --cli`), which owns the `qwen3-coder-next`
provider and auth.

## Files

| File | Layer | Role |
|------|-------|------|
| `config.py` | — | Secrets + settings (gitignored; see `config.example.py`) |
| `db.py` | Storage | SQLite schema + ops, dedup by content hash |
| `hermes_llm.py` | Intelligence | Route-B wrapper around the Hermes CLI |
| `intelligence.py` | Intelligence | Extract + score a post into structured JSON |
| `profile.py` | Memory | Evolving user preferences |
| `sources.py` | Collectors | Manage monitored channels (nothing hardcoded) |
| `collector.py` | Collectors | Live Telethon listener → intelligence → DB |
| `mcp_server.py` | Agent interface | MCP tools exposed to Hermes |

## Setup

```bash
pip install -r requirements.txt
cp config.example.py config.py     # then fill in your Telegram API_ID / API_HASH
python db.py                        # initialise the database
```

### 1. Choose channels to monitor (no hardcoding)
```bash
python sources.py --list-telegram   # see channels your account follows
python sources.py --import-all      # monitor all of them
# or add specific ones:
python sources.py --add <chat_id> "<name>"
python sources.py --show
```

### 2. Run the collector (background process)
```bash
python collector.py --backfill 20   # analyse recent history + go live
```
Each new post is scored by Hermes and stored if relevant.

### 3. Register the MCP tools with Hermes
```bash
hermes mcp add internship --command python --args <abs-path>\mcp_server.py
hermes tools enable internship
```

### 4. Chat on Telegram
> "What internships came today?"
> "Any AI/ML roles for 2027 grads?"
> "Did anything arrive from Jobvisit?"
> "Add cybersecurity to my interests."
> "Mark job 12 as applied."

Hermes understands intent and calls the right tool.

## Roadmap

- **Phase 1 (done):** multi-channel collection, LLM extraction + scoring,
  dedup, NL querying via Hermes tools, evolving profile.
- **Phase 2:** daily summaries, richer memory of shown/ignored jobs.
- **Phase 3:** proactive notifications (`hermes cron` / `hermes send`),
  application tracking, resume matching, company tracking.

## Security

`config.py` and `*.session` are **gitignored**. The `.session` file is a live
login to your Telegram account — never commit or share it.
