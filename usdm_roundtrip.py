#!/usr/bin/env python3
"""USDm bidirectional bridge round-trip test (Base <-> MORM L1).

Exercises BOTH new relayer paths end-to-end with a tiny real amount:
  1. Base : deposit USDC->USDm (only if short), approve + lock into USDmLockBridge
  2. relayer FORWARD : Locked  -> L1 BRIDGE_MINT credits account_tokens[USDm]
  3. L1   : BRIDGE_BURN(token=USDm) from a FRESH test account (auto-generated)
  4. relayer REVERSE : unlock() releases escrowed USDm back to a Base recipient

The only secret input is BASE_KEY (a Base EOA that holds USDC). A fresh L1
keypair is generated for the mirror account, so no existing L1 seed is needed
and the test cannot touch any production L1 balance.

Env (BASE_KEY required; the rest are read from relayer.env when sourced):
  BASE_KEY          Base EOA private key (holds USDC / pays gas)
  AMOUNT_USDC       human amount, default "1"  (1 USDC = 1_000_000 base units)
  EVM_RECIPIENT     where unlock returns USDm  (default: BASE_KEY's own address)
  EVM_RPC MORM_RPC CHAIN_ID USDM_ADDR USDM_BRIDGE_ADDR   (from relayer.env)
  POLL_TIMEOUT      seconds to wait for each relayer leg (default 240)

Run (on ts-mini):
  cd /Users/user/Desktop/MORM
  set -a; source ~/.morm-relayer-main/relayer.env; set +a
  export BASE_KEY=0x....                      # your Base EOA holding USDC
  /usr/bin/python3 usdm_roundtrip.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from web3 import Web3
from eth_account import Account

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "morm-l1"))
from morm_l1 import crypto            # noqa: E402
from morm_l1.tx import Transaction    # noqa: E402

EVM_RPC          = os.environ["EVM_RPC"]
MORM_RPC         = os.environ["MORM_RPC"]
CHAIN_ID         = int(os.environ.get("CHAIN_ID", "8453"))
USDM_ADDR        = Web3.to_checksum_address(os.environ["USDM_ADDR"])
USDM_BRIDGE_ADDR = Web3.to_checksum_address(os.environ["USDM_BRIDGE_ADDR"])
AMOUNT           = int(round(float(os.environ.get("AMOUNT_USDC", "1")) * 1_000_000))
POLL_TIMEOUT     = float(os.environ.get("POLL_TIMEOUT", "240"))
USDM_TOKEN       = os.environ.get("USDM_TOKEN", "USDm")


def get_morm(p):
    return json.loads(urllib.request.urlopen(MORM_RPC + p, timeout=8).read())


def post_morm(p, b):
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        MORM_RPC + p, method="POST", data=json.dumps(b).encode(),
        headers={"Content-Type": "application/json"}), timeout=8).read())


def _abi(sol, name):
    return json.loads((ROOT / "morm-chain" / "out" / sol / f"{name}.json").read_text())["abi"]


ERC20_ABI = [
    {"name": "approve", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"type": "address"}, {"type": "uint256"}], "outputs": [{"type": "bool"}]},
    {"name": "allowance", "type": "function", "stateMutability": "view",
     "inputs": [{"type": "address"}, {"type": "address"}], "outputs": [{"type": "uint256"}]},
    {"name": "balanceOf", "type": "function", "stateMutability": "view",
     "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]},
]


def main():
    acct = Account.from_key(os.environ["BASE_KEY"])
    me = acct.address
    recipient = Web3.to_checksum_address(os.environ.get("EVM_RECIPIENT", me))
    w3 = Web3(Web3.HTTPProvider(EVM_RPC))
    if not w3.is_connected():
        raise SystemExit(f"EVM RPC unreachable: {EVM_RPC}")

    usdm = w3.eth.contract(address=USDM_ADDR, abi=_abi("USDm.sol", "USDm"))
    bridge = w3.eth.contract(address=USDM_BRIDGE_ADDR, abi=_abi("USDmLockBridge.sol", "USDmLockBridge"))
    usdc_addr = Web3.to_checksum_address(usdm.functions.usdc().call())
    usdc = w3.eth.contract(address=usdc_addr, abi=ERC20_ABI)

    # fresh L1 mirror account (its m0r address is the lock's mormAddress + the burner)
    seed = crypto.random_seed() if hasattr(crypto, "random_seed") else os.urandom(32)
    pub = crypto.pubkey_from_seed(seed)
    m0r = crypto.address(pub)
    mbytes20 = crypto.address_to_bytes20(m0r)

    amt_h = AMOUNT / 1_000_000
    print(f"=== USDm round-trip test ===")
    print(f"Base EOA      : {me}")
    print(f"unlock -> to  : {recipient}")
    print(f"amount        : {amt_h} USDC  ({AMOUNT} base units)")
    print(f"L1 test acct  : {m0r}")
    print(f"USDC          : {usdc_addr}")
    print(f"USDm          : {USDM_ADDR}")
    print(f"USDmLockBridge: {USDM_BRIDGE_ADDR}")
    esc0 = bridge.functions.escrowed().call()
    rcpt0 = usdm.functions.balanceOf(recipient).call()
    print(f"escrow(before): {esc0/1e6} USDm   recipient USDm(before): {rcpt0/1e6}")

    # local nonce counter — the public RPC lags right after a receipt and can
    # hand back a stale count ("nonce too low"), so track it ourselves.
    nstate = {"n": w3.eth.get_transaction_count(me, "pending")}

    def send(fn, gas=250_000):
        tx = fn.build_transaction({
            "from": me,
            "nonce": nstate["n"],
            "gas": gas,
            "gasPrice": w3.eth.gas_price * 2,
            "chainId": CHAIN_ID,
        })
        signed = acct.sign_transaction(tx)
        h = w3.eth.send_raw_transaction(signed.raw_transaction)
        r = w3.eth.wait_for_transaction_receipt(h, timeout=120)
        if r.status != 1:
            raise SystemExit(f"tx reverted: {h.hex()}")
        nstate["n"] += 1
        print(f"   ok {h.hex()[:18]}…")
        return r

    # ── 1. ensure enough USDm on Base (mint from USDC if short) ──
    have = usdm.functions.balanceOf(me).call()
    if have < AMOUNT:
        need = AMOUNT - have
        ubal = usdc.functions.balanceOf(me).call()
        if ubal < need:
            raise SystemExit(f"insufficient USDC: have {ubal/1e6}, need {need/1e6}")
        print(f"[1] deposit {need/1e6} USDC -> USDm")
        if usdc.functions.allowance(me, USDM_ADDR).call() < need:
            print("   approve USDC -> USDm"); send(usdc.functions.approve(USDM_ADDR, need))
        send(usdm.functions.deposit(need))
    else:
        print(f"[1] already hold {have/1e6} USDm — skip deposit")

    # ── 2. approve + lock into the escrow bridge ──
    print(f"[2] lock {amt_h} USDm -> bridge (mormAddress={m0r})")
    if usdm.functions.allowance(me, USDM_BRIDGE_ADDR).call() < AMOUNT:
        print("   approve USDm -> bridge"); send(usdm.functions.approve(USDM_BRIDGE_ADDR, AMOUNT))
    send(bridge.functions.lock(AMOUNT, mbytes20))

    # ── 3. wait for relayer FORWARD credit on L1 ──
    print(f"[3] waiting for L1 credit account_tokens[{USDM_TOKEN}] ...")
    t0 = time.time(); credited = 0
    while time.time() - t0 < POLL_TIMEOUT:
        tokens = get_morm(f"/account/{m0r}").get("tokens", {})
        credited = int(tokens.get(USDM_TOKEN, 0))
        if credited >= AMOUNT:
            break
        time.sleep(4)
    if credited < AMOUNT:
        raise SystemExit(f"FORWARD FAILED: L1 credit {credited} < {AMOUNT} after {POLL_TIMEOUT}s")
    print(f"   FORWARD OK: L1 {m0r} now holds {credited/1e6} {USDM_TOKEN}")

    # ── 4. L1 BRIDGE_BURN(token=USDm) from the fresh account ──
    print(f"[4] L1 BRIDGE_BURN {amt_h} {USDM_TOKEN} -> evm_recipient {recipient}")
    nonce = get_morm(f"/account/{m0r}")["nonce"]
    burn = Transaction.bridge_burn(
        pub, nonce, amount=AMOUNT, evm_recipient=recipient,
        token=USDM_TOKEN, token_address=USDM_ADDR).sign(seed)
    res = post_morm("/tx", burn.to_dict())
    burn_hash = burn.hash().hex()
    print(f"   L1 burn posted: {res} (burn_tx_hash={burn_hash[:18]}…)")

    # ── 5. wait for relayer REVERSE unlock on Base ──
    print(f"[5] waiting for Base unlock -> {recipient} ...")
    t0 = time.time(); rcpt1 = rcpt0
    while time.time() - t0 < POLL_TIMEOUT:
        rcpt1 = usdm.functions.balanceOf(recipient).call()
        if rcpt1 >= rcpt0 + AMOUNT:
            break
        time.sleep(4)
    esc1 = bridge.functions.escrowed().call()
    if rcpt1 < rcpt0 + AMOUNT:
        raise SystemExit(f"REVERSE FAILED: recipient USDm {rcpt1/1e6} (want +{amt_h}) after {POLL_TIMEOUT}s")
    print(f"   REVERSE OK: recipient USDm {rcpt0/1e6} -> {rcpt1/1e6}  (+{amt_h})")
    print(f"escrow(after) : {esc1/1e6} USDm  (was {esc0/1e6})")
    print("=== ROUND-TRIP OK: forward credit + reverse unlock both verified ===")


if __name__ == "__main__":
    main()
