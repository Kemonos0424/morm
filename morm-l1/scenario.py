"""End-to-end MORM L1 scenario:
  ① bootstrap: treasury credits buyer/seller
  ② creator → registerContent
  ③ buyer → createOrder
  ④ seller → submit-proof packing
  ⑤ buyer → submit-proof opening
  ⑥ treasury → finalize valid
  ⑦ verify on-chain state
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from morm_l1 import crypto
from morm_l1.tx import Transaction


RPC = "http://127.0.0.1:8900"


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        RPC + path, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())


def get(path: str):
    return json.loads(urllib.request.urlopen(RPC + path).read())


def submit(seed_hex: str, tx_factory) -> dict:
    seed = bytes.fromhex(seed_hex)
    pub = crypto.pubkey_from_seed(seed)
    nonce = get(f"/account/{crypto.address(pub)}")["nonce"]
    tx = tx_factory(pub, nonce).sign(seed)
    return post("/tx", tx.to_dict())


def main():
    keys = {n: json.loads(Path(f"/tmp/k_{n}.json").read_text())
            for n in ("prod", "treas", "creator", "buyer", "seller")}

    print("── ① bootstrap: treasury credits buyer + seller ──")
    print(post("/credit", {"to": keys["buyer"]["address"], "amount": 1_000_000}))
    print(post("/credit", {"to": keys["seller"]["address"], "amount": 500_000}))

    cid = "0x" + hashlib.sha256(b"morm-l1-content").hexdigest()
    rh  = "0x" + "ab" * 32
    gid = "0x" + "ef" * 32
    oid = "0x" + hashlib.sha256(b"order-A").hexdigest()
    pack_h = "0x" + "ca" * 32
    open_h = "0x" + "be" * 32

    print("\n── ② creator → registerContent ──")
    print(submit(keys["creator"]["seed_hex"],
                 lambda pub, n: Transaction.register_content(
                     pub, n, content_id=cid, root_hash=rh, generation_id=gid)))
    time.sleep(1.5)

    print("\n── ③ buyer → createOrder (value=100000) ──")
    print(submit(keys["buyer"]["seed_hex"],
                 lambda pub, n: Transaction.create_order(
                     pub, n, order_id=oid, content_id=cid,
                     seller=keys["seller"]["address"], value=100_000)))
    time.sleep(1.5)

    print("\n── ④ seller → submit packing proof ──")
    print(submit(keys["seller"]["seed_hex"],
                 lambda pub, n: Transaction.submit_proof(
                     pub, n, order_id=oid, role="packing", proof_hash=pack_h)))
    time.sleep(1.5)

    print("\n── ⑤ buyer → submit opening proof ──")
    print(submit(keys["buyer"]["seed_hex"],
                 lambda pub, n: Transaction.submit_proof(
                     pub, n, order_id=oid, role="opening", proof_hash=open_h)))
    time.sleep(1.5)

    print("\n── ⑥ treasury → finalize valid ──")
    print(submit(keys["treas"]["seed_hex"],
                 lambda pub, n: Transaction.finalize(
                     pub, n, order_id=oid, valid=True)))
    time.sleep(1.5)

    print("\n── /content ──"); print(json.dumps(get(f"/content/{cid}"), indent=2))
    print("\n── /order ──"); print(json.dumps(get(f"/order/{oid}"), indent=2))

    print("\n── balances ──")
    for label, addr in [
        ("treasury", keys["treas"]["address"]),
        ("buyer",    keys["buyer"]["address"]),
        ("seller",   keys["seller"]["address"]),
        ("escrow",   "0xescrow"),
    ]:
        a = get(f"/account/{addr}")
        print(f"  {label:>10}  bal={a['balance']:>15}  nonce={a['nonce']}  "
              f"stake={a['stake']} locked={a['locked']}")

    print("\n── recent blocks (height + hash + parents + state_root) ──")
    for b in get("/blocks/latest?n=10")["blocks"]:
        parents = [p[:8] + "…" for p in b["parents"]]
        print(f"  #{b['height']:>2}  hash={b['hash'][:14]}…  parents={parents}  "
              f"state_root={b['state_root'][:12]}…")


if __name__ == "__main__":
    main()
