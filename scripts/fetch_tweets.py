#!/usr/bin/env python3
"""Fetch new tweets from tracked Twitter accounts via twikit."""

import sys
import json
import asyncio
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "accounts.yaml"
STATE_PATH = PROJECT_ROOT / "data" / "processed.json"

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from auth import get_client


def load_accounts(config_path: Path) -> list:
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("accounts", [])


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"accounts": {}, "last_run": None}
    with open(state_path, "r") as f:
        return json.load(f)


def _parse_tweet(tweet) -> dict:
    """Extract relevant fields from a twikit Tweet object."""
    is_retweet = hasattr(tweet, "retweeted_tweet") and tweet.retweeted_tweet is not None
    retweet_of = None
    if is_retweet and tweet.retweeted_tweet:
        rt = tweet.retweeted_tweet
        retweet_of = {
            "user": rt.user.screen_name if rt.user else None,
            "text": rt.text or "",
            "id": rt.id,
        }

    # Extract quote tweet info
    is_quote = hasattr(tweet, "quoted_tweet") and tweet.quoted_tweet is not None
    quote_of = None
    if is_quote and tweet.quoted_tweet:
        qt = tweet.quoted_tweet
        quote_of = {
            "user": qt.user.screen_name if qt.user else None,
            "text": qt.text or "",
            "id": qt.id,
        }

    # Extract URLs from tweet entities
    urls = []
    if hasattr(tweet, "urls") and tweet.urls:
        for u in tweet.urls:
            if isinstance(u, dict):
                urls.append(u.get("expanded_url") or u.get("url", ""))
            elif hasattr(u, "expanded_url"):
                urls.append(u.expanded_url)

    # Extract hashtags
    hashtags = []
    if hasattr(tweet, "hashtags") and tweet.hashtags:
        hashtags = tweet.hashtags

    created_at = None
    if hasattr(tweet, "created_at") and tweet.created_at:
        created_at = tweet.created_at

    return {
        "id": tweet.id,
        "text": tweet.text or "",
        "created_at": created_at,
        "is_retweet": is_retweet,
        "retweet_of": retweet_of,
        "is_quote": is_quote,
        "quote_of": quote_of,
        "reply_count": getattr(tweet, "reply_count", 0) or 0,
        "retweet_count": getattr(tweet, "retweet_count", 0) or 0,
        "favorite_count": getattr(tweet, "favorite_count", 0) or 0,
        "view_count": getattr(tweet, "view_count", 0) or 0,
        "urls": urls,
        "hashtags": hashtags,
    }


async def fetch_account_tweets(client, handle: str, cutoff: datetime,
                               last_tweet_id: str = None,
                               ignore_state: bool = False) -> list:
    """Fetch tweets for a single account."""
    handle = handle.lstrip("@")
    tweets = []

    try:
        user = await client.get_user_by_screen_name(handle)
    except Exception as e:
        print(f"ERROR: Could not find user @{handle}: {e}", file=sys.stderr)
        return []

    try:
        result = await user.get_tweets("Tweets", count=40)
    except Exception as e:
        if "429" in str(e):
            print(f"WARNING: Rate limited for @{handle}, waiting 60s...", file=sys.stderr)
            await asyncio.sleep(60)
            try:
                result = await user.get_tweets("Tweets", count=40)
            except Exception as e2:
                print(f"ERROR: Rate limit retry failed for @{handle}: {e2}", file=sys.stderr)
                return []
        else:
            print(f"ERROR: Could not fetch tweets for @{handle}: {e}", file=sys.stderr)
            return []

    # Process tweets from result
    page_count = 0
    max_pages = 5  # Limit pagination

    while result and page_count < max_pages:
        for tweet in result:
            parsed = _parse_tweet(tweet)

            # Skip if already processed (by ID comparison)
            if not ignore_state and last_tweet_id and parsed["id"] <= last_tweet_id:
                # Tweets are in reverse chronological order, so we can stop
                return tweets

            # Skip if outside time window
            if parsed["created_at"]:
                try:
                    tweet_time = datetime.strptime(
                        parsed["created_at"],
                        "%a %b %d %H:%M:%S %z %Y"
                    )
                    if tweet_time < cutoff:
                        return tweets
                except (ValueError, TypeError):
                    pass

            tweets.append(parsed)

        # Try next page
        page_count += 1
        if page_count < max_pages:
            try:
                result = await result.next()
            except Exception:
                break
            if not result:
                break
            await asyncio.sleep(1)  # Be gentle between pages

    return tweets


async def async_main(args):
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    accounts = load_accounts(CONFIG_PATH)
    state = load_state(STATE_PATH)

    # Filter to single account if specified
    if args.account:
        target = args.account.lstrip("@").lower()
        accounts = [a for a in accounts if a["handle"].lower() == target]
        if not accounts:
            print(f"ERROR: Account @{target} not found in config.", file=sys.stderr)
            sys.exit(1)

    print(f"Fetching tweets from {len(accounts)} account(s) "
          f"(since {cutoff.strftime('%Y-%m-%d')})...", file=sys.stderr)

    client = await get_client()
    results = []

    for i, acct in enumerate(accounts):
        handle = acct["handle"]
        acct_state = state.get("accounts", {}).get(handle.lower(), {})
        last_tweet_id = None if args.all else acct_state.get("last_tweet_id")

        print(f"[{i+1}/{len(accounts)}] Fetching @{handle}...", file=sys.stderr)

        tweets = await fetch_account_tweets(
            client, handle, cutoff,
            last_tweet_id=last_tweet_id,
            ignore_state=args.all,
        )

        if tweets:
            results.append({
                "account": acct.get("name", handle),
                "handle": handle,
                "category": acct.get("category", "general"),
                "tweets": tweets,
                "tweet_count": len(tweets),
            })
            print(f"  → {len(tweets)} new tweet(s)", file=sys.stderr)
        else:
            print(f"  → no new tweets", file=sys.stderr)

        # Rate limit between accounts
        if i < len(accounts) - 1:
            await asyncio.sleep(2)

    print(f"\nTotal: {sum(r['tweet_count'] for r in results)} tweets "
          f"from {len(results)} account(s)", file=sys.stderr)
    print(json.dumps(results, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Fetch tweets from tracked accounts")
    parser.add_argument("--days", type=int, default=7,
                        help="Number of days to look back (default: 7)")
    parser.add_argument("--account", type=str, default=None,
                        help="Fetch only from this @handle")
    parser.add_argument("--all", action="store_true",
                        help="Ignore processed state, fetch all within time window")
    args = parser.parse_args()

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
