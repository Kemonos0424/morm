#!/bin/sh
# MORM L1 entrypoint.
#
# Required env:
#   PRODUCER_SEED            — 64-hex ed25519 seed (or: --no-produce mode)
#   TREASURY                 — m0r…/0x…40hex
# Optional env:
#   MORM_PORT                — default 8900
#   PEERS                    — comma-separated peer URLs (overrides seeds.json bake-in)
#   DAG_MODE                 — "1" to enable --dag-mode
#   QUIC                     — "1" to enable --quic
#   GENESIS_LOCKDOWN_HEIGHT  — int, default 100; 0 disables
#   NO_PRODUCE               — "1" for passive importer
#   DATA_DIR                 — default /data/l1
set -eu

DATA_DIR="${DATA_DIR:-/data/l1}"
MORM_PORT="${MORM_PORT:-8900}"
mkdir -p "$DATA_DIR"

if [ -z "${PRODUCER_SEED:-}" ] && [ "${NO_PRODUCE:-0}" != "1" ]; then
    if [ -f "$DATA_DIR/producer.seed" ]; then
        PRODUCER_SEED="$(cat "$DATA_DIR/producer.seed")"
        echo "[l1] reusing PRODUCER_SEED from $DATA_DIR/producer.seed"
    else
        echo "[l1] generating fresh producer seed → $DATA_DIR/producer.seed"
        python3 - <<'PY'
import os, secrets, sys
sys.path.insert(0, '/app')
from morm_l1 import crypto
seed = secrets.token_bytes(32)
pub = crypto.pubkey_from_seed(seed)
out = '/data/l1/producer.seed'
with open(out, 'w') as f: f.write(seed.hex())
os.chmod(out, 0o600)
with open('/data/l1/producer.pub', 'w') as f: f.write(pub.hex())
with open('/data/l1/producer.address', 'w') as f: f.write(crypto.address(pub))
print(f"[l1] producer addr = {crypto.address(pub)}")
PY
        PRODUCER_SEED="$(cat "$DATA_DIR/producer.seed")"
    fi
fi

if [ -z "${TREASURY:-}" ]; then
    echo "[l1] FATAL: TREASURY env required (m0r… address)"
    exit 1
fi

ARGS="--data-dir $DATA_DIR --treasury $TREASURY --port $MORM_PORT --host 0.0.0.0"
[ -n "${PRODUCER_SEED:-}" ] && ARGS="$ARGS --producer-seed $PRODUCER_SEED"
[ "${NO_PRODUCE:-0}" = "1" ] && ARGS="$ARGS --no-produce"
[ "${DAG_MODE:-0}" = "1" ] && ARGS="$ARGS --dag-mode"
[ "${QUIC:-0}" = "1" ] && ARGS="$ARGS --quic"
[ -n "${GENESIS_LOCKDOWN_HEIGHT:-}" ] && ARGS="$ARGS --genesis-lockdown-height $GENESIS_LOCKDOWN_HEIGHT"

# Phase 30c: when PEERS env is unset, the cli.py seed_loader auto-merges
# baked-in /app/morm_l1/seeds.json + user-mutable /data/l1/seeds.json
# + live discovery (github raw / DNS SRV) for us. Passing PEERS via env
# explicitly overrides everything.
[ -n "${PEERS:-}" ] && ARGS="$ARGS --peers $PEERS"
[ "${NO_SEED_DISCOVERY:-0}" = "1" ] && ARGS="$ARGS --no-seed-discovery"

echo "[l1] python -m morm_l1.cli node $ARGS"
exec python -m morm_l1.cli node $ARGS
