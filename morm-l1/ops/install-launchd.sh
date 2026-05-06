#!/usr/bin/env bash
# Install the MORM L1 node as a macOS LaunchAgent.
#
# Usage:
#   ops/install-launchd.sh <producer-seed-hex> <treasury-addr> [<peer-url>...]
#
#   ops/install-launchd.sh \
#       3b5557fe8c4c09188005bd2b23b2451e2674d850209cbbc8df3e15ca026aafe1 \
#       0xdba3eeb3c90b561f15a3d36b8580fadd5dde0d58 \
#       http://<LAN-IP>:8900
#
# Add `--no-produce` to MORM_EXTRA_FLAGS to run a passive importer instead.
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "usage: $0 <producer-seed-hex> <treasury-addr> [peer1] [peer2] ..." >&2
  exit 2
fi

SEED="$1"; shift
TREASURY="$1"; shift
PEERS=$(IFS=,; echo "$*")

MORM_L1_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${MORM_L1_DIR}/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3.11 || command -v python3 || true)"
fi
if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
  echo "no usable python found" >&2; exit 1
fi

DATA_DIR="${MORM_DATA_DIR:-$HOME/Library/Application Support/morm-l1}"
LOG_DIR="${MORM_LOG_DIR:-$HOME/Library/Logs/morm-l1}"
PORT="${MORM_PORT:-8900}"
HOST="${MORM_HOST:-0.0.0.0}"
EXTRA_FLAGS="${MORM_EXTRA_FLAGS:-}"

mkdir -p "$DATA_DIR" "$LOG_DIR" "$HOME/Library/LaunchAgents"

# Build EXTRA_FLAGS as plist-safe <string> elements
extra_xml=""
for f in $EXTRA_FLAGS; do
  extra_xml+="        <string>$f</string>"$'\n'
done

PLIST="$HOME/Library/LaunchAgents/com.morm.l1.plist"
template="$MORM_L1_DIR/ops/com.morm.l1.plist.template"

sed \
  -e "s#@PYTHON@#${PYTHON}#g" \
  -e "s#@MORM_L1_DIR@#${MORM_L1_DIR}#g" \
  -e "s#@DATA_DIR@#${DATA_DIR}#g" \
  -e "s#@LOG_DIR@#${LOG_DIR}#g" \
  -e "s#@PRODUCER_SEED@#${SEED}#g" \
  -e "s#@TREASURY@#${TREASURY}#g" \
  -e "s#@HOST@#${HOST}#g" \
  -e "s#@PORT@#${PORT}#g" \
  -e "s#@PEERS@#${PEERS}#g" \
  "$template" | \
  awk -v ex="$extra_xml" '/@EXTRA_FLAGS@/ { printf "%s", ex; next } { print }' \
  > "$PLIST"

echo "wrote $PLIST"
echo "  python  : $PYTHON"
echo "  data    : $DATA_DIR"
echo "  logs    : $LOG_DIR/{morm-l1.out.log,morm-l1.err.log}"
echo "  bind    : ${HOST}:${PORT}"
echo "  peers   : ${PEERS:-(none)}"
echo "  extras  : ${EXTRA_FLAGS:-(none)}"
echo

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"
echo "launchctl loaded com.morm.l1"
echo
sleep 2
launchctl list | grep com.morm.l1 || echo "(not running yet — check ${LOG_DIR}/morm-l1.err.log)"
echo
echo "── /info ──"
curl -s --max-time 3 "http://127.0.0.1:${PORT}/info" | head -c 200; echo
