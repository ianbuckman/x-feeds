#!/usr/bin/env python3
"""Manage processed tweet state per account."""

import json
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "processed.json"


def _ensure_data_dir():
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"accounts": {}, "last_run": None}
    with open(STATE_PATH, "r") as f:
        return json.load(f)


def save_state(state: dict):
    _ensure_data_dir()
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def mark_account(handle: str, last_tweet_id: str = "",
                 notion_page_id: str = ""):
    handle = handle.lstrip("@").lower()
    state = load_state()
    state.setdefault("accounts", {})
    state["accounts"][handle] = {
        "last_tweet_id": last_tweet_id,
        "last_fetch": datetime.now(timezone.utc).isoformat(),
        "notion_page_id": notion_page_id,
    }
    save_state(state)


def update_last_run():
    state = load_state()
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state)


def reset_account(handle: str):
    handle = handle.lstrip("@").lower()
    state = load_state()
    if handle in state.get("accounts", {}):
        del state["accounts"][handle]
        save_state(state)
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Manage tweet processing state")
    sub = parser.add_subparsers(dest="command", required=True)

    p_mark = sub.add_parser("mark", help="Mark account as processed")
    p_mark.add_argument("handle", help="Twitter @handle")
    p_mark.add_argument("--last-tweet-id", default="", help="ID of latest processed tweet")
    p_mark.add_argument("--notion-page-id", default="", help="Notion page ID")

    sub.add_parser("check-time", help="Update last_run timestamp")
    sub.add_parser("show", help="Show state summary")

    p_reset = sub.add_parser("reset", help="Reset state for an account")
    p_reset.add_argument("handle", help="Twitter @handle to reset")

    args = parser.parse_args()

    if args.command == "mark":
        mark_account(args.handle, args.last_tweet_id,
                     getattr(args, "notion_page_id", ""))
        print(f"Marked @{args.handle.lstrip('@')} as processed", file=sys.stderr)
    elif args.command == "check-time":
        update_last_run()
        print("Updated last_run timestamp", file=sys.stderr)
    elif args.command == "show":
        state = load_state()
        summary = {
            "total_accounts": len(state.get("accounts", {})),
            "last_run": state.get("last_run"),
            "accounts": state.get("accounts", {}),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    elif args.command == "reset":
        handle = args.handle.lstrip("@")
        if reset_account(handle):
            print(f"Reset state for @{handle}", file=sys.stderr)
        else:
            print(f"No state found for @{handle}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
