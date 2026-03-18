# Tweet Insights

## Overview
Monitor Twitter/X accounts, fetch tweets, analyze with Claude, push insights to Notion.

## Architecture
- Python scripts in `scripts/` handle data fetching (twikit + browser cookies)
- Claude Code skill at `.claude/skills/tweet-insights/SKILL.md` orchestrates the workflow
- State tracked in `data/processed.json` (gitignored)
- Notion database "Tweet Insights" stores all analysis

## Running
- User invokes `/tweet-insights` to trigger the full workflow
- User invokes `/accounts` to manage tracked accounts
- Python 3.9+ required with packages in requirements.txt
- Requires logged-in Twitter session in browser (cookies extracted via rookiepy)

## Conventions
- All Python scripts output JSON to stdout, errors/warnings to stderr
- Scripts use absolute paths relative to PROJECT_ROOT
- Each script is independently runnable for debugging
- twikit is async — scripts use `asyncio.run()` at entry point
