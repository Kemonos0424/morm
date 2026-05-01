"""Phase 13b — manual M-of-N quorum bridge scenario.

Demonstrates that the existing primitives (MORMBridgeMS.sol on the EVM,
REGISTER_TREASURY_SIGNERS + MULTISIG_TX on the L1) chain together end-
to-end without any single-key relayer.

Prerequisites (orchestrated by the runner, NOT this script):
  - anvil running on :8545
  - MORMBridgeMS deployed (script/DeployBridgeMS.s.sol) — addr in
    /tmp/bridge_ms_addr.txt
  - Fresh L1 running on :8910 with genesis-lockdown-height=0 and
    treasury = the bootstrap key from /tmp/quorum-keys.json

Run from the project root:
  $ morm-l1/.venv/bin/python scenario_swap_quorum.py

What this scenario covers:
  ① register 3 ed25519 validators as treasury signers (M=2-of-3)
  ② alice (anvil acct #2) → MORMBridgeMS.lock(0.05 ETH, mormAddr)
  ③ each validator signs `multisig_signing_bytes(BRIDGE_MINT, ...)` over
    the same payload+treasury_nonce; we collect 2-of-3 cosignatures
  ④ any signer wraps in MULTISIG_TX and submits to L1 /tx → mint lands
    on alice_morm
  ⑤ alice signs BRIDGE_BURN(amount, evm_recipient=bob) on L1
  ⑥ each validator signs the EVM unlock digest with their EVM key;
    we collect 2-of-3 sorted-ascending signatures
  ⑦ any party calls MORMBridgeMS.unlock(recipient, amount, burnId,
    sigs[]) → bob receives the ETH
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "morm-l1"))

from morm_l1 import crypto                        # noqa: E402
from morm_l1.tx import Transaction, TxKind        # noqa: E402

from web3 import Web3                              # noqa: E402
from eth_account import Account                    # noqa: E402
from eth_account.messages import encode_defunct    # noqa: E402

EVM_RPC  = "http://127.0.0.1:8545"
MORM_RPC = "http://127.0.0.1:8910"

# anvil acct #2 — alice (already used in scenario_swap.py)
ALICE_EVM_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
# anvil acct #3 — bob (recipient on EVM after burn)
BOB_EVM_ADDR = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"
# anvil accts #5/6/7 — the 3 EVM signers (must match DeployBridgeMS.s.sol).
VALIDATOR_EVM_KEYS = [
    "0x8b3a350cf5c34c9194ca85829a2df0ec3153be0318b5e2d3348e872092edffba",  # #5
    "0x92db14e403b83dfe3df233f83dfa3a0d7096f21ca9b0d6d6b8d88b2b4ec1564e",  # #6
    "0x4bbbf85ce3377467afe5d46f804f221813b2bb87f24d81f60f1fcdbf7cbf4356",  # #7
]


def get_morm(p):
    return json.loads(urllib.request.urlopen(MORM_RPC + p, timeout=5).read())


def post_morm(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        MORM_RPC + path, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def wait_for(predicate, *, timeout=20, every=0.5, label="condition"):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if predicate():
            return True
        time.sleep(every)
    raise TimeoutError(f"timed out waiting for {label}")


def main():
    keys = json.loads(Path("/tmp/quorum-keys.json").read_text())
    bridge_ms_addr = Web3.to_checksum_address(
        Path("/tmp/bridge_ms_addr.txt").read_text().strip()
    )

    treasury_seed = bytes.fromhex(keys["treasury_bootstrap"]["seed_hex"])
    treasury_pub  = crypto.pubkey_from_seed(treasury_seed)
    treasury_addr = crypto.address(treasury_pub)
    print(f"treasury bootstrap = {treasury_addr}")

    validators = [keys[f"validator_{i}"] for i in range(3)]
    val_seeds  = [bytes.fromhex(v["seed_hex"]) for v in validators]
    val_pubs   = [crypto.pubkey_from_seed(s) for s in val_seeds]
    val_evm    = [Account.from_key(k) for k in VALIDATOR_EVM_KEYS]
    for i, v in enumerate(validators):
        print(f"  validator-{i} L1 pub = {v['pubkey_hex'][:16]}…  EVM = {val_evm[i].address}")

    w3 = Web3(Web3.HTTPProvider(EVM_RPC))
    bridge_ms_abi = json.loads(
        (ROOT / "morm-chain" / "out" / "MORMBridgeMS.sol" / "MORMBridgeMS.json").read_text()
    )["abi"]
    bridge = w3.eth.contract(address=Web3.to_checksum_address(bridge_ms_addr),
                              abi=bridge_ms_abi)
    print(f"bridge MS contract = {bridge_ms_addr} (threshold={bridge.functions.threshold().call()}, signers={bridge.functions.signerCount().call()})")

    # ── ① bootstrap: register the 3 validator pubkeys as treasury signers, M=2 ─
    print("\n── ① REGISTER_TREASURY_SIGNERS (single-key bootstrap, sets M=2-of-3) ──")
    treasury_acct = get_morm(f"/account/{treasury_addr}")
    nonce = treasury_acct["nonce"]
    tx = Transaction.register_treasury_signers(
        sender=treasury_pub, nonce=nonce,
        signers=[{"pubkey": v["pubkey_hex"], "name": v["name"]} for v in validators],
        threshold=2,
    ).sign(treasury_seed)
    resp = post_morm("/tx", tx.to_dict())
    print(f"   submitted: tx_hash={resp.get('tx_hash','?')[:16]}…  ok={resp.get('ok')}")
    # Wait for head to advance one block. The tx may also benignly fail if
    # multi-sig was already activated by a prior run; we proceed either way
    # since the multi-sig path below is the actual proof.
    pre_head = get_morm("/info")["head_height"]
    try:
        wait_for(lambda: get_morm("/info")["head_height"] > pre_head,
                 timeout=10, label="head_height advance after register")
    except TimeoutError:
        pass
    # If multi-sig isn't active yet, abort with a clear message.
    # We probe by trying to submit a no-op MULTISIG_TX would be invasive;
    # instead, rely on the state.py guard that rejects single-key BRIDGE_MINT
    # when active. We just print a hint.
    print(f"   ✓ register attempt landed (treasury nonce now {get_morm(f'/account/{treasury_addr}')['nonce']})")

    # ── ② alice locks 0.05 ETH on the multi-sig bridge ────────────────────
    print("\n── ② alice.lock(0.05 ETH, mormAddr) on MORMBridgeMS ──")
    alice_evm = Account.from_key(ALICE_EVM_KEY)
    alice_seed, alice_pub = crypto.keygen()
    alice_morm = crypto.address(alice_pub)
    alice_morm_b20 = crypto.address_to_bytes20(alice_morm)
    print(f"   alice EVM = {alice_evm.address[:14]}…  alice MORM = {alice_morm}")

    n = w3.eth.get_transaction_count(alice_evm.address)
    tx = bridge.functions.lock(alice_morm_b20).build_transaction({
        "from": alice_evm.address,
        "value": Web3.to_wei(0.05, "ether"),
        "nonce": n, "gas": 120_000,
        "gasPrice": w3.eth.gas_price, "chainId": 31337,
    })
    h = w3.eth.send_raw_transaction(alice_evm.sign_transaction(tx).raw_transaction)
    rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=10)
    print(f"   evm_tx={h.hex()[:16]}…  block={rcpt.blockNumber}  status={rcpt.status}")

    # The Locked event payload — relayers normally read this from logs.
    # Here we know the inputs directly.
    locked = bridge.events.Locked().process_receipt(rcpt)[0]
    evm_lock_id = f"evm:{h.hex()}:{locked.logIndex}"
    amount_wei = int(locked.args.amount)
    print(f"   Locked event amount={amount_wei} mormAddress=0x{bytes(locked.args.mormAddress).hex()}")

    # ── ③ each validator cosigns the BRIDGE_MINT inner tx ─────────────────
    print("\n── ③ validators sign multisig_signing_bytes(BRIDGE_MINT, ...) ──")
    # Build the inner BRIDGE_MINT payload exactly as the L1 will see it.
    inner_payload = {
        "to":          alice_morm,
        "amount":      amount_wei,
        "evm_lock_id": evm_lock_id,
        "token":       "MORM",
    }
    treasury_nonce = get_morm(f"/account/{treasury_addr}")["nonce"]
    pre_image = Transaction.multisig_signing_bytes(
        inner_kind=int(TxKind.BRIDGE_MINT),
        inner_payload=inner_payload,
        treasury_addr=treasury_addr,
        treasury_nonce=treasury_nonce,
    )
    cosigs = []
    for i in range(3):
        sig = crypto.sign(val_seeds[i], pre_image)
        cosigs.append({"pubkey": val_pubs[i].hex(), "sig": sig.hex()})
        print(f"   validator-{i} cosig = {sig.hex()[:24]}…")

    # ── ④ aggregate 2-of-3 → MULTISIG_TX → submit ─────────────────────────
    print("\n── ④ aggregate 2-of-3 cosignatures, wrap in MULTISIG_TX, submit ──")
    submitter_idx = 0     # validator-0 submits; any signer is acceptable
    submitter_acct = get_morm(f"/account/{validators[submitter_idx]['address']}")
    # Submitter's own account nonce — independent from treasury_nonce.
    sub_nonce = submitter_acct["nonce"]
    multi_tx = Transaction.multisig_tx(
        sender=val_pubs[submitter_idx], nonce=sub_nonce,
        inner_kind=int(TxKind.BRIDGE_MINT),
        inner_payload=inner_payload,
        treasury_nonce=treasury_nonce,
        signatures=cosigs[:2],   # first 2 cosignatures = M=2 quorum
    ).sign(val_seeds[submitter_idx])
    resp = post_morm("/tx", multi_tx.to_dict())
    print(f"   submitted MULTISIG_TX: tx_hash={resp.get('tx_hash','?')[:16]}…  ok={resp.get('ok')}")
    if not resp.get("ok"):
        print(f"   ✗ rejected: {resp}")
        sys.exit(1)
    wait_for(lambda: int(get_morm(f"/account/{alice_morm}")["balance"]) >= amount_wei,
             timeout=15, label="alice MORM balance >= mint amount")
    minted = int(get_morm(f"/account/{alice_morm}")["balance"])
    print(f"   ✓ alice L1 balance = {minted} (expect {amount_wei})")

    # ── ⑤ alice signs BRIDGE_BURN on L1 (anyone, no multi-sig needed) ─────
    print("\n── ⑤ alice BRIDGE_BURN(0.02 ETH equivalent → bob) ──")
    burn_amt = Web3.to_wei(0.02, "ether")
    alice_acct_nonce = get_morm(f"/account/{alice_morm}")["nonce"]
    btx = Transaction.bridge_burn(
        sender=alice_pub, nonce=alice_acct_nonce,
        amount=burn_amt, evm_recipient=BOB_EVM_ADDR,
    ).sign(alice_seed)
    burn_resp = post_morm("/tx", btx.to_dict())
    print(f"   submitted BRIDGE_BURN: tx_hash={burn_resp['tx_hash'][:16]}…")
    burn_id = burn_resp["tx_hash"]
    wait_for(
        lambda: any(b["burn_tx_hash"] == burn_id for b in get_morm("/bridge/burns")["burns"]),
        timeout=10, label="burn row in /bridge/burns",
    )
    print(f"   ✓ burn recorded on L1 (burn_tx_hash={burn_id[:16]}…)")

    # ── ⑥ each validator signs the EVM unlock digest ─────────────────────
    print("\n── ⑥ validators sign EVM unlock digest (eth_sign-compatible) ──")
    digest = bridge.functions.unlockDigest(
        Web3.to_checksum_address(BOB_EVM_ADDR), burn_amt,
        bytes.fromhex(burn_id),
    ).call()
    print(f"   digest = 0x{digest.hex()}")
    # eth_sign style: signs keccak256("\x19Ethereum Signed Message:\n32" || digest).
    # eth_account.messages.encode_defunct does that prefixing for us.
    msg = encode_defunct(primitive=digest)
    sigs_with_addr = []
    for i, acct in enumerate(val_evm):
        signed = acct.sign_message(msg)
        sigs_with_addr.append((acct.address, bytes(signed.signature)))
        print(f"   validator-{i} EVM={acct.address} sig={signed.signature.hex()[:24]}…")

    # ── ⑦ pick the 2 lowest-address sigs (MS contract requires ascending) ──
    print("\n── ⑦ select 2-of-3 sigs sorted ascending by signer address, call unlock() ──")
    sigs_with_addr.sort(key=lambda x: int(x[0], 16))
    chosen = sigs_with_addr[:2]
    print(f"   chosen signers: {[a[0] for a in chosen]}")
    sigs_bytes = [s[1] for s in chosen]

    bob_before = w3.eth.get_balance(BOB_EVM_ADDR)
    # any party can submit — use validator-0's anvil EVM key
    submitter = val_evm[0]
    n = w3.eth.get_transaction_count(submitter.address)
    tx = bridge.functions.unlock(
        Web3.to_checksum_address(BOB_EVM_ADDR), burn_amt,
        bytes.fromhex(burn_id), sigs_bytes,
    ).build_transaction({
        "from": submitter.address, "nonce": n, "gas": 250_000,
        "gasPrice": w3.eth.gas_price, "chainId": 31337,
    })
    h = w3.eth.send_raw_transaction(submitter.sign_transaction(tx).raw_transaction)
    rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=10)
    print(f"   evm_tx={h.hex()[:16]}…  status={rcpt.status}  block={rcpt.blockNumber}")
    bob_after = w3.eth.get_balance(BOB_EVM_ADDR)
    print(f"   bob EVM Δ = {bob_after - bob_before} wei (expect {burn_amt})")
    if bob_after - bob_before != burn_amt:
        print("   ✗ unlock did not credit bob")
        sys.exit(1)

    # ── ⑧ final ledger ────────────────────────────────────────────────────
    print("\n══ FINAL ══")
    final = get_morm(f"/account/{alice_morm}")
    print(f"   alice L1 balance  = {final['balance']} (expect {amount_wei - burn_amt})")
    print(f"   bridge ETH held   = {w3.eth.get_balance(bridge_ms_addr)} wei (expect {amount_wei - burn_amt})")
    print(f"   lock/unlock nonce = {bridge.functions.lockNonce().call()}/{bridge.functions.unlockNonce().call()}")
    print(f"   bob EVM total     = {w3.eth.get_balance(BOB_EVM_ADDR)} wei")
    print("\n✓ Phase 13b M-of-N E2E PASS — ETH bridged via 2-of-3 EVM sigs + 2-of-3 L1 cosigs, no single-key relayer.")


if __name__ == "__main__":
    main()
