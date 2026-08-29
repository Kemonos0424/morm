#!/bin/bash
# Phase 2 unit-system verification. Ephemeral L1 + isolated Next dev at base=1e6.
# NEVER touches prod (own treasury, local sqlite, ports 8903/3011). 8900 untouched.
set -u
L1DIR=/Users/akihisayachida/Desktop/MORM/morm-l1
DASH=/Users/akihisayachida/Desktop/MORM/morm-dashboard
LANE=/Users/akihisayachida/Desktop/MORM/agent-lane/verify
L1PORT=8903
DEVPORT=3011
SCRATCH=/private/tmp/claude-501/-Users-akihisayachida-Desktop/20de3e75-c5ab-4d0b-9178-d1d85d146f0f/scratchpad

cleanup() {
  for p in "$L1PORT" "$DEVPORT"; do
    pid=$(lsof -ti tcp:"$p" 2>/dev/null); [ -n "$pid" ] && kill -9 $pid 2>/dev/null
  done
  sleep 1; rm -rf "${DATADIR:-/nonexistent}" 2>/dev/null
}
trap cleanup EXIT

KG=$(cd "$L1DIR" && PYTHONPATH="$L1DIR" python3 -m morm_l1.cli keygen)
SEED=$(echo "$KG" | python3 -c "import sys,json;print(json.load(sys.stdin)['seed_hex'])")
TADDR=$(echo "$KG" | python3 -c "import sys,json;print(json.load(sys.stdin)['address'])")
echo "[setup] ephemeral treasury=$TADDR"

DATADIR=$(mktemp -d "$SCRATCH/morm-p2u-XXXXXX")
( cd "$L1DIR" && MORM_PRODUCER_SEED="$SEED" PYTHONPATH="$L1DIR" \
  python3 -m morm_l1.cli node --data-dir "$DATADIR" --treasury "$TADDR" \
  --host 127.0.0.1 --port "$L1PORT" --no-seed-discovery --genesis-lockdown-height 0 \
  > "$SCRATCH/p2u-l1.log" 2>&1 ) &
for i in $(seq 1 40); do curl -sf "http://127.0.0.1:$L1PORT/info" >/dev/null 2>&1 && { echo "[setup] L1 up"; break; }; sleep 0.4; done

echo "[setup] next dev :$DEVPORT  base=1e6 (µMORM), faucet=5 MORM, laneEarn=0.002 MORM"
( cd "$DASH" && \
  MORM_L1_RPC_URL="http://127.0.0.1:$L1PORT" \
  MORM_TREASURY_SEED="$SEED" MORM_TREASURY_ADDRESS="$TADDR" \
  MORM_BASE_UNITS_PER_MORM=1000000 \
  MORM_FAUCET_AMOUNT=5 MORM_LANE_EARN=0.002 \
  TURSO_DATABASE_URL="" TURSO_AUTH_TOKEN="" \
  npx next dev -p "$DEVPORT" > "$SCRATCH/p2u-dev.log" 2>&1 ) &
UP=0
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$DEVPORT/api/lane/skill" 2>/dev/null)
  [ "$code" = "200" ] && { echo "[setup] dev up"; UP=1; break; }; sleep 1
done
[ "$UP" != "1" ] && { echo "[fatal] dev not up"; tail -30 "$SCRATCH/p2u-dev.log"; exit 1; }

BASE="http://127.0.0.1:$DEVPORT" EXPECT_BASE=1000000 EXPECT_FAUCET=5 EXPECT_EARN=0.002 \
  node "$LANE/phase2_units_client.mjs" 2>&1 | tee "$SCRATCH/p2u-client.log"
RC=${PIPESTATUS[0]}
[ "$RC" != "0" ] && { echo "---- dev log ----"; tail -30 "$SCRATCH/p2u-dev.log"; }
exit $RC
