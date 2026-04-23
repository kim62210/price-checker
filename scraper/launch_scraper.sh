#!/bin/bash
# nodriver 기반 scraper 런처. 기존 Chrome CDP 런처를 재사용하고 Python 3.12 venv 로 uvicorn 기동.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"

# Chrome CDP 보장 (원래 경로 그대로 재사용)
/Users/hj/scraper/launch_chrome_cdp.sh || {
    echo "$(date '+%F %T') failed to ensure chrome cdp — aborting scraper" >&2
    exit 1
}

export SCRAPER_CDP_URL="${SCRAPER_CDP_URL:-http://localhost:9222}"

exec /Users/hj/scraper-venv-nodriver/bin/python -m uvicorn app:app \
    --app-dir "$HERE" \
    --host 0.0.0.0 \
    --port 8081
