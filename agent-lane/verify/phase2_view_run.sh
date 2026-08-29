#!/bin/bash
# Phase 2 view_by_other verification. Ephemeral L1 (8906) + play_server driven
# directly. Own treasury, temp DB. NEVER touches prod. 8900 untouched.
set -u
L1DIR=/Users/akihisayachida/Desktop/MORM/morm-l1
LANE=/Users/akihisayachida/Desktop/MORM/agent-lane/verify
L1PORT=8906
SCRATCH=/private/tmp/claude-501/-Users-akihisayachida-Desktop/20de3e75-c5ab-4d0b-9178-d1d85d146f0f/scratchpad

cleanup() {
  pid=$(lsof -ti tcp:"$L1PORT" 2>/dev/null); [ -n "$pid" ] && kill -9 $pid 2>/dev/null
  sleep 1; rm -rf "${DATADIR:-/nonexistent}" "${SEEDFILE:-/nonexistent}" "${PLAYDB:-/nonexistent}" 2>/dev/null
}
trap cleanup EXIT

KG=$(cd "$L1DIR" && PYTHONPATH="$L1DIR" python3 -m morm_l1.cli keygen)
SEED=$(echo "$KG" | python3 -c "import sys,json;print(json.load(sys.stdin)['seed_hex'])")
TADDR=$(echo "$KG" | python3 -c "import sys,json;print(json.load(sys.stdin)['address'])")
echo "[setup] ephemeral treasury=$TADDR"

DATADIR=$(mktemp -d "$SCRATCH/morm-p2w-XXXXXX")
SEEDFILE=$(mktemp "$SCRATCH/p2w-seed-XXXXXX"); printf '%s' "$SEED" > "$SEEDFILE"
PLAYDB="$SCRATCH/p2w-play-$$.db"; rm -f "$PLAYDB"

( cd "$L1DIR" && MORM_PRODUCER_SEED="$SEED" PYTHONPATH="$L1DIR" \
  python3 -m morm_l1.cli node --data-dir "$DATADIR" --treasury "$TADDR" \
  --host 127.0.0.1 --port "$L1PORT" --no-seed-discovery --genesis-lockdown-height 0 \
  > "$SCRATCH/p2w-l1.log" 2>&1 ) &
for i in $(seq 1 40); do curl -sf "http://127.0.0.1:$L1PORT/info" >/dev/null 2>&1 && { echo "[setup] L1 up"; break; }; sleep 0.4; done

CATALOG_DB="$PLAYDB" \
MORM_L1_RPC="http://127.0.0.1:$L1PORT" \
TREASURY_SEED_FILE="$SEEDFILE" \
EMISSION_MODE=proportional \
MORM_BASE_UNITS_PER_MORM=1000000 \
B_EPOCH_MORM=1000 \
EPOCH_ACCT_CAP_FRAC=1.0 \
VIEW_EARN=on PT_VIEW=1 \
PYTHONPATH="/Users/akihisayachida/Desktop/MORM/morm-play:$L1DIR" \
  python3 "$LANE/phase2_view_client.py"
RC=$?
[ "$RC" != "0" ] && { echo "---- l1 log ----"; tail -15 "$SCRATCH/p2w-l1.log"; }
exit $RC
