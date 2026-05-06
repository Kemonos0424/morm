#!/usr/bin/env bash
# Invite a new MORM L1 node to the network.
#
# What this does (idempotent — safe to re-run):
#   1. ssh to the target host, ensure it has python3.11+ and ffmpeg
#   2. rsync morm-l1/ to ~/MORM/morm-l1/ on the target
#   3. set up a Python venv with `cryptography`
#   4. generate a fresh ed25519 producer keypair on the target
#   5. install a LaunchAgent (macOS) or systemd unit (Linux) that runs the
#      node, peering this host as a bootstrap
#   6. submit a REGISTER_PRODUCER tx to the local node so the new producer
#      enters the slot rotation
#
# Usage:
#   ops/invite-node.sh <ssh-target> [--name NAME] [--no-produce]
#
#   ops/invite-node.sh user@<LAN-IP> --name "mac-mini-1"
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 <ssh-target> [--name NAME] [--no-produce]" >&2
  exit 2
fi

TARGET="$1"; shift
NAME="$(echo "$TARGET" | tr '@.:' '_')"
EXTRA_FLAGS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --name)        NAME="$2"; shift 2;;
    --no-produce)  EXTRA_FLAGS="--no-produce"; shift;;
    *) echo "unknown flag: $1" >&2; exit 2;;
  esac
done

LOCAL_HOST="${MORM_LOCAL_HOST:-$(ipconfig getifaddr en0 2>/dev/null || hostname -I | awk '{print $1}')}"
LOCAL_PORT="${MORM_LOCAL_PORT:-8900}"
LOCAL_RPC="http://${LOCAL_HOST}:${LOCAL_PORT}"

L1_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TREAS_FILE="${MORM_TREAS_FILE:-/tmp/k_treas.json}"
[ -f "$TREAS_FILE" ] || { echo "missing treasury keyfile: $TREAS_FILE" >&2; exit 1; }

echo "── ① preflight ssh + tools on $TARGET ──"
ssh -o ConnectTimeout=8 "$TARGET" '
  set -e
  if command -v python3.11 >/dev/null; then PY=python3.11
  elif command -v python3.12 >/dev/null; then PY=python3.12
  elif command -v python3.13 >/dev/null; then PY=python3.13
  else
    echo "no usable python3.11+ found on remote — aborting" >&2; exit 3
  fi
  echo "  python: $($PY --version)"
  command -v ffmpeg >/dev/null && echo "  ffmpeg: $(ffmpeg -version | head -1)" || echo "  ffmpeg: not installed (encoder will not run)"
  echo "  os: $(uname -s)"
'

echo "── ② rsync morm-l1/ → $TARGET:~/MORM/morm-l1/ ──"
ssh "$TARGET" 'mkdir -p ~/MORM/morm-l1'
rsync -az --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' --exclude 'storage' \
  -e ssh "$L1_DIR/" "$TARGET:~/MORM/morm-l1/"

echo "── ③ python venv + cryptography on remote ──"
ssh "$TARGET" '
  set -e
  cd ~/MORM/morm-l1
  if command -v python3.11 >/dev/null; then PY=python3.11
  elif command -v python3.12 >/dev/null; then PY=python3.12
  else PY=python3.13; fi
  if [ ! -x .venv/bin/python ]; then
    "$PY" -m venv .venv
  fi
  .venv/bin/pip install --upgrade pip --quiet
  .venv/bin/pip install cryptography --quiet
'

echo "── ④ generate producer keypair on remote ──"
KEYJSON=$(ssh "$TARGET" 'cd ~/MORM/morm-l1 && .venv/bin/python -m morm_l1.cli keygen')
PROD_SEED=$(echo "$KEYJSON" | python3 -c "import json,sys;print(json.load(sys.stdin)['seed_hex'])")
PROD_PUB=$(echo "$KEYJSON"  | python3 -c "import json,sys;print(json.load(sys.stdin)['pubkey_hex'])")
PROD_ADDR=$(echo "$KEYJSON" | python3 -c "import json,sys;print(json.load(sys.stdin)['address'])")
echo "  pubkey  : $PROD_PUB"
echo "  address : $PROD_ADDR"

echo "── ⑤ install LaunchAgent / systemd unit ──"
TREAS_ADDR=$(python3 -c "import json;print(json.load(open('$TREAS_FILE'))['address'])")
OS=$(ssh "$TARGET" 'uname -s')
if [ "$OS" = "Darwin" ]; then
  ssh "$TARGET" "
    cd ~/MORM/morm-l1
    MORM_PORT=8900 MORM_HOST=0.0.0.0 \
    MORM_DATA_DIR=\"\$HOME/Library/Application Support/morm-l1\" \
    MORM_LOG_DIR=\"\$HOME/Library/Logs/morm-l1\" \
    MORM_EXTRA_FLAGS='$EXTRA_FLAGS' \
    bash ops/install-launchd.sh '$PROD_SEED' '$TREAS_ADDR' '$LOCAL_RPC'
  "
else
  ssh "$TARGET" "
    cd ~/MORM/morm-l1
    cat > /tmp/morm-l1.service <<EOF
[Unit]
Description=MORM L1 node
After=network-online.target

[Service]
ExecStart=\$HOME/MORM/morm-l1/.venv/bin/python -m morm_l1.cli node \\\\
  --data-dir \$HOME/.morm-l1 \\\\
  --producer-seed $PROD_SEED \\\\
  --treasury $TREAS_ADDR \\\\
  --host 0.0.0.0 --port 8900 \\\\
  --peers $LOCAL_RPC $EXTRA_FLAGS
WorkingDirectory=\$HOME/MORM/morm-l1
Environment=PYTHONUNBUFFERED=1
Restart=always

[Install]
WantedBy=default.target
EOF
    mkdir -p ~/.config/systemd/user
    mv /tmp/morm-l1.service ~/.config/systemd/user/morm-l1.service
    systemctl --user daemon-reload
    systemctl --user enable --now morm-l1.service
  "
fi

echo "── ⑥ register producer on local L1 ──"
TREAS_SEED=$(python3 -c "import json;print(json.load(open('$TREAS_FILE'))['seed_hex'])")
"$L1_DIR/.venv/bin/python" - <<PY
import urllib.request, json, sys
sys.path.insert(0, "$L1_DIR")
from morm_l1 import crypto
from morm_l1.tx import Transaction
seed = bytes.fromhex("$TREAS_SEED")
pub  = crypto.pubkey_from_seed(seed)
addr = crypto.address(pub)
nonce = json.loads(urllib.request.urlopen(
    "$LOCAL_RPC/account/" + addr).read())["nonce"]
tx = Transaction.register_producer(pub, nonce,
    producer_pubkey_hex="$PROD_PUB", name="$NAME").sign(seed)
res = json.loads(urllib.request.urlopen(urllib.request.Request(
    "$LOCAL_RPC/tx", method="POST",
    data=json.dumps(tx.to_dict()).encode(),
    headers={"Content-Type":"application/json"})).read())
print(f"  register-producer tx: {res.get('tx_hash','?')[:16]}…  ok={res.get('ok')}")
PY

echo
echo "── ⑦ verify ──"
sleep 3
ssh "$TARGET" 'curl -s http://127.0.0.1:8900/info | head -c 200; echo'
echo
echo "✓ node $NAME ($PROD_ADDR) joined the swarm via $LOCAL_RPC"
