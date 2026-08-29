"""End-to-end EVM ↔ MORM swap scenario.

Prereqs: anvil running, MORM L1 node running, MORMBridge deployed, relayer
running. Uses the deterministic anvil keys + the existing /tmp/k_*.json.

Flow:
  ① Alice (EVM) → MORMBridge.lock(0.5 ETH, mormAddr=alice_morm)
  ② Relayer observes Locked → BRIDGE_MINT alice_morm 5e17 µMORM
  ③ alice_morm has L1 balance 5e17
  ④ alice_morm BRIDGE_BURN 2e17 → evm_recipient=bob_evm
  ⑤ Relayer observes burn → MORMBridge.unlock(bob_evm, 2e17)
  ⑥ bob_evm receives 0.2 ETH, alice_morm has L1 balance 3e17
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "morm-l1"))
from morm_l1 import crypto
from morm_l1.tx import Transaction

from web3 import Web3
from eth_account import Account


EVM_RPC  = "http://127.0.0.1:8545"
MORM_RPC = "http://127.0.0.1:8900"

# Anvil default keys
ALICE_EVM_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"  # acct #2
BOB_EVM_ADDR  = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"                          # acct #3


def get_morm(p): return json.loads(urllib.request.urlopen(MORM_RPC + p).read())


def main(bridge_addr: str):
    w3 = Web3(Web3.HTTPProvider(EVM_RPC))
    artifact = json.loads((ROOT / "morm-chain" / "out" /
                           "MORMBridge.sol" / "MORMBridge.json").read_text())
    bridge = w3.eth.contract(address=Web3.to_checksum_address(bridge_addr),
                              abi=artifact["abi"])

    alice_evm = Account.from_key(ALICE_EVM_KEY)
    # alice's L1 identity: we generate one. Phase 18 — `crypto.address()`
    # returns the m0r-prefixed base32 form; convert to bytes20 for the
    # EVM `lock(bytes20)` call via the dedicated helper.
    alice_seed, alice_pub = crypto.keygen()
    alice_morm_hex = crypto.address(alice_pub)             # "m0r…" base32
    alice_morm_b20 = crypto.address_to_bytes20(alice_morm_hex)

    print(f"alice EVM       = {alice_evm.address}")
    print(f"alice MORM      = {alice_morm_hex}")
    print(f"bob   EVM       = {BOB_EVM_ADDR}")
    print(f"bridge contract = {bridge_addr}")

    # ── ① Alice locks 0.5 ETH on EVM ─────────────────────────────────────
    print("\n── ① alice.lock(0.5 ETH) on MORMBridge ──")
    nonce = w3.eth.get_transaction_count(alice_evm.address)
    tx = bridge.functions.lock(alice_morm_b20).build_transaction({
        "from": alice_evm.address, "value": Web3.to_wei(0.5, "ether"),
        "nonce": nonce, "gas": 120_000,
        "gasPrice": w3.eth.gas_price, "chainId": 31337,
    })
    signed = alice_evm.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=10)
    print(f"   evm_tx={h.hex()[:16]}…  status={rcpt.status}  block={rcpt.blockNumber}")

    # ── ② wait for relayer to mint on MORM L1 ───────────────────────────
    print("\n── ② wait for relayer → BRIDGE_MINT ──")
    expected = Web3.to_wei(0.5, "ether")
    for _ in range(15):
        time.sleep(1)
        bal = get_morm(f"/account/{alice_morm_hex}")["balance"]
        if bal >= expected:
            print(f"   alice L1 balance = {bal} (expected ≥ {expected})")
            break
    else:
        print(f"   ✗ timed out waiting; alice L1 balance = {bal}")
        return

    # ── ③ Alice burns half of her L1 balance, designating bob_evm ────────
    print("\n── ③ alice BRIDGE_BURN 0.2 ETH-equivalent → bob ──")
    burn_amt = Web3.to_wei(0.2, "ether")
    nonce = get_morm(f"/account/{alice_morm_hex}")["nonce"]
    tx = Transaction.bridge_burn(
        alice_pub, nonce,
        amount=burn_amt, evm_recipient=BOB_EVM_ADDR,
    ).sign(alice_seed)
    body = json.dumps(tx.to_dict()).encode()
    resp = json.loads(urllib.request.urlopen(urllib.request.Request(
        MORM_RPC + "/tx", method="POST", data=body,
        headers={"Content-Type": "application/json"})).read())
    print(f"   l1_tx_hash={resp['tx_hash'][:16]}…")

    # ── ④ wait for relayer to call unlock() on EVM ──────────────────────
    print("\n── ④ wait for relayer → MORMBridge.unlock() ──")
    bob_before = w3.eth.get_balance(BOB_EVM_ADDR)
    for _ in range(15):
        time.sleep(1)
        bob_after = w3.eth.get_balance(BOB_EVM_ADDR)
        if bob_after - bob_before == burn_amt:
            print(f"   bob EVM Δ = {bob_after - bob_before} wei (expect {burn_amt})")
            break
    else:
        print(f"   ✗ timed out; bob EVM Δ = {bob_after - bob_before}")
        return

    # ── ⑤ final ledger ──────────────────────────────────────────────────
    print("\n══ FINAL ══")
    print(f"   alice L1 balance = {get_morm(f'/account/{alice_morm_hex}')['balance']} "
          f"(expect {expected - burn_amt})")
    print(f"   bridge ETH held  = {w3.eth.get_balance(bridge_addr)} "
          f"(expect {expected - burn_amt})")
    print(f"   alice EVM        = {w3.eth.get_balance(alice_evm.address)} wei")
    print(f"   bob   EVM        = {w3.eth.get_balance(BOB_EVM_ADDR)} wei")


if __name__ == "__main__":
    addr = sys.argv[1] if len(sys.argv) > 1 else "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
    main(addr)
