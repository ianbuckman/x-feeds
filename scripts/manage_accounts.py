#!/usr/bin/env python3
"""Manage tracked Twitter accounts: add, list, remove."""

import sys
import json
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "accounts.yaml"

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from resolve_account import resolve


def load_config():
    if not CONFIG_PATH.exists():
        return {"accounts": []}
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f) or {"accounts": []}


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def cmd_list(args):
    config = load_config()
    accounts = config.get("accounts", [])
    print(json.dumps(accounts, ensure_ascii=False, indent=2))
    print(f"{len(accounts)} account(s) configured", file=sys.stderr)


def cmd_add(args):
    handle = args.handle.lstrip("@")
    category = args.category

    # Check for duplicates first
    config = load_config()
    for acct in config.get("accounts", []):
        if acct["handle"].lower() == handle.lower():
            print(f"Already exists: @{acct['handle']}", file=sys.stderr)
            print(json.dumps(acct, ensure_ascii=False, indent=2))
            sys.exit(0)

    # Resolve handle to get user_id
    print(f"Resolving @{handle}...", file=sys.stderr)
    result = resolve(handle)
    if result is None:
        print(f"ERROR: Could not resolve @{handle}.", file=sys.stderr)
        sys.exit(1)

    entry = {
        "handle": result["handle"],
        "user_id": result["user_id"],
        "name": result["name"],
        "category": category,
    }

    config.setdefault("accounts", []).append(entry)
    save_config(config)

    print(json.dumps(entry, ensure_ascii=False, indent=2))
    print(f"Added @{result['handle']} ({category})", file=sys.stderr)


def cmd_remove(args):
    handle_query = args.handle.lstrip("@").lower()
    config = load_config()
    accounts = config.get("accounts", [])

    removed = [a for a in accounts if a["handle"].lower() == handle_query]
    if not removed:
        print(json.dumps({"error": f"No account matching @{handle_query} found."}))
        sys.exit(1)

    config["accounts"] = [a for a in accounts if a["handle"].lower() != handle_query]
    save_config(config)

    print(json.dumps(removed, ensure_ascii=False, indent=2))
    print(f"Removed {len(removed)} account(s).", file=sys.stderr)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Manage tracked Twitter accounts")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all tracked accounts")

    p_add = sub.add_parser("add", help="Add a Twitter account")
    p_add.add_argument("handle", help="Twitter @handle")
    p_add.add_argument("--category", default="general",
                       help="Category tag (default: general)")

    p_rm = sub.add_parser("remove", help="Remove an account")
    p_rm.add_argument("handle", help="Twitter @handle to remove")

    args = parser.parse_args()
    {"list": cmd_list, "add": cmd_add, "remove": cmd_remove}[args.command](args)


if __name__ == "__main__":
    main()
