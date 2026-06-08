"""
Collector (Layer 1).

Long-running process. Listens for new messages on the configured source
channels, runs each through the intelligence layer (Hermes / qwen3-coder-next),
and stores relevant, deduplicated, scored jobs.

    python collector.py            # live: monitor configured sources
    python collector.py --backfill 20   # also analyse last N msgs per source

If no sources are configured yet, run `python sources.py --import-all` first.
"""

import argparse
import asyncio

from telethon import TelegramClient, events

from config import (
    API_HASH,
    API_ID,
    BACKFILL_DEFAULT,
    MIN_STORE_SCORE,
    SCORE_DELAY_SECONDS,
    SESSION_NAME,
)
from db import get_profile, hash_text, init_db, job_exists, list_sources, save_job
from intelligence import analyse
from hermes_llm import HermesError


async def process_message(source_name: str, text: str, posted_at):
    """Analyse one message and store it if relevant + new. Returns job or None."""
    if not text or not text.strip():
        return None

    content_hash = hash_text(text)
    if job_exists(content_hash):
        return None  # dedup before spending an LLM call

    try:
        data = analyse(text, get_profile())
    except HermesError as e:
        print(f"  ! intelligence failed: {e}")
        return None
    finally:
        # Throttle AI calls to stay under Ollama Cloud free-tier limits.
        await asyncio.sleep(SCORE_DELAY_SECONDS)

    if not data["is_job"] or data["score"] < MIN_STORE_SCORE:
        return None

    data.update(
        content_hash=content_hash,
        source=source_name,
        full_text=text,
        posted_at=str(posted_at) if posted_at else None,
    )
    row_id = save_job(data)
    if row_id:
        print(
            f"\n  ✓ JOB #{row_id}  [{data['score']}/100]  "
            f"{data['company'] or '?'} — {data['role'] or '?'}\n"
            f"    {data['summary']}"
        )
        return data
    return None


async def backfill(client, sources, n):
    print(f"Backfilling last {n} messages per source...")
    for s in sources:
        try:
            async for msg in client.iter_messages(s["chat_id"], limit=n):
                await process_message(s["name"], msg.text, msg.date)
        except Exception as e:  # channel might be inaccessible
            print(f"  ! {s['name']}: {e}")


async def run(backfill_n: int = 0):
    init_db()
    sources = list_sources(enabled_only=True)
    if not sources:
        print("No sources configured. Run: python sources.py --import-all")
        return

    chat_ids = [s["chat_id"] for s in sources]
    name_by_id = {s["chat_id"]: s["name"] for s in sources}
    print(f"Monitoring {len(sources)} channels:")
    for s in sources:
        print(f"  • {s['name']}")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    if backfill_n:
        await backfill(client, sources, backfill_n)

    @client.on(events.NewMessage(chats=chat_ids))
    async def handler(event):
        name = name_by_id.get(event.chat_id, str(event.chat_id))
        await process_message(name, event.raw_text, event.message.date)

    print("\nListening for new posts...  (Ctrl+C to stop)")
    await client.run_until_disconnected()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=int, default=BACKFILL_DEFAULT,
                    help="analyse the last N messages of each source on start")
    args = ap.parse_args()
    try:
        asyncio.run(run(args.backfill))
    except KeyboardInterrupt:
        print("\nStopped.")
