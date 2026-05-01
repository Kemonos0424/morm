"""ERC-20 (USDC) ↔ MORM L1 swap scenario.

Prereqs: anvil + MORMBridgeERC20 + MockUSDC deployed, MORM L1 + relayer
running with --erc20-bridge --usdc-addr.

  ① Deployer (alice) approves bridge for 100 USDC, calls lockToken
  ② Relayer mints 100 USDC.morm to alice's L1 address
  ③ Alice burns 40 USDC.morm targeting bob's EVM address
  ④ Relayer calls unlockToken → bob receives 40 USDC on EVM
"""
from __future__ import annotations
import json, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "morm-l1"))
from morm_l1 import crypto
from morm_l1.tx import Transaction
from web3 import Web3
from eth_account import Account


EVM_RPC = "http://127.0.0.1:8545"
MORM_RPC = "http://127.0.0.1:8900"
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
BOB_EVM = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"


def get_morm(p): return json.loads(urllib.request.urlopen(MORM_RPC + p).read())


def main(usdc_addr, bridge_addr):
    w3 = Web3(Web3.HTTPProvider(EVM_RPC))
    out = ROOT / "morm-chain" / "out"
    usdc_abi = json.loads((out / "MockUSDC.sol" / "MockUSDC.json").read_text())["abi"]
    bridge_abi = json.loads((out / "MORMBridgeERC20.sol" / "MORMBridgeERC20.json").read_text())["abi"]
    usdc = w3.eth.contract(address=Web3.to_checksum_address(usdc_addr), abi=usdc_abi)
    bridge = w3.eth.contract(address=Web3.to_checksum_address(bridge_addr), abi=bridge_abi)

    alice_evm = Account.from_key(DEPLOYER_KEY)
    alice_seed, alice_pub = crypto.keygen()
    # Phase 18: m0r-prefixed base32 address; use the dedicated helper to
    # produce bytes20 for the EVM lockToken call (raw `bytes.fromhex` would
    # choke on the 'm' prefix).
    alice_morm = crypto.address(alice_pub)
    alice_morm_b20 = crypto.address_to_bytes20(alice_morm)

    print(f"alice EVM   = {alice_evm.address}")
    print(f"alice MORM  = {alice_morm}")
    print(f"USDC addr   = {usdc_addr}")
    print(f"bridge      = {bridge_addr}")

    print(f"\n   alice USDC (EVM): {usdc.functions.balanceOf(alice_evm.address).call() / 1e6}")

    # ── ① approve + lockToken 100 USDC ────────────────────────────────────
    print("\n── ① alice approve(bridge, 100 USDC) + lockToken ──")
    n = w3.eth.get_transaction_count(alice_evm.address)
    tx1 = usdc.functions.approve(bridge.address, 100 * 1_000_000).build_transaction({
        "from": alice_evm.address, "nonce": n,
        "gas": 80_000, "gasPrice": w3.eth.gas_price, "chainId": 31337,
    })
    s1 = alice_evm.sign_transaction(tx1)
    h1 = w3.eth.send_raw_transaction(s1.raw_transaction)
    w3.eth.wait_for_transaction_receipt(h1, timeout=10)
    print(f"   approve tx={h1.hex()[:16]}…")

    tx2 = bridge.functions.lockToken(
        usdc.address, 100 * 1_000_000, alice_morm_b20
    ).build_transaction({
        "from": alice_evm.address, "nonce": n + 1,
        "gas": 200_000, "gasPrice": w3.eth.gas_price, "chainId": 31337,
    })
    s2 = alice_evm.sign_transaction(tx2)
    h2 = w3.eth.send_raw_transaction(s2.raw_transaction)
    rcpt = w3.eth.wait_for_transaction_receipt(h2, timeout=10)
    print(f"   lockToken tx={h2.hex()[:16]}… status={rcpt.status}")

    # ── ② wait for relayer mint ──────────────────────────────────────────
    print("\n── ② wait for relayer → BRIDGE_MINT (USDC) ──")
    expected = 100 * 1_000_000
    for _ in range(15):
        time.sleep(1)
        a = get_morm(f"/account/{alice_morm}")
        bal = a["tokens"].get("USDC", 0)
        if bal >= expected:
            print(f"   alice L1.USDC = {bal / 1e6} USDC ✓")
            break
    else:
        print(f"   ✗ timed out; alice L1 tokens = {a.get('tokens')}")
        return

    # ── ③ burn 40 USDC.morm → unlock to bob ─────────────────────────────
    print("\n── ③ alice BRIDGE_BURN 40 USDC → bob ──")
    burn_amt = 40 * 1_000_000
    nonce = get_morm(f"/account/{alice_morm}")["nonce"]
    tx = Transaction.bridge_burn(
        alice_pub, nonce,
        amount=burn_amt, evm_recipient=BOB_EVM,
        token="USDC", token_address=usdc.address,
    ).sign(alice_seed)
    body = json.dumps(tx.to_dict()).encode()
    resp = json.loads(urllib.request.urlopen(urllib.request.Request(
        MORM_RPC + "/tx", method="POST", data=body,
        headers={"Content-Type": "application/json"})).read())
    print(f"   l1_tx_hash={resp['tx_hash'][:16]}…")

    # ── ④ wait for relayer unlockToken ──────────────────────────────────
    print("\n── ④ wait for relayer → unlockToken ──")
    bob_before = usdc.functions.balanceOf(BOB_EVM).call()
    for _ in range(15):
        time.sleep(1)
        bob_after = usdc.functions.balanceOf(BOB_EVM).call()
        if bob_after - bob_before == burn_amt:
            print(f"   bob EVM.USDC Δ = {(bob_after-bob_before)/1e6} USDC ✓")
            break
    else:
        print(f"   ✗ timed out; bob USDC Δ = {(bob_after-bob_before)/1e6}")

    # ── ⑤ ledger ────────────────────────────────────────────────────────
    print("\n══ FINAL ══")
    a = get_morm(f"/account/{alice_morm}")
    print(f"   alice L1.USDC      = {a['tokens'].get('USDC',0) / 1e6} USDC (expect 60)")
    print(f"   bridge USDC held   = {usdc.functions.balanceOf(bridge.address).call() / 1e6} USDC (expect 60)")
    print(f"   bob USDC           = {usdc.functions.balanceOf(BOB_EVM).call() / 1e6} USDC")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
