#!/bin/bash
# Phase 2-⑤ node-emission verification. Ephemeral L1 (8907) + isolated Next dev
# (3013) with an isolated sqlite seeded with 3 nodes (scores 10/30/60). Proves
# proportional NODE payout within the node budget + idempotency + nonce-safety
# (serialized transferMorm). NEVER touches prod. 8900 untouched.
set -u
L1DIR=/Users/akihisayachida/Desktop/MORM/morm-l1
DASH=/Users/akihisayachida/Desktop/MORM/morm-dashboard
LANE=/Users/akihisayachida/Desktop/MORM/agent-lane/verify
L1PORT=8907
DEVPORT=3013
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

DATADIR=$(mktemp -d "$SCRATCH/morm-p2n-XXXXXX")
TESTDB="$SCRATCH/p2n-dash-$$.sqlite"; rm -f "$TESTDB"

# seed nodes table (minimal) with 3 nodes scored 10/30/60 and real m0r wallets
PYTHONPATH="$L1DIR" python3 - "$TESTDB" <<'PY'
import sys, sqlite3
sys.path.insert(0, "/Users/akihisayachida/Desktop/MORM/morm-l1")
from morm_l1 import crypto
db = sys.argv[1]
c = sqlite3.connect(db)
c.execute("CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, wallet_address TEXT, total_score INTEGER)")
for nid, score in [("nodeA", 10), ("nodeB", 30), ("nodeC", 60)]:
    _, pub = crypto.keygen()
    c.execute("INSERT INTO nodes(id,wallet_address,total_score) VALUES(?,?,?)", (nid, crypto.address(pub), score))
c.commit()
for r in c.execute("SELECT id,wallet_address,total_score FROM nodes"):
    print("[seed]", r[0], r[1], r[2])
c.close()
PY

( cd "$L1DIR" && MORM_PRODUCER_SEED="$SEED" PYTHONPATH="$L1DIR" \
  python3 -m morm_l1.cli node --data-dir "$DATADIR" --treasury "$TADDR" \
  --host 127.0.0.1 --port "$L1PORT" --no-seed-discovery --genesis-lockdown-height 0 \
  > "$SCRATCH/p2n-l1.log" 2>&1 ) &
for i in $(seq 1 40); do curl -sf "http://127.0.0.1:$L1PORT/info" >/dev/null 2>&1 && { echo "[setup] L1 up"; break; }; sleep 0.4; done

echo "[setup] next dev :$DEVPORT (base=1e6, B=1000, SPLIT_NODE=0.30 -> node budget 300 MORM)"
( cd "$DASH" && \
  MORM_L1_RPC_URL="http://127.0.0.1:$L1PORT" \
  MORM_TREASURY_SEED="$SEED" MORM_TREASURY_ADDRESS="$TADDR" \
  MORM_BASE_UNITS_PER_MORM=1000000 \
  B_EPOCH_MORM=1000 SPLIT_NODE=0.30 EPOCH_ACCT_CAP_FRAC=1.0 \
  ADMIN_PASSWORD=testpass \
  LOCAL_SQLITE_URL="file:$TESTDB" \
  TURSO_DATABASE_URL="" TURSO_AUTH_TOKEN="" \
  npx next dev -p "$DEVPORT" > "$SCRATCH/p2n-dev.log" 2>&1 ) &
UP=0
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$DEVPORT/api/lane/skill" 2>/dev/null)
  [ "$code" = "200" ] && { echo "[setup] dev up"; UP=1; break; }; sleep 1
done
[ "$UP" != "1" ] && { echo "[fatal] dev not up"; tail -30 "$SCRATCH/p2n-dev.log"; exit 1; }

BASE="http://127.0.0.1:$DEVPORT" L1="http://127.0.0.1:$L1PORT" ADMIN=testpass \
  node "$LANE/phase2_node_client.mjs" 2>&1 | tee "$SCRATCH/p2n-client.log"
RC=${PIPESTATUS[0]}
[ "$RC" != "0" ] && { echo "---- dev log ----"; tail -30 "$SCRATCH/p2n-dev.log"; }
exit $RC
