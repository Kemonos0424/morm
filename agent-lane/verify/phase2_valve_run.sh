#!/bin/bash
# Phase 2-③ cash-out valve verification. Ephemeral L1 (8905) + isolated Next dev
# (3012) with BRIDGE_VALVE=on and price/reserve OVERRIDES (no Base RPC needed).
# NEVER touches prod. 8900 untouched.
set -u
L1DIR=/Users/akihisayachida/Desktop/MORM/morm-l1
DASH=/Users/akihisayachida/Desktop/MORM/morm-dashboard
LANE=/Users/akihisayachida/Desktop/MORM/agent-lane/verify
L1PORT=8905
DEVPORT=3012
SCRATCH=/private/tmp/claude-501/-Users-akihisayachida-Desktop/20de3e75-c5ab-4d0b-9178-d1d85d146f0f/scratchpad

cleanup() {
  for p in "$L1PORT" "$DEVPORT"; do pid=$(lsof -ti tcp:"$p" 2>/dev/null); [ -n "$pid" ] && kill -9 $pid 2>/dev/null; done
  sleep 1; rm -rf "${DATADIR:-/nonexistent}" "${TESTDB:-/nonexistent}" 2>/dev/null
}
trap cleanup EXIT

KG=$(cd "$L1DIR" && PYTHONPATH="$L1DIR" python3 -m morm_l1.cli keygen)
SEED=$(echo "$KG" | python3 -c "import sys,json;print(json.load(sys.stdin)['seed_hex'])")
TADDR=$(echo "$KG" | python3 -c "import sys,json;print(json.load(sys.stdin)['address'])")
echo "[setup] ephemeral treasury=$TADDR"

DATADIR=$(mktemp -d "$SCRATCH/morm-p2v-XXXXXX")
TESTDB="$SCRATCH/p2v-dash-$$.sqlite"; rm -f "$TESTDB"
( cd "$L1DIR" && MORM_PRODUCER_SEED="$SEED" PYTHONPATH="$L1DIR" \
  python3 -m morm_l1.cli node --data-dir "$DATADIR" --treasury "$TADDR" \
  --host 127.0.0.1 --port "$L1PORT" --no-seed-discovery --genesis-lockdown-height 0 \
  > "$SCRATCH/p2v-l1.log" 2>&1 ) &
for i in $(seq 1 40); do curl -sf "http://127.0.0.1:$L1PORT/info" >/dev/null 2>&1 && { echo "[setup] L1 up"; break; }; sleep 0.4; done

echo "[setup] next dev :$DEVPORT (valve ON, overrides: usdc=120 -> sys cap 0.5%=\$0.60/day, price=\$0.0136, cooldown=3s)"
( cd "$DASH" && \
  MORM_L1_RPC_URL="http://127.0.0.1:$L1PORT" \
  MORM_TREASURY_SEED="$SEED" MORM_TREASURY_ADDRESS="$TADDR" \
  MORM_BASE_UNITS_PER_MORM=1000000 \
  MORM_FAUCET_AMOUNT=200 \
  BRIDGE_VALVE=on \
  BRIDGE_SYSTEM_DAILY_FRAC=0.005 \
  BRIDGE_ACCT_DAILY_USD=100 \
  BRIDGE_COOLDOWN_SEC=3 \
  MORM_PRICE_OVERRIDE_USD=0.0136 \
  MORM_RESERVE_USDC_OVERRIDE=120 \
  LOCAL_SQLITE_URL="file:$TESTDB" \
  TURSO_DATABASE_URL="" TURSO_AUTH_TOKEN="" \
  npx next dev -p "$DEVPORT" > "$SCRATCH/p2v-dev.log" 2>&1 ) &
UP=0
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$DEVPORT/api/lane/skill" 2>/dev/null)
  [ "$code" = "200" ] && { echo "[setup] dev up"; UP=1; break; }; sleep 1
done
[ "$UP" != "1" ] && { echo "[fatal] dev not up"; tail -30 "$SCRATCH/p2v-dev.log"; exit 1; }

BASE="http://127.0.0.1:$DEVPORT" EXPECT_BASE=1000000 \
  node "$LANE/phase2_valve_client.mjs" 2>&1 | tee "$SCRATCH/p2v-client.log"
RC=${PIPESTATUS[0]}
[ "$RC" != "0" ] && { echo "---- dev log ----"; tail -30 "$SCRATCH/p2v-dev.log"; }
exit $RC
