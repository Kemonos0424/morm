#!/usr/bin/env bash
# MORM end-to-end scenario: encoder → screening → chain → evidence → finalize.
# Runs both happy path (block-order valid) and fraud path (block-order broken).

set -euo pipefail
cd "$(dirname "$0")"

RPC=http://127.0.0.1:8545
PY=morm-core/.venv/bin/python

# anvil default keys
TREASURY_KEY=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
CREATOR_KEY=0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a
BUYER_KEY=0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6
SELLER_KEY=0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a
TREASURY=0x70997970C51812dc3A010C7d01b50e0d17dc79C8
CREATOR=0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC
BUYER=0x90F79bf6EB2c4f870365E785982E1f101E93b906
SELLER=0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65

ESC=0x5FbDB2315678afecb367f032d93F642f64180aa3   # deterministic anvil deploy addr
ORDER_HAPPY=$(cast keccak "morm-order-happy")
ORDER_FRAUD=$(cast keccak "morm-order-fraud")

balance() { cast balance "$1" --rpc-url $RPC; }
fmt()     { cast to-unit "$1" ether | head -c 8; }

# ----------------------------------------------------------------------
# bootstrap
# ----------------------------------------------------------------------
echo "═══ bootstrap: fresh anvil + deploy ═══"
pkill -f "anvil --port 8545" 2>/dev/null || true
sleep 0.3
anvil --port 8545 --silent &
ANVIL_PID=$!
trap "kill $ANVIL_PID 2>/dev/null || true" EXIT
sleep 1

(cd morm-chain && forge script script/Deploy.s.sol --rpc-url $RPC --broadcast 2>&1) | grep -E "(deployed at|treasury)" || true

