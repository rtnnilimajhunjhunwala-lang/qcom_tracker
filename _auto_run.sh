#!/bin/bash
cd "/Users/nilima/Documents/qcom_tracker"
# only run during waking hours 8am-11pm IST-ish (local time)
H=$(date +%H)
if [ "$H" -lt 8 ] || [ "$H" -gt 22 ]; then exit 0; fi
[ -d .git ] && git pull --quiet 2>/dev/null
python3 tracker.py --only blinkit >> _auto_log.txt 2>&1
python3 estimate_sales.py >/dev/null 2>&1
python3 market_share.py >/dev/null 2>&1
if [ -d .git ]; then
  git add data/*.csv >/dev/null 2>&1
  git commit -m "auto $(date '+%Y-%m-%d %H:%M')" --quiet 2>/dev/null
  git push --quiet 2>/dev/null
fi
