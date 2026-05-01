"""PoUW scenario:
  ① treasury credits poster + 2 workers
  ② creator registers a content (so jobs can reference it)
  ③ poster posts 2 transcode jobs (reward 5000 each)
  ④ workerA + workerB race to CLAIM each job (one each)
  ⑤ each worker submits a work proof (output_root) → reward releases
  ⑥ verify: workers' balances grew, jobs have status=Completed,
            worker_stats reflect 1 completed each
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


def post(path, body):
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        RPC + path, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})).read())


def get(path):
    return json.loads(urllib.request.urlopen(RPC + path).read())


def submit(seed_hex, factory):
    seed = bytes.fromhex(seed_hex)
    pub = crypto.pubkey_from_seed(seed)
    nonce = get(f"/account/{crypto.address(pub)}")["nonce"]
    return post("/tx", factory(pub, nonce).sign(seed).to_dict())


def keygen_local():
    """Return (seed_hex, address) for an ad-hoc account."""
    seed, pub = crypto.keygen()
    return seed.hex(), crypto.address(pub)


def main():
    keys = {n: json.loads(Path(f"/tmp/k_{n}.json").read_text())
            for n in ("prod", "treas", "creator")}
    # fresh workers + poster for this scenario
    poster_seed,  poster_addr  = keygen_local()
    workerA_seed, workerA_addr = keygen_local()
    workerB_seed, workerB_addr = keygen_local()

    print("── ① treasury credits poster + 2 workers ──")
    print(post("/credit", {"to": poster_addr,  "amount": 50_000}))
    print(post("/credit", {"to": workerA_addr, "amount":  1_000}))
    print(post("/credit", {"to": workerB_addr, "amount":  1_000}))

    cid = "0x" + hashlib.sha256(b"pouw-content").hexdigest()
    rh  = "0x" + "ab" * 32
    print("\n── ② creator registers a content ──")
    print(submit(keys["creator"]["seed_hex"],
                 lambda pub, n: Transaction.register_content(
                     pub, n, content_id=cid, root_hash=rh, generation_id=None)))
    time.sleep(1.5)

    # ③ post 2 transcode jobs against this content
    job1 = "0x" + hashlib.sha256(b"job-1").hexdigest()
    job2 = "0x" + hashlib.sha256(b"job-2").hexdigest()
    print("\n── ③ poster posts 2 transcode jobs (reward=5000 each) ──")
    print(submit(poster_seed, lambda pub, n: Transaction.post_job(
        pub, n, job_id=job1, content_id=cid, kind="transcode", reward=5000)))
    time.sleep(1.5)
    print(submit(poster_seed, lambda pub, n: Transaction.post_job(
        pub, n, job_id=job2, content_id=cid, kind="transcode", reward=5000)))
    time.sleep(1.5)

    # poster's balance should be 50_000 - 5_000 - 5_000 = 40_000
    print(f"  poster balance: {get(f'/account/{poster_addr}')['balance']} (expect 40000)")
    print(f"  escrow balance: {get('/account/0xescrow')['balance']} (expect 10000)")

    # ④ workers claim
    print("\n── ④ workers race to claim ──")
    print(submit(workerA_seed, lambda pub, n: Transaction.claim_job(pub, n, job_id=job1)))
    print(submit(workerB_seed, lambda pub, n: Transaction.claim_job(pub, n, job_id=job2)))
    time.sleep(1.5)

    # workerA tries to claim job2 — should fail (already claimed)
    print("\n── ⑤ workerA tries to double-claim job2 (expect rejection) ──")
    print(submit(workerA_seed, lambda pub, n: Transaction.claim_job(pub, n, job_id=job2)))
    time.sleep(1.5)
    print(f"  job2 claimer: {get(f'/job/{job2}')['claimer']}  (should be {workerB_addr})")

    # ⑥ submit work proofs
    out1 = "0x" + hashlib.sha256(b"output-root-1").hexdigest()
    out2 = "0x" + hashlib.sha256(b"output-root-2").hexdigest()
    print("\n── ⑥ workers submit proofs ──")
    print(submit(workerA_seed, lambda pub, n: Transaction.submit_work_proof(
        pub, n, job_id=job1, output_root=out1)))
    print(submit(workerB_seed, lambda pub, n: Transaction.submit_work_proof(
        pub, n, job_id=job2, output_root=out2)))
    time.sleep(1.5)

    # ⑦ verify
    print("\n── final state ──")
    for label, addr in [
        ("poster",   poster_addr),
        ("workerA",  workerA_addr),
        ("workerB",  workerB_addr),
        ("escrow",   "0xescrow"),
    ]:
        a = get(f"/account/{addr}")
        ws = get(f"/worker/{addr}")
        print(f"  {label:>10}  bal={a['balance']:>7}  worker.completed={ws['completed']:>2}  earned={ws['earned']:>6}")

    j1 = get(f"/job/{job1}"); j2 = get(f"/job/{job2}")
    print(f"\n  job1 status={j1['status']}  claimer={j1['claimer']}  output_root={j1['output_root'][:18]}…")
    print(f"  job2 status={j2['status']}  claimer={j2['claimer']}  output_root={j2['output_root'][:18]}…")

    print("\n── recent blocks ──")
    for b in get("/blocks/latest?n=10")["blocks"]:
        print(f"  #{b['height']:>2}  hash={b['hash'][:14]}…  state_root={b['state_root'][:12]}…")


if __name__ == "__main__":
    main()
