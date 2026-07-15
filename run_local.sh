#!/usr/bin/env bash
# Residential run: collects ALL three platforms from your home/office wifi.
# Zepto & Instamart block datacenter IPs, so they only work when run locally.
# Blinkit is also collected here for a full same-moment cross-platform snapshot.
set -e
cd "$(dirname "$0")"

echo "▶ Q-Com tracker — full local run (Blinkit + Zepto + Instamart)"
python3 tracker.py --only blinkit,zepto,instamart
echo "▶ Recomputing sales estimates…"
python3 estimate_sales.py || true
echo "✓ Done. Open dashboard.html and load data/snapshots.csv"
