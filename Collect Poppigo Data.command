#!/bin/bash
# ============================================================
#  POPPIGO Q-COM TRACKER — double-click to collect & publish
# ============================================================
#  Runs from YOUR Mac's internet connection (residential IP),
#  which Blinkit allows -- and gives you a MUMBAI dark store.
#  Then pushes the data to GitHub so your dashboard updates.
# ============================================================

cd "$(dirname "$0")"

echo ""
echo "  POPPIGO Q-COM TRACKER"
echo "  ====================="
echo ""

# 1. make sure python bits are present
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ERROR: python3 not found. Install from python.org, then try again."
  echo "  Press any key to close."; read -n 1; exit 1
fi

# 2. pull latest data from GitHub first (so we append, not overwrite)
if command -v git >/dev/null 2>&1 && [ -d .git ]; then
  echo "  Syncing with GitHub..."
  git pull --quiet 2>/dev/null || echo "  (couldn't pull -- continuing with local data)"
fi

# 2b. ensure browser engine is available (needed to get past Blinkit's block)
if ! python3 -c "import playwright" 2>/dev/null; then
  echo "  First-time setup: installing browser engine (2-3 min, one time)..."
  pip3 install --quiet playwright 2>/dev/null || pip3 install --quiet --user playwright
  python3 -m playwright install chromium 2>/dev/null
fi

# 3. collect
echo "  Reading Blinkit (55 products)... browser mode takes ~4-5 min"
echo ""
python3 tracker.py --only blinkit

# 4. recompute
python3 estimate_sales.py >/dev/null 2>&1 || true
python3 market_share.py   >/dev/null 2>&1 || true

# 5. push back to GitHub so the dashboard updates
if command -v git >/dev/null 2>&1 && [ -d .git ]; then
  echo ""
  echo "  Publishing to your dashboard..."
  git add data/*.csv >/dev/null 2>&1
  git commit -m "data $(date '+%Y-%m-%d %H:%M')" --quiet 2>/dev/null && \
    git push --quiet 2>/dev/null && echo "  Published. Dashboard will refresh in ~1 min." || \
    echo "  (nothing new to publish, or git not connected -- see setup note)"
fi

echo ""
echo "  DONE. You can close this window."
echo ""
