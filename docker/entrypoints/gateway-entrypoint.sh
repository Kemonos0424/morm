#!/bin/sh
# MORM Gateway entrypoint (passkey + browser entry-points).
#
# Required env:
#   MORM_RPC                  — e.g. http://l1:8900
# Optional env:
#   GATEWAY_PORT              — default 8801
#   TREASURY_SEED             — 64-hex (or)
#   TREASURY_SEED_FILE        — path inside container (mode 0600 enforced by gateway)
#   ALLOWED_ORIGINS           — comma-separated browser origins (CSRF strict mode)
#   BRIDGE_ADDR / EVM_RPC / EVM_CHAIN_ID                           — Phase 28a
#   ERC20_BRIDGE_ADDR / USDC_ADDR                                  — Phase 28b
#   HLS_STORAGE_DIR           — default /data/hls
#   DEV_MODE                  — "1" to add --dev-mode (LOCAL ONLY)
#   CDN_BASE_URL              — opt-in CDN edge base URL (Phase 25Vc)
set -eu

GATEWAY_PORT="${GATEWAY_PORT:-8801}"
HLS_STORAGE_DIR="${HLS_STORAGE_DIR:-/data/hls}"
DB_PATH="${DB_PATH:-/data/passkeys.db}"
mkdir -p "$HLS_STORAGE_DIR" "$(dirname "$DB_PATH")"

if [ -z "${MORM_RPC:-}" ]; then
    echo "[gateway] FATAL: MORM_RPC env required (e.g. http://l1:8900)"
    exit 1
fi

# treasury seed: env > file > none (gateway will refuse register-content
# hook if neither is provided, but page serving still works).
TREAS_ARG=""
if [ -n "${TREASURY_SEED:-}" ]; then
    TREAS_ARG="--treasury-seed $TREASURY_SEED"
elif [ -n "${TREASURY_SEED_FILE:-}" ]; then
    TREAS_ARG="--treasury-key-file $TREASURY_SEED_FILE"
fi

ARGS="--port $GATEWAY_PORT --host 0.0.0.0 --morm-rpc $MORM_RPC \
      --hls-storage-dir $HLS_STORAGE_DIR --db $DB_PATH"

[ -n "$TREAS_ARG" ]                                && ARGS="$ARGS $TREAS_ARG"
[ "${DEV_MODE:-0}" = "1" ]                         && ARGS="$ARGS --dev-mode"
[ -n "${ALLOWED_ORIGINS:-}" ]                      && for o in $(echo "$ALLOWED_ORIGINS" | tr , ' '); do
    ARGS="$ARGS --allowed-origins $o"
done
[ -n "${CDN_BASE_URL:-}" ]                         && ARGS="$ARGS --cdn-base-url $CDN_BASE_URL"
[ -n "${BRIDGE_ADDR:-}" ]                          && ARGS="$ARGS --bridge-addr $BRIDGE_ADDR"
[ -n "${EVM_RPC:-}" ]                              && ARGS="$ARGS --evm-rpc $EVM_RPC"
[ -n "${EVM_CHAIN_ID:-}" ]                         && ARGS="$ARGS --evm-chain-id $EVM_CHAIN_ID"
[ -n "${ERC20_BRIDGE_ADDR:-}" ]                    && ARGS="$ARGS --erc20-bridge-addr $ERC20_BRIDGE_ADDR"
[ -n "${USDC_ADDR:-}" ]                            && ARGS="$ARGS --usdc-addr $USDC_ADDR"
[ -n "${TURN_URL:-}" ]                             && for u in $(echo "$TURN_URL" | tr , ' '); do
    ARGS="$ARGS --turn-url $u"
done
[ -n "${TURN_SECRET:-}" ]                          && ARGS="$ARGS --turn-secret $TURN_SECRET"

echo "[gateway] python morm-player/passkey_morm.py $ARGS"
exec python /app/morm-player/passkey_morm.py $ARGS
