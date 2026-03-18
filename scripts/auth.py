#!/usr/bin/env python3
"""Manage Twitter authentication via browser cookie extraction."""

import re
import sys
import json
import asyncio
import argparse
from pathlib import Path

from twikit import Client

# Monkey-patch twikit ClientTransaction to fix two issues:
# 1. #304: AttributeError on retry (init order fix)
# 2. ON_DEMAND_FILE_REGEX no longer matches X.com's new webpack chunk format.
#    Old format: "ondemand.s": "HASH"
#    New format: CHUNK_ID:"ondemand.s" with hash in a separate mapping.
from twikit.x_client_transaction.transaction import (
    ClientTransaction, handle_x_migration, INDICES_REGEX,
)

_original_get_indices = ClientTransaction.get_indices

async def _patched_get_indices(self, home_page_response, session, headers):
    """Find ondemand.s JS file using new webpack chunk format and extract key byte indices."""
    response_text = str(home_page_response)

    # Try the original approach first
    try:
        return await _original_get_indices(self, home_page_response, session, headers)
    except Exception:
        pass

    # Fallback: new X.com format where chunk IDs map to names separately from hashes
    # Find chunk ID: e.g. 20113:"ondemand.s"
    chunk_match = re.search(r'(\d+):"ondemand\.s"', response_text)
    if not chunk_match:
        raise Exception("Couldn't find ondemand.s chunk ID in home page")

    chunk_id = chunk_match.group(1)

    # Find all hash candidates for this chunk ID: e.g. 20113:"2507f89"
    # The hash mapping is in a different part of the JS, so find all matches
    hash_candidates = re.findall(chunk_id + r':"([a-f0-9]{6,12})"', response_text)
    if not hash_candidates:
        raise Exception(f"Couldn't find hash for ondemand.s chunk {chunk_id}")

    # Try each hash candidate with retries (network can be flaky)
    last_error = None
    for chunk_hash in hash_candidates:
        url = f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{chunk_hash}a.js"
        for attempt in range(3):
            try:
                js_resp = await session.request(method="GET", url=url, headers=headers)
                if js_resp.status_code != 200:
                    last_error = f"HTTP {js_resp.status_code}"
                    break  # non-retryable
                key_byte_indices = []
                for item in INDICES_REGEX.finditer(str(js_resp.text)):
                    key_byte_indices.append(item.group(2))
                if key_byte_indices:
                    key_byte_indices = list(map(int, key_byte_indices))
                    print(f"Found KEY_BYTE indices via new format (chunk {chunk_id}, hash {chunk_hash})",
                          file=sys.stderr)
                    return key_byte_indices[0], key_byte_indices[1:]
                last_error = "INDICES_REGEX matched nothing"
                break  # non-retryable
            except Exception as e:
                last_error = str(e)
                if attempt < 2:
                    import asyncio as _aio
                    await _aio.sleep(2)
                continue

    raise Exception(f"Couldn't get KEY_BYTE indices: {last_error}")

ClientTransaction.get_indices = _patched_get_indices

async def _patched_ct_init(self, session, headers):
    home_page_response = await handle_x_migration(session, headers)
    home_page_response = self.validate_response(home_page_response)
    self.DEFAULT_ROW_INDEX, self.DEFAULT_KEY_BYTES_INDICES = await self.get_indices(
        home_page_response, session, headers)
    self.key = self.get_key(response=home_page_response)
    self.key_bytes = self.get_key_bytes(key=self.key)
    self.animation_key = self.get_animation_key(
        key_bytes=self.key_bytes, response=home_page_response)
    self.home_page_response = home_page_response  # only set on full success

ClientTransaction.init = _patched_ct_init

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COOKIES_PATH = PROJECT_ROOT / "data" / "cookies.json"

# Browser names rookiepy supports
BROWSERS = ["chrome", "arc", "brave", "edge", "safari", "chromium", "opera", "vivaldi"]


def _ensure_data_dir():
    COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)


def _extract_twitter_cookies(browser_name: str = None) -> dict:
    """Extract Twitter/X cookies from browser using rookiepy."""
    import rookiepy

    domains = [".twitter.com", ".x.com", "twitter.com", "x.com"]
    cookies = {}

    browsers_to_try = [browser_name] if browser_name else BROWSERS

    for name in browsers_to_try:
        fn = getattr(rookiepy, name, None)
        if fn is None:
            continue
        try:
            raw = fn(domains)
            for c in raw:
                cookies[c["name"]] = c["value"]
            if cookies:
                print(f"Extracted {len(cookies)} cookies from {name}", file=sys.stderr)
                return cookies
        except Exception as e:
            print(f"WARNING: Could not read cookies from {name}: {e}", file=sys.stderr)
            continue

    return cookies


def _save_cookies(cookies: dict):
    """Save cookies as simple key-value JSON for twikit."""
    _ensure_data_dir()
    with open(COOKIES_PATH, "w") as f:
        json.dump(cookies, f, indent=2)
    print(f"Saved cookies to {COOKIES_PATH}", file=sys.stderr)


def cmd_import_cookies(args):
    """Import cookies from browser."""
    browser = getattr(args, "browser", None)
    cookies = _extract_twitter_cookies(browser)

    if not cookies:
        print("ERROR: No Twitter cookies found in any browser. "
              "Make sure you're logged into Twitter/X.", file=sys.stderr)
        sys.exit(1)

    # Check for essential cookies
    essential = ["auth_token", "ct0"]
    missing = [k for k in essential if k not in cookies]
    if missing:
        print(f"WARNING: Missing essential cookies: {missing}. "
              "Authentication may not work.", file=sys.stderr)

    _save_cookies(cookies)
    print(json.dumps({"status": "ok", "cookie_count": len(cookies)}))


async def _check_cookies() -> bool:
    """Verify cookies by making a test API call."""
    if not COOKIES_PATH.exists():
        return False

    client = Client("en-US")
    client.load_cookies(str(COOKIES_PATH))

    try:
        # Try to get own user info as a test
        user = await client.user()
        print(f"Authenticated as: @{user.screen_name}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"Cookie validation failed: {e}", file=sys.stderr)
        return False


def cmd_check(args):
    """Check if cookies are valid."""
    if not COOKIES_PATH.exists():
        print(json.dumps({"status": "no_cookies",
                          "message": "No cookies found. Run: python3 scripts/auth.py import-cookies"}))
        sys.exit(1)

    valid = asyncio.run(_check_cookies())
    if valid:
        print(json.dumps({"status": "ok", "message": "Cookies are valid"}))
    else:
        print(json.dumps({"status": "expired",
                          "message": "Cookies expired. Run: python3 scripts/auth.py import-cookies"}))
        sys.exit(1)


async def get_client() -> Client:
    """Get an authenticated twikit client. Used by other scripts."""
    if not COOKIES_PATH.exists():
        print("ERROR: No cookies found. Run: python3 scripts/auth.py import-cookies",
              file=sys.stderr)
        sys.exit(1)

    client = Client("en-US")
    client.load_cookies(str(COOKIES_PATH))
    return client


def main():
    parser = argparse.ArgumentParser(description="Manage Twitter authentication")
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import-cookies",
                              help="Extract Twitter cookies from browser")
    p_import.add_argument("--browser", choices=BROWSERS, default=None,
                          help="Specific browser to extract from")

    sub.add_parser("check", help="Verify cookies are valid")

    args = parser.parse_args()
    {"import-cookies": cmd_import_cookies, "check": cmd_check}[args.command](args)


if __name__ == "__main__":
    main()
