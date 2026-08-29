#!/bin/bash
# Phase 1 end-to-end verification. Boots an ephemeral L1 + an isolated Next dev
# server (its own treasury, local sqlite — NEVER prod Turso / prod treasury),
# then drives the /api/lane/* routes over real HTTP. Cleans up on exit.
set -u
L1DIR=/Users/akihisayachida/Desktop/MORM/morm-l1
DASH=/Users/akihisayachida/Desktop/MORM/morm-dashboard
LANE=/Users/akihisayachida/Desktop/MORM/agent-lane/verify
L1PORT=8902
DEVPORT=3010
SCRATCH=/private/tmp/claude-501/-Users-akihisayachida-Desktop/20de3e75-c5ab-4d0b-9178-d1d85d146f0f/scratchpad

cleanup() {
  # Kill by PORT (the real python/next-server child PIDs differ from the
  # backgrounded subshell PIDs). NEVER touch 8900 = the machine's real L1 node.
  for p in "$L1PORT" "$DEVPORT"; do
    pid=$(lsof -ti tcp:"$p" 2>/dev/null)
    [ -n "$pid" ] && kill -9 $pid 2>/dev/null
  done
  sleep 1
  rm -rf "${DATADIR:-/nonexistent}" 2>/dev/null
}
trap cleanup EXIT

# --- ephemeral treasury/producer identity ---
KG=$(cd "$L1DIR" && PYTHONPATH="$L1DIR" python3 -m morm_l1.cli keygen)
SEED=$(echo "$KG" | python3 -c "import sys,json;print(json.load(sys.stdin)['seed_hex'])")
TADDR=$(echo "$KG" | python3 -c "import sys,json;print(json.load(sys.stdin)['address'])")
echo "[setup] ephemeral treasury=$TADDR"

# --- start L1 node ---
DATADIR=$(mktemp -d "$SCRATCH/morm-p1-XXXXXX")
( cd "$L1DIR" && MORM_PRODUCER_SEED="$SEED" PYTHONPATH="$L1DIR" \
  python3 -m morm_l1.cli node --data-dir "$DATADIR" --treasury "$TADDR" \
  --host 127.0.0.1 --port "$L1PORT" --no-seed-discovery --genesis-lockdown-height 0 \
  > "$SCRATCH/p1-l1.log" 2>&1 ) &
L1_PID=$!
echo "[setup] L1 pid=$L1_PID, waiting for /info ..."
for i in $(seq 1 40); do
  curl -sf "http://127.0.0.1:$L1PORT/info" >/dev/null 2>&1 && { echo "[setup] L1 up"; break; }
  sleep 0.4
done

# --- start isolated Next dev server (override all secrets to the ephemeral chain) ---
echo "[setup] starting next dev on :$DEVPORT (isolated env, local sqlite) ..."
( cd "$DASH" && \
  MORM_L1_RPC_URL="http://127.0.0.1:$L1PORT" \
  MORM_TREASURY_SEED="$SEED" \
  MORM_TREASURY_ADDRESS="$TADDR" \
  MORM_BASE_UNITS_PER_MORM=1 \
  MORM_FAUCET_AMOUNT=5 \
  MORM_FAUCET_CLAIM=50 \
  MORM_LANE_EARN=1 \
  TURSO_DATABASE_URL="" TURSO_AUTH_TOKEN="" \
  npx next dev -p "$DEVPORT" > "$SCRATCH/p1-dev.log" 2>&1 ) &
DEV_PID=$!
echo "[setup] next dev pid=$DEV_PID, warming up route ..."
UP=0
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$DEVPORT/api/lane/skill" 2>/dev/null)
  if [ "$code" = "200" ]; then echo "[setup] dev up (skill 200)"; UP=1; break; fi
  sleep 1
done
if [ "$UP" != "1" ]; then echo "[fatal] dev server did not come up; tail log:"; tail -30 "$SCRATCH/p1-dev.log"; exit 1; fi

# --- run the HTTP client verification ---
echo "[run] driving /api/lane/* over HTTP ..."
BASE="http://127.0.0.1:$DEVPORT" node "$LANE/phase1_client.mjs"
RC=$?
echo "[run] client exit=$RC"
if [ "$RC" != "0" ]; then echo "---- dev log tail ----"; tail -30 "$SCRATCH/p1-dev.log"; echo "---- l1 log tail ----"; tail -15 "$SCRATCH/p1-l1.log"; fi
exit $RC
