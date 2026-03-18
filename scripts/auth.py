#!/usr/bin/env python3
"""Manage Twitter authentication via browser cookie extraction."""

import sys
import json
import asyncio
import argparse
from pathlib import Path

from twikit import Client

# Monkey-patch twikit ClientTransaction.init() to fix #304:
# https://github.com/d60/twikit/issues/304
# self.home_page_response was set before self.key, causing AttributeError
# on retry if intermediate steps fail. Move it to the end so the guard
# flag is only set after all attributes are successfully initialized.
from twikit.x_client_transaction.transaction import ClientTransaction, handle_x_migration

_original_ct_init = ClientTransaction.init

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
