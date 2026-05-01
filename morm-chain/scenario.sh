#!/usr/bin/env bash
# End-to-end MORMEscrow scenario against a running anvil.
# Registers content → creates order → submits proofs → finalize.
# Verifies 1% fee + 99% release math live on-chain.

set -euo pipefail

RPC=http://127.0.0.1:8545
ESC=0x5FbDB2315678afecb367f032d93F642f64180aa3

# anvil default keys
DEPLOYER=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
TREASURY_KEY=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
CREATOR_KEY=0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a
BUYER_KEY=0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6
SELLER_KEY=0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a

TREASURY=0x70997970C51812dc3A010C7d01b50e0d17dc79C8
CREATOR=0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC
BUYER=0x90F79bf6EB2c4f870365E785982E1f101E93b906
SELLER=0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65

CID=$(cast keccak "morm-content-1")
RH=$(cast keccak "manifest-root-1")
GID=$(cast keccak "gen-id-001")
ORD=$(cast keccak "order-001")
PACK=$(cast keccak "packing-evidence-blockhash")
OPEN=$(cast keccak "opening-evidence-blockhash")

balance() { cast balance "$1" --rpc-url $RPC; }
fmt_eth() { cast to-unit "$1" ether; }

echo "── ① register content (creator) ──"
cast send $ESC "registerContent(bytes32,bytes32,bytes32)" $CID $RH $GID \
  --private-key $CREATOR_KEY --rpc-url $RPC > /dev/null
cast call $ESC "contents(bytes32)(bytes32,bytes32,address,uint64)" $CID --rpc-url $RPC

echo
echo "── ② createOrder 1 ETH (buyer) ──"
T_BEFORE=$(balance $TREASURY)
S_BEFORE=$(balance $SELLER)
ESC_BEFORE=$(balance $ESC)
cast send $ESC "createOrder(bytes32,bytes32,address)" $ORD $CID $SELLER \
  --value 1ether --private-key $BUYER_KEY --rpc-url $RPC > /dev/null

T_AFTER_CREATE=$(balance $TREASURY)
ESC_AFTER_CREATE=$(balance $ESC)
echo "  treasury Δ: $(fmt_eth $((T_AFTER_CREATE - T_BEFORE))) ETH (expect 0.01)"
echo "  escrow held: $(fmt_eth $((ESC_AFTER_CREATE - ESC_BEFORE))) ETH (expect 0.99)"

echo
echo "── ③ submit packing proof (seller) ──"
cast send $ESC "submitPackingProof(bytes32,bytes32)" $ORD $PACK \
  --private-key $SELLER_KEY --rpc-url $RPC > /dev/null

echo "── ④ submit opening proof (buyer) ──"
cast send $ESC "submitOpeningProof(bytes32,bytes32)" $ORD $OPEN \
  --private-key $BUYER_KEY --rpc-url $RPC > /dev/null

echo
echo "── ⑤ finalize valid=true (treasury / validator) ──"
cast send $ESC "finalize(bytes32,bool)" $ORD true \
  --private-key $TREASURY_KEY --rpc-url $RPC > /dev/null
S_AFTER=$(balance $SELLER)
ESC_AFTER=$(balance $ESC)
echo "  seller   Δ: $(fmt_eth $((S_AFTER - S_BEFORE))) ETH (expect 0.99)"
echo "  escrow held now: $(fmt_eth $ESC_AFTER) ETH (expect 0)"

echo
echo "── ⑥ order status ──"
cast call $ESC "orders(bytes32)(bytes32,address,address,uint256,uint256,bytes32,bytes32,uint8,uint64)" $ORD --rpc-url $RPC
echo "  (status field: 4 = Finalized)"
