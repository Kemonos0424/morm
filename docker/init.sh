#!/usr/bin/env bash
# MORM federated node — first-boot key generation (Phase 30b).
#
# Usage (run once before `docker compose up`):
#   docker/init.sh
#
# What it does:
#   1. Creates ./data/{l1,gateway,edge}/ if missing
#   2. Generates a producer ed25519 seed → data/l1/producer.{seed,pub,address}
#   3. Generates a treasury ed25519 seed → data/gateway/treasury.seed (0o600)
#   4. Writes data/gateway/treasury.address for reference
#   5. Patches `.env` (creating from .env.example if absent) so TREASURY,
#      TREASURY_SEED_FILE and TREASURY_KEYFILE_HOST point at the new files
#
# Idempotent: re-runs are safe; existing keys are reused.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKER_DIR="$ROOT/docker"
DATA_DIR="$DOCKER_DIR/data"
ENV_FILE="$DOCKER_DIR/.env"
EXAMPLE="$DOCKER_DIR/.env.example"

mkdir -p "$DATA_DIR/l1" "$DATA_DIR/gateway" "$DATA_DIR/edge"

if [ ! -f "$ENV_FILE" ]; then
    cp "$EXAMPLE" "$ENV_FILE"
    echo "[init] created $ENV_FILE from .env.example"
fi

PYBIN="$ROOT/morm-l1/.venv/bin/python"
if [ ! -x "$PYBIN" ]; then
    echo "[init] FATAL: morm-l1/.venv/bin/python missing — bootstrap the venv first:"
    echo "       cd $ROOT/morm-l1 && python3.11 -m venv .venv && .venv/bin/pip install cryptography"
    exit 1
fi

# ---- producer key ----
PROD_SEED_FILE="$DATA_DIR/l1/producer.seed"
PROD_ADDR_FILE="$DATA_DIR/l1/producer.address"
if [ ! -s "$PROD_SEED_FILE" ]; then
    "$PYBIN" - <<PY
import sys, secrets, os
sys.path.insert(0, "$ROOT/morm-l1")
from morm_l1 import crypto
seed = secrets.token_bytes(32)
pub = crypto.pubkey_from_seed(seed)
os.makedirs("$DATA_DIR/l1", exist_ok=True)
with open("$PROD_SEED_FILE", "w") as f: f.write(seed.hex())
os.chmod("$PROD_SEED_FILE", 0o600)
with open("$PROD_ADDR_FILE", "w") as f: f.write(crypto.address(pub))
PY
    echo "[init] generated producer seed (addr=$(cat "$PROD_ADDR_FILE"))"
else
    echo "[init] reusing producer seed (addr=$(cat "$PROD_ADDR_FILE"))"
fi

# ---- treasury key ----
TREAS_SEED_FILE="$DATA_DIR/gateway/treasury.seed"
TREAS_ADDR_FILE="$DATA_DIR/gateway/treasury.address"
if [ ! -s "$TREAS_SEED_FILE" ]; then
    "$PYBIN" - <<PY
import sys, secrets, os
sys.path.insert(0, "$ROOT/morm-l1")
from morm_l1 import crypto
seed = secrets.token_bytes(32)
pub = crypto.pubkey_from_seed(seed)
os.makedirs("$DATA_DIR/gateway", exist_ok=True)
with open("$TREAS_SEED_FILE", "w") as f: f.write(seed.hex())
os.chmod("$TREAS_SEED_FILE", 0o600)
with open("$TREAS_ADDR_FILE", "w") as f: f.write(crypto.address(pub))
PY
    echo "[init] generated treasury seed (addr=$(cat "$TREAS_ADDR_FILE"))"
else
    echo "[init] reusing treasury seed (addr=$(cat "$TREAS_ADDR_FILE"))"
fi

TREAS_ADDR="$(cat "$TREAS_ADDR_FILE")"

# ---- patch .env ----
patch_env() {
    local key="$1"; local val="$2"
    if grep -q "^${key}=" "$ENV_FILE"; then
        # macOS sed needs '' after -i
        sed -i.bak "s|^${key}=.*|${key}=${val}|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
    else
        echo "${key}=${val}" >> "$ENV_FILE"
    fi
}
patch_env TREASURY "$TREAS_ADDR"
patch_env TREASURY_SEED_FILE "/data/treasury.seed"
# bind the treasury keyfile read-only into the gateway container
patch_env TREASURY_KEYFILE_HOST "$TREAS_SEED_FILE"

echo
echo "[init] DONE."
echo "       producer addr  = $(cat "$PROD_ADDR_FILE")"
echo "       treasury addr  = $TREAS_ADDR"
echo
echo "Next:"
echo "  cd $DOCKER_DIR"
echo "  docker compose -f morm-node.docker-compose.yml --env-file .env build"
echo "  docker compose -f morm-node.docker-compose.yml --env-file .env up -d"
echo "  docker compose -f morm-node.docker-compose.yml logs -f"
echo
echo "Open http://localhost:${GATEWAY_PORT:-8801}/auth-morm to register a passkey."
