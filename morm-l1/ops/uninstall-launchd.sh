#!/usr/bin/env bash
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.morm.l1.plist"
if [ -f "$PLIST" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "removed $PLIST"
else
  echo "$PLIST not present"
fi
launchctl list 2>/dev/null | grep com.morm.l1 || echo "(no com.morm.l1 entries)"
