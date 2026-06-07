"""
Collector sources (Layer 1 config).

The set of monitored channels lives in the DB, never hardcoded. This script
helps you populate it from the channels your Telegram account already follows:

    python sources.py --list-telegram     # show channels you can monitor
    python sources.py --import-all        # add every channel as a source
    python sources.py --add <chat_id> <name>
    python sources.py --show              # show configured sources
"""

import argparse
import asyncio

from telethon import TelegramClient

from config import API_HASH, API_ID, SESSION_NAME
from db import add_source, init_db, list_sources


async def telegram_channels() -> list[tuple[int, str]]:
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    out = []
    async for dialog in client.iter_dialogs():
        if dialog.is_channel:
            out.append((dialog.entity.id, dialog.name))
    await client.disconnect()
    return out


def main():
    init_db()
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-telegram", action="store_true")
    ap.add_argument("--import-all", action="store_true")
    ap.add_argument("--add", nargs=2, metavar=("CHAT_ID", "NAME"))
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    if args.list_telegram or args.import_all:
        channels = asyncio.run(telegram_channels())
        for cid, name in channels:
            print(f"{cid}\t{name}")
            if args.import_all:
                add_source(cid, name)
        if args.import_all:
            print(f"\nImported {len(channels)} channels as sources.")
    elif args.add:
        add_source(int(args.add[0]), args.add[1])
        print("Added source:", args.add[1])
    elif args.show:
        for s in list_sources(enabled_only=False):
            flag = "on " if s["enabled"] else "off"
            print(f"[{flag}] {s['chat_id']}\t{s['name']}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
