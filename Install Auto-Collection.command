#!/bin/bash
# ============================================================
#  POPPIGO — install automatic hourly collection (one time)
#  Double-click this ONCE. After that, data collects by itself
#  every hour your Mac is awake -- even after a restart.
# ============================================================

cd "$(dirname "$0")"
FOLDER="$(pwd)"
LABEL="com.poppigo.qcom"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo ""
echo "  Installing automatic collection..."
echo "  Folder: $FOLDER"
echo ""

# sanity: python + files present
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ERROR: python3 not found. Install from python.org first."
  echo "  Press any key to close."; read -n 1; exit 1
fi
if [ ! -f "$FOLDER/tracker.py" ]; then
  echo "  ERROR: tracker.py not found here. Keep this file INSIDE the qcom_tracker folder."
  echo "  Press any key to close."; read -n 1; exit 1
fi

# make a small runner the scheduler will call
# ensure browser engine present (one-time)
if ! python3 -c "import playwright" 2>/dev/null; then
  echo "  Installing browser engine (one-time, 2-3 min)..."
  pip3 install --quiet playwright 2>/dev/null || pip3 install --quiet --user playwright
  python3 -m playwright install chromium 2>/dev/null
fi

cat > "$FOLDER/_auto_run.sh" << RUNNER
#!/bin/bash
cd "$FOLDER"
# only run during waking hours 8am-11pm IST-ish (local time)
H=\$(date +%H)
if [ "\$H" -lt 8 ] || [ "\$H" -gt 22 ]; then exit 0; fi
[ -d .git ] && git pull --quiet 2>/dev/null
python3 tracker.py --only blinkit >> _auto_log.txt 2>&1
python3 estimate_sales.py >/dev/null 2>&1
python3 market_share.py >/dev/null 2>&1
if [ -d .git ]; then
  git add data/*.csv >/dev/null 2>&1
  git commit -m "auto \$(date '+%Y-%m-%d %H:%M')" --quiet 2>/dev/null
  git push --quiet 2>/dev/null
fi
RUNNER
chmod +x "$FOLDER/_auto_run.sh"

# create the LaunchAgent: runs hourly, catches missed runs on wake, survives reboot
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" << PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
    <array><string>/bin/bash</string><string>$FOLDER/_auto_run.sh</string></array>
  <key>StartInterval</key><integer>3600</integer>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
PL

# load it (and reload if already installed)
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST" 2>/dev/null

echo "  ============================================"
echo "  DONE. Automatic collection is now ON."
echo ""
echo "  - Runs every hour your Mac is awake"
echo "  - Restarts itself after a reboot"
echo "  - Catches up after sleep when you reopen the Mac"
echo "  - Only collects 8am-11pm (skips the quiet night hours)"
echo ""
echo "  First run is happening right now. Check your dashboard"
echo "  in ~3 minutes."
echo "  ============================================"
echo ""
echo "  To STOP it later, double-click 'Stop Auto-Collection'."
echo "  Press any key to close."
read -n 1
