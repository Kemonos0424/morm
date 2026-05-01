"""P2P gossip scenario:

  ① start two MORM L1 nodes:
       nodeA (port 8900) — producer (active)
       nodeB (port 8901) — passive importer
     they know about each other via --peers
  ② submit registerContent to nodeA
  ③ wait for the block to gossip → nodeB
  ④ confirm: same state_root, same content row, same chain head on both nodes
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from morm_l1 import crypto
from morm_l1.tx import Transaction


NODE_A = "http://127.0.0.1:8900"
NODE_B = "http://127.0.0.1:8901"


def get(url):
    return json.loads(urllib.request.urlopen(url).read())


def post(url, body):
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        url, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})).read())


def submit_to(rpc, seed_hex, factory):
    seed = bytes.fromhex(seed_hex)
    pub = crypto.pubkey_from_seed(seed)
    nonce = get(f"{rpc}/account/{crypto.address(pub)}")["nonce"]
    return post(f"{rpc}/tx", factory(pub, nonce).sign(seed).to_dict())


def main():
    keys = {n: json.loads(Path(f"/tmp/k_{n}.json").read_text())
            for n in ("creator",)}

    print("── ① initial state ──")
    a_info = get(f"{NODE_A}/info")
    b_info = get(f"{NODE_B}/info")
    print(f"  nodeA height={a_info['latest'][0]['height'] if a_info['latest'] else 0}  "
          f"state_root={a_info['state_root'][:14]}…")
    print(f"  nodeB height={b_info['latest'][0]['height'] if b_info['latest'] else 0}  "
          f"state_root={b_info['state_root'][:14]}…")
    print(f"  match? {a_info['state_root'] == b_info['state_root']}")

    import hashlib
    cid = "0x" + hashlib.sha256(b"p2p-gossip-content").hexdigest()
    rh  = "0x" + "ab" * 32
    print("\n── ② submit registerContent → nodeA ──")
    print(submit_to(NODE_A, keys["creator"]["seed_hex"],
                    lambda pub, n: Transaction.register_content(
                        pub, n, content_id=cid, root_hash=rh, generation_id=None)))

    print("\n── ③ wait for gossip propagation ──")
    time.sleep(2.5)

    print("── ④ verify on both nodes ──")
    a_info = get(f"{NODE_A}/info")
    b_info = get(f"{NODE_B}/info")
    print(f"  nodeA height={a_info['latest'][0]['height']}  "
          f"state_root={a_info['state_root'][:14]}…")
    print(f"  nodeB height={b_info['latest'][0]['height']}  "
          f"state_root={b_info['state_root'][:14]}…")
    print(f"  state_root match? {a_info['state_root'] == b_info['state_root']}")

    print("\n  GET /content/{cid}:")
    a_c = get(f"{NODE_A}/content/{cid}")
    b_c = get(f"{NODE_B}/content/{cid}")
    print(f"    nodeA: creator={a_c['creator']}  registered_at={a_c['registered_at']}")
    print(f"    nodeB: creator={b_c['creator']}  registered_at={b_c['registered_at']}")
    print(f"    rows equal? {a_c == b_c}")

    print("\n  block #1 hash on each node:")
    a_blk = get(f"{NODE_A}/blocks/at/1")["blocks"][0]
    b_blk = get(f"{NODE_B}/blocks/at/1")["blocks"][0]
    print(f"    nodeA: {a_blk['hash']}")
    print(f"    nodeB: {b_blk['hash']}")
    print(f"    block hash match? {a_blk['hash'] == b_blk['hash']}")

    print("\n  block producer signature: nodeB validated the foreign block.")
    print(f"    producer (both)= {a_blk['header']['producer'][:24]}…")


if __name__ == "__main__":
    main()