# pull manifest from Phase 1 output to get a real root_hash and content_id
CID_RAW=$($PY -c "import json; m=json.load(open('morm-core/output/sample/manifest.json')); print(m['content_id'])")
RH_RAW=$($PY -c "
import json, hashlib
m=json.load(open('morm-core/output/sample/manifest.json'))
h=hashlib.sha256()
h.update(m['content_id'].encode())
for c in m['cells']:
    h.update(c['sha256'].encode()); h.update(c['vhash']['visual'].encode()); h.update(c['vhash']['audio'].encode())
print('0x'+h.hexdigest())
")
CID=0x${CID_RAW}
RH=${RH_RAW}
GID=$(cast keccak "manifest-gen-1")

echo
echo "═══ creator: registerContent (CID=${CID:0:18}…) ═══"
cast send $ESC "registerContent(bytes32,bytes32,bytes32)" $CID $RH $GID \
  --private-key $CREATOR_KEY --rpc-url $RPC > /dev/null
echo "  ✓ registered"

# raw seller stake (so we can prove slash works)
cast send $ESC "stakeNode()" --value 0.5ether \
  --private-key $SELLER_KEY --rpc-url $RPC > /dev/null
echo "  ✓ seller staked 0.5 ETH (slashable)"

# ----------------------------------------------------------------------
# generate two short evidence videos (different patterns)
# ----------------------------------------------------------------------
mkdir -p morm-core/samples
[ -f morm-core/samples/pack.mp4 ] || \
  ffmpeg -y -loglevel error -f lavfi -i "color=c=blue:size=480x270:rate=30,format=yuv420p" \
         -t 4 morm-core/samples/pack.mp4
[ -f morm-core/samples/open.mp4 ] || \
  ffmpeg -y -loglevel error -f lavfi -i "color=c=green:size=480x270:rate=30,format=yuv420p" \
         -t 4 morm-core/samples/open.mp4

# ======================================================================
# SCENARIO A — happy path
# ======================================================================
echo
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║ SCENARIO A — happy path  (packing block# < opening block#)         ║"
echo "╚════════════════════════════════════════════════════════════════════╝"

T_BEFORE=$(balance $TREASURY)
S_BEFORE=$(balance $SELLER)
B_BEFORE=$(balance $BUYER)

echo "── ① buyer createOrder 1 ETH ──"
cast send $ESC "createOrder(bytes32,bytes32,address)" $ORDER_HAPPY $CID $SELLER \
  --value 1ether --private-key $BUYER_KEY --rpc-url $RPC > /dev/null

echo "── ② seller encodes packing evidence (binds to current block) ──"
PACK_HASH=$(cd morm-core && .venv/bin/python -m morm_core.cli evidence \
  samples/pack.mp4 --role packing --order-id $ORDER_HAPPY \
  --rpc-url $RPC --out output/evidence/happy 2>&1 | tail -1)
echo "  packing proof_hash = ${PACK_HASH:0:18}…"

cast send $ESC "submitPackingProof(bytes32,bytes32)" $ORDER_HAPPY $PACK_HASH \
  --private-key $SELLER_KEY --rpc-url $RPC > /dev/null

echo "── ③ buyer encodes opening evidence (later block) ──"
OPEN_HASH=$(cd morm-core && .venv/bin/python -m morm_core.cli evidence \
  samples/open.mp4 --role opening --order-id $ORDER_HAPPY \
  --rpc-url $RPC --out output/evidence/happy 2>&1 | tail -1)
echo "  opening proof_hash = ${OPEN_HASH:0:18}…"

cast send $ESC "submitOpeningProof(bytes32,bytes32)" $ORDER_HAPPY $OPEN_HASH \
  --private-key $BUYER_KEY --rpc-url $RPC > /dev/null

echo "── ④ validator inspection ──"
PACK_BLK=$($PY -c "import json; print(json.load(open('morm-core/output/evidence/happy/packing-pack/evidence.json'))['block_number'])")
OPEN_BLK=$($PY -c "import json; print(json.load(open('morm-core/output/evidence/happy/opening-open/evidence.json'))['block_number'])")
echo "  packing block #$PACK_BLK"
echo "  opening block #$OPEN_BLK"
if [ "$OPEN_BLK" -gt "$PACK_BLK" ]; then
  echo "  ✓ chronology valid → finalize(true)"
  VALID=true
else
  echo "  ✗ chronology broken → finalize(false)"
  VALID=false
fi

cast send $ESC "finalize(bytes32,bool)" $ORDER_HAPPY $VALID \
  --private-key $TREASURY_KEY --rpc-url $RPC > /dev/null

T_AFTER=$(balance $TREASURY)
S_AFTER=$(balance $SELLER)
echo "── ledger ──"
echo "  treasury Δ = $(fmt $((T_AFTER - T_BEFORE))) ETH  (expect +0.01)"
echo "  seller   Δ = $(fmt $((S_AFTER - S_BEFORE))) ETH  (expect +0.99 minus seller's tx gas)"
echo "  status     = $(cast call $ESC "orders(bytes32)(bytes32,address,address,uint256,uint256,bytes32,bytes32,uint8,uint64)" $ORDER_HAPPY --rpc-url $RPC | sed -n '8p') (4=Finalized)"

# ======================================================================
# SCENARIO B — fraud (open watermarked with packing's block hash → broken chronology)
# ======================================================================
echo
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║ SCENARIO B — fraud  (opening reused an OLD block hash)            ║"
echo "╚════════════════════════════════════════════════════════════════════╝"

# attacker (= seller) tries again with a different buyer
ATTACKER=$BUYER  # reuse buyer for simplicity

# First the seller would need to NOT be locked from scenario A. Since we
# finalized true in A, seller is still active. But to demonstrate fraud,
# we'll use a fresh seller account to avoid "node locked" interference.
SELLER2_KEY=0x8b3a350cf5c34c9194ca85829a2df0ec3153be0318b5e2d3348e872092edffba
SELLER2=0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc

cast send $ESC "stakeNode()" --value 0.3ether \
  --private-key $SELLER2_KEY --rpc-url $RPC > /dev/null

cast send $ESC "createOrder(bytes32,bytes32,address)" $ORDER_FRAUD $CID $SELLER2 \
  --value 1ether --private-key $BUYER_KEY --rpc-url $RPC > /dev/null

# capture an OLD block hash now (packing time)
OLD_BH=$(cast block latest --field hash --rpc-url $RPC)
OLD_NUM=$(cast block latest --field number --rpc-url $RPC)
echo "── packing recorded at block #$OLD_NUM (will be reused fraudulently in opening) ──"

PACK_HASH=$(cd morm-core && .venv/bin/python -m morm_core.cli evidence \
  samples/pack.mp4 --role packing --order-id $ORDER_FRAUD \
  --block-hash $OLD_BH --out output/evidence/fraud 2>&1 | tail -1)
cast send $ESC "submitPackingProof(bytes32,bytes32)" $ORDER_FRAUD $PACK_HASH \
  --private-key $SELLER2_KEY --rpc-url $RPC > /dev/null

# attacker submits an opening that REUSES the old packing block hash —
# i.e. claims to have opened the package before/at the moment they shipped.
echo "── attacker produces opening with the SAME (older) block hash ──"
OPEN_HASH=$(cd morm-core && .venv/bin/python -m morm_core.cli evidence \
  samples/open.mp4 --role opening --order-id $ORDER_FRAUD \
  --block-hash $OLD_BH --out output/evidence/fraud 2>&1 | tail -1)
cast send $ESC "submitOpeningProof(bytes32,bytes32)" $ORDER_FRAUD $OPEN_HASH \
  --private-key $BUYER_KEY --rpc-url $RPC > /dev/null

echo "── validator inspection ──"
PACK_BLK=$($PY -c "import json; print(json.load(open('morm-core/output/evidence/fraud/packing-pack/evidence.json'))['block_number'])")
OPEN_BLK=$($PY -c "import json; print(json.load(open('morm-core/output/evidence/fraud/opening-open/evidence.json'))['block_number'])")
echo "  packing block #$PACK_BLK"
echo "  opening block #$OPEN_BLK"
if [ "$OPEN_BLK" -gt "$PACK_BLK" ]; then
  echo "  ✓ chronology valid"
  VALID=true
else
  echo "  ✗ chronology broken (opening ≤ packing) → finalize(false), slash + lock"
  VALID=false
fi

B_BEFORE2=$(balance $BUYER)
S2_BEFORE=$(balance $SELLER2)
T_BEFORE2=$(balance $TREASURY)

cast send $ESC "finalize(bytes32,bool)" $ORDER_FRAUD $VALID \
  --private-key $TREASURY_KEY --rpc-url $RPC > /dev/null

B_AFTER2=$(balance $BUYER)
S2_LOCKED=$(cast call $ESC "nodeLocked(address)(bool)" $SELLER2 --rpc-url $RPC)
S2_STAKE=$(cast call $ESC "stakeOf(address)(uint256)" $SELLER2 --rpc-url $RPC)
T_AFTER2=$(balance $TREASURY)

echo "── ledger ──"
echo "  buyer    Δ = +$(fmt $((B_AFTER2 - B_BEFORE2))) ETH  (refund, expect +0.99)"
echo "  treasury Δ = +$(fmt $((T_AFTER2 - T_BEFORE2))) ETH  (slashed stake, expect +0.3)"
echo "  seller2 stake = $S2_STAKE  (expect 0)"
echo "  seller2 nodeLocked = $S2_LOCKED  (expect true)"

# Verify locked node can't re-enter
echo
echo "── verify locked node is permanently excluded ──"
set +e
ZERO=0x0000000000000000000000000000000000000000000000000000000000000000
cast send $ESC "registerContent(bytes32,bytes32,bytes32)" \
  $(cast keccak "evil-content") $ZERO $ZERO \
  --private-key $SELLER2_KEY --rpc-url $RPC > /tmp/morm_locked_attempt.log 2>&1
RC=$?
set -e
if [ $RC -ne 0 ]; then
  echo "  ✓ registerContent reverted (rc=$RC); locked node cannot re-enter"
  grep -E "revert|NodeIsLocked|0x" /tmp/morm_locked_attempt.log | head -2 | sed 's/^/      /'
else
  echo "  ✗ unexpected: locked node still able to register"
fi

echo
echo "═══ DONE ═══"
