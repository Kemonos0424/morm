"""Native-module parity test: every Phase 4 forge-test scenario, re-run on
MORM Chain L1 instead of Anvil/Solidity.

Mirrors test/MORMEscrow.t.sol:
  ① register_content
  ② revert_double_register
  ③ revert_generation_id_collision
  ④ order_fee_split_99_1
  ⑤ full_finalize_releases_to_seller
  ⑥ invalid_finalize_refunds_buyer_and_locks_seller
  ⑦ locked_node_cannot_create_orders
  ⑧ locked_node_cannot_register_content
  ⑨ revert_finalize_by_non_treasury
  ⑩ revert_pack_by_non_seller
  ⑪ revert_open_before_pack

Each case is colored PASS/FAIL based on whether the MORM L1 state matches
the Solidity contract's expected behavior.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from morm_l1 import crypto
from morm_l1.tx import Transaction


RPC = "http://127.0.0.1:8900"


def get(path):
    return json.loads(urllib.request.urlopen(RPC + path).read())


def post(path, body):
    req = urllib.request.Request(
        RPC + path, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())


def submit(seed_hex, factory):
    seed = bytes.fromhex(seed_hex)
    pub = crypto.pubkey_from_seed(seed)
    nonce = get(f"/account/{crypto.address(pub)}")["nonce"]
    tx = factory(pub, nonce).sign(seed)
    return post("/tx", tx.to_dict()), tx


def keygen_local():
    seed, pub = crypto.keygen()
    return seed.hex(), crypto.address(pub), pub


def settle(secs=1.5):
    time.sleep(secs)


def expect_state(addr, **fields) -> str:
    a = get(f"/account/{addr}")
    for k, v in fields.items():
        if a[k] != v:
            return f"FAIL: {addr[:10]}.{k}={a[k]} (expected {v})"
    return "PASS"


def assert_block_count_grew(before: int, label: str):
    after = max((b["height"] for b in get("/blocks/latest?n=20")["blocks"]), default=0)
    return "PASS" if after > before else f"FAIL: no block produced for {label}"


def assert_block_count_unchanged(before: int, label: str, settle_secs=1.5):
    settle(settle_secs)
    after = max((b["height"] for b in get("/blocks/latest?n=20")["blocks"]), default=0)
    return "PASS" if after == before else f"FAIL: unexpected block produced for {label}"


def head_height() -> int:
    bs = get("/blocks/latest?n=1")["blocks"]
    return bs[0]["height"] if bs else 0


def main():
    keys = json.loads(Path("/tmp/k_treas.json").read_text())
    treasury_seed = keys["seed_hex"]
    treasury_addr = keys["address"]

    creator_s, creator_a, _ = keygen_local()
    buyer_s,   buyer_a,   _ = keygen_local()
    seller_s,  seller_a,  _ = keygen_local()
    bad_s,     bad_a,     _ = keygen_local()

    # bootstrap balances
    print("── bootstrap: credit creator/buyer/seller/bad-actor ──")
    for addr, amt in [(creator_a, 100_000), (buyer_a, 1_000_000),
                       (seller_a, 100_000), (bad_a, 100_000)]:
        post("/credit", {"to": addr, "amount": amt})

    cid    = "0x" + hashlib.sha256(b"native-content-1").hexdigest()
    cid2   = "0x" + hashlib.sha256(b"native-content-2").hexdigest()
    rh     = "0x" + "ab" * 32
    gid    = "0x" + "cd" * 32
    pack_h = "0x" + "ca" * 32
    open_h = "0x" + "be" * 32

    results: list[tuple[str, str]] = []

    # ① register_content
    submit(creator_s, lambda pub, n: Transaction.register_content(
        pub, n, content_id=cid, root_hash=rh, generation_id=gid))
    settle()
    c = get(f"/content/{cid}")
    results.append(("① register_content",
                    "PASS" if c.get("creator") == creator_a else f"FAIL: {c}"))

    # ② revert_double_register
    h0 = head_height()
    submit(creator_s, lambda pub, n: Transaction.register_content(
        pub, n, content_id=cid, root_hash=rh, generation_id=gid))
    results.append(("② revert_double_register",
                    assert_block_count_unchanged(h0, "double register")))

    # ③ revert_generation_id_collision (different cid, same gid)
    h0 = head_height()
    submit(bad_s, lambda pub, n: Transaction.register_content(
        pub, n, content_id=cid2, root_hash=rh, generation_id=gid))
    results.append(("③ revert_generation_id_collision",
                    assert_block_count_unchanged(h0, "gid collision")))

    # ④ order_fee_split_99_1: buyer createOrder 100000 → treasury +1000, escrow +99000
    treas_before = get(f"/account/{treasury_addr}")["balance"]
    esc_before   = get("/account/0xescrow")["balance"]
    oid = "0x" + hashlib.sha256(b"native-order-1").hexdigest()
    submit(buyer_s, lambda pub, n: Transaction.create_order(
        pub, n, order_id=oid, content_id=cid, seller=seller_a, value=100_000))
    settle()
    treas_after = get(f"/account/{treasury_addr}")["balance"]
    esc_after   = get("/account/0xescrow")["balance"]
    fee_ok    = (treas_after - treas_before) == 1000
    escrow_ok = (esc_after - esc_before) == 99_000
    results.append(("④ order_fee_split_99_1",
                    "PASS" if (fee_ok and escrow_ok) else
                    f"FAIL: Δtreasury={treas_after-treas_before} Δescrow={esc_after-esc_before}"))

    # ⑤ full_finalize_releases_to_seller
    seller_before = get(f"/account/{seller_a}")["balance"]
    submit(seller_s, lambda pub, n: Transaction.submit_proof(
        pub, n, order_id=oid, role="packing", proof_hash=pack_h))
    settle()
    submit(buyer_s, lambda pub, n: Transaction.submit_proof(
        pub, n, order_id=oid, role="opening", proof_hash=open_h))
    settle()
    submit(treasury_seed, lambda pub, n: Transaction.finalize(
        pub, n, order_id=oid, valid=True))
    settle()
    seller_after = get(f"/account/{seller_a}")["balance"]
    results.append(("⑤ full_finalize_releases_to_seller",
                    "PASS" if (seller_after - seller_before) == 99_000
                    else f"FAIL: Δseller={seller_after - seller_before}"))

    # ⑥ invalid_finalize_refunds_buyer_and_locks_seller
    seller2_s, seller2_a, _ = keygen_local()
    post("/credit", {"to": seller2_a, "amount": 100_000})
    settle()
    submit(seller2_s, lambda pub, n: Transaction.stake(pub, n, amount=50_000))
    settle()
    oid2 = "0x" + hashlib.sha256(b"native-order-fraud").hexdigest()
    buyer_before = get(f"/account/{buyer_a}")["balance"]
    treas_b2     = get(f"/account/{treasury_addr}")["balance"]
    submit(buyer_s, lambda pub, n: Transaction.create_order(
        pub, n, order_id=oid2, content_id=cid, seller=seller2_a, value=100_000))
    settle()
    submit(seller2_s, lambda pub, n: Transaction.submit_proof(
        pub, n, order_id=oid2, role="packing", proof_hash=pack_h))
    settle()
    submit(buyer_s, lambda pub, n: Transaction.submit_proof(
        pub, n, order_id=oid2, role="opening", proof_hash=open_h))
    settle()
    submit(treasury_seed, lambda pub, n: Transaction.finalize(
        pub, n, order_id=oid2, valid=False))
    settle()

    buyer_after = get(f"/account/{buyer_a}")["balance"]
    treas_a2    = get(f"/account/{treasury_addr}")["balance"]
    s2 = get(f"/account/{seller2_a}")
    refund_ok = (buyer_after - buyer_before) == -1000   # paid 100000, refunded 99000
    slash_ok  = (treas_a2 - treas_b2) == 50_000 + 1000  # slashed 50k + fee
    locked_ok = s2["locked"] is True and s2["stake"] == 0
    results.append(("⑥ invalid_finalize_refunds_buyer_and_locks_seller",
                    "PASS" if (refund_ok and slash_ok and locked_ok) else
                    f"FAIL: refund={buyer_after-buyer_before} treasury={treas_a2-treas_b2} "
                    f"locked={s2['locked']} stake={s2['stake']}"))

    # ⑦ locked_node_cannot_create_orders (as a seller)
    h0 = head_height()
    oid3 = "0x" + hashlib.sha256(b"native-order-locked-seller").hexdigest()
    submit(buyer_s, lambda pub, n: Transaction.create_order(
        pub, n, order_id=oid3, content_id=cid, seller=seller2_a, value=100_000))
    results.append(("⑦ locked_node_cannot_create_orders",
                    assert_block_count_unchanged(h0, "create_order with locked seller")))

    # ⑧ locked_node_cannot_register_content (locked seller2 tries)
    h0 = head_height()
    cid3 = "0x" + hashlib.sha256(b"native-content-3").hexdigest()
    submit(seller2_s, lambda pub, n: Transaction.register_content(
        pub, n, content_id=cid3, root_hash=rh, generation_id=None))
    results.append(("⑧ locked_node_cannot_register_content",
                    assert_block_count_unchanged(h0, "register from locked")))

    # ⑨ revert_finalize_by_non_treasury (bad actor tries finalize)
    # we need a fresh order in OpeningDone state
    seller3_s, seller3_a, _ = keygen_local()
    post("/credit", {"to": seller3_a, "amount": 10_000})
    oid4 = "0x" + hashlib.sha256(b"native-order-non-treasury").hexdigest()
    submit(buyer_s, lambda pub, n: Transaction.create_order(
        pub, n, order_id=oid4, content_id=cid, seller=seller3_a, value=10_000))
    settle()
    submit(seller3_s, lambda pub, n: Transaction.submit_proof(
        pub, n, order_id=oid4, role="packing", proof_hash=pack_h))
    settle()
    submit(buyer_s, lambda pub, n: Transaction.submit_proof(
        pub, n, order_id=oid4, role="opening", proof_hash=open_h))
    settle()
    h0 = head_height()
    submit(bad_s, lambda pub, n: Transaction.finalize(pub, n, order_id=oid4, valid=True))
    results.append(("⑨ revert_finalize_by_non_treasury",
                    assert_block_count_unchanged(h0, "non-treasury finalize")))

    # ⑩ revert_pack_by_non_seller (bad actor tries packing on someone else's order)
    h0 = head_height()
    submit(bad_s, lambda pub, n: Transaction.submit_proof(
        pub, n, order_id=oid4, role="packing", proof_hash=pack_h))
    results.append(("⑩ revert_pack_by_non_seller",
                    assert_block_count_unchanged(h0, "pack by non-seller")))

    # ⑪ revert_open_before_pack (new order, buyer tries opening immediately)
    seller4_s, seller4_a, _ = keygen_local()
    post("/credit", {"to": seller4_a, "amount": 5_000})
    oid5 = "0x" + hashlib.sha256(b"native-order-open-before-pack").hexdigest()
    submit(buyer_s, lambda pub, n: Transaction.create_order(
        pub, n, order_id=oid5, content_id=cid, seller=seller4_a, value=5_000))
    settle()
    h0 = head_height()
    submit(buyer_s, lambda pub, n: Transaction.submit_proof(
        pub, n, order_id=oid5, role="opening", proof_hash=open_h))
    results.append(("⑪ revert_open_before_pack",
                    assert_block_count_unchanged(h0, "open before pack")))

    # report
    print("\n══════════════════════════════════════════════════════════════")
    print("  Phase 4 Solidity parity on MORM Chain L1")
    print("══════════════════════════════════════════════════════════════")
    pass_count = 0
    for name, status in results:
        marker = "✓" if status == "PASS" else "✗"
        print(f"  {marker}  {name:55}  {status}")
        if status == "PASS":
            pass_count += 1
    print(f"\n  {pass_count} / {len(results)} passed.")


if __name__ == "__main__":
    main()
