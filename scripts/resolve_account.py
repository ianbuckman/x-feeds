#!/usr/bin/env python3
"""Resolve a Twitter @handle to user_id and profile info via twikit."""

import sys
import json
import asyncio
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from auth import get_client


async def resolve_handle(handle: str) -> dict:
    """Resolve @handle to user info."""
    handle = handle.lstrip("@")
    client = await get_client()

    try:
        user = await client.get_user_by_screen_name(handle)
        return {
            "handle": user.screen_name,
            "user_id": user.id,
            "name": user.name,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
            "description": user.description or "",
        }
    except Exception as e:
        print(f"ERROR: Could not resolve @{handle}: {e}", file=sys.stderr)
        return None


def resolve(handle: str) -> dict:
    """Synchronous wrapper for resolve_handle."""
    return asyncio.run(resolve_handle(handle))


def main():
    parser = argparse.ArgumentParser(description="Resolve Twitter @handle to user_id")
    parser.add_argument("handle", help="Twitter @handle (with or without @)")
    args = parser.parse_args()

    result = resolve(args.handle)
    if result is None:
        print(json.dumps({"error": f"Could not resolve @{args.handle.lstrip('@')}"}))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
