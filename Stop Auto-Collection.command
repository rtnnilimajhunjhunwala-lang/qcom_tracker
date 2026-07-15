#!/bin/bash
launchctl unload "$HOME/Library/LaunchAgents/com.poppigo.qcom.plist" 2>/dev/null
rm -f "$HOME/Library/LaunchAgents/com.poppigo.qcom.plist"
echo ""
echo "  Automatic collection STOPPED and removed."
echo "  (You can still collect manually with 'Collect Poppigo Data'.)"
echo "  Press any key to close."
read -n 1
