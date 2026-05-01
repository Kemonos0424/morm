"""End-to-end MORM PoC on the native L1 chain.

Pipeline:
  Phase 1 (encode + V-Hash)
    → Phase 2 (screening: ACCEPTED into local DB)
    → MORM L1 registerContent (Phase 4/10d native module)
    → Phase 5 evidence — packing/opening videos with MORM L1 block hashes
    → submitProof packing (seller) + opening (buyer)
    → finalize (treasury) — refund/release + slash decisioning
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MORM_L1 = ROOT / "morm-l1"
MORM_CORE = ROOT / "morm-core"
PYBIN = MORM_CORE / ".venv" / "bin" / "python"
RPC = "http://127.0.0.1:8900"

sys.path.insert(0, str(MORM_L1))
from morm_l1 import crypto
from morm_l1.tx import Transaction


def get(path):
    return json.loads(urllib.request.urlopen(RPC + path).read())


def post(path, body):
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        RPC + path, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})).read())


def submit(seed_hex, factory):
    seed = bytes.fromhex(seed_hex)
    pub = crypto.pubkey_from_seed(seed)
    nonce = get(f"/account/{crypto.address(pub)}")["nonce"]
    return post("/tx", factory(pub, nonce).sign(seed).to_dict())


def keygen_local():
    seed, pub = crypto.keygen()
    return seed.hex(), crypto.address(pub)


def settle(s=1.5):
    time.sleep(s)


def main():
    # ── Phase 1: encode the source video into 3-second WebM cells ────────
    print("══ Phase 1: encode (morm-core encode) ══")
    sample = MORM_CORE / "samples" / "sample.mp4"
    out_dir = MORM_CORE / "output"
    subprocess.run([
        str(PYBIN), "-m", "morm_core.cli", "encode", str(sample),
        "--creator", "akihisa-l1", "--out", str(out_dir),
    ], cwd=MORM_CORE, check=True)
    manifest_path = out_dir / "sample" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    cells_count = len(manifest["cells"])
    print(f"   → {cells_count} cells, content_id={manifest['content_id'][:18]}…")

    # ── Phase 2: screening DB (already covered in earlier phases) ────────
    print("\n══ Phase 2: screen ══")
    # reset screening DB so re-runs are idempotent
    db = MORM_CORE / "output" / "morm.db"
    for ext in ("", "-shm", "-wal"):
        f = Path(str(db) + ext)
        if f.exists(): f.unlink()
    subprocess.run([str(PYBIN), "-m", "morm_core.cli", "screen", str(manifest_path)],
                    cwd=MORM_CORE, check=True)

    # ── Phase 4/10d: registerContent on MORM Chain L1 ─────────────────────
    print("\n══ Phase 4/10d: register on MORM Chain ══")
    treas = json.loads(Path("/tmp/k_treas.json").read_text())
    creator_seed, creator_addr = keygen_local()
    buyer_seed,   buyer_addr   = keygen_local()
    seller_seed,  seller_addr  = keygen_local()
    for addr, amt in [(creator_addr, 100_000), (buyer_addr, 1_000_000),
                       (seller_addr, 100_000)]:
        post("/credit", {"to": addr, "amount": amt})

    # canonicalize manifest IDs to bytes32 hex
    cid_bytes = bytes.fromhex(manifest["content_id"])
    cid = "0x" + cid_bytes.hex()
    rh  = "0x" + hashlib.sha256(b"manifest-root").hexdigest()
    gid = "0x" + hashlib.sha256(b"morm-l1-gen-id").hexdigest()

    submit(creator_seed, lambda pub, n: Transaction.register_content(
        pub, n, content_id=cid, root_hash=rh, generation_id=gid))
    settle()
    on_chain = get(f"/content/{cid}")
    assert on_chain["creator"] == creator_addr, on_chain
    print(f"   ✓ registered. creator={on_chain['creator']}")

    # ── Phase 4/10d: createOrder (1% fee, 99% lock) ───────────────────────
    print("\n══ Phase 4/10d: createOrder ══")
    submit(seller_seed, lambda pub, n: Transaction.stake(pub, n, amount=50_000))
    settle()

    order_id = "0x" + hashlib.sha256(b"morm-l1-e2e-order").hexdigest()
    treas_b = get(f"/account/{treas['address']}")["balance"]
    submit(buyer_seed, lambda pub, n: Transaction.create_order(
        pub, n, order_id=order_id, content_id=cid, seller=seller_addr, value=100_000))
    settle()
    treas_a = get(f"/account/{treas['address']}")["balance"]
    print(f"   ✓ Δtreasury={treas_a - treas_b} (expect +1000 fee)")
    assert treas_a - treas_b == 1000

    # ── Phase 5: packing/opening evidence with MORM L1 block hashes ──────
    print("\n══ Phase 5: physical evidence (MORM Chain block hashes) ══")
    sys.path.insert(0, str(MORM_CORE))
    from morm_core.evidence import latest_block_hash  # uses /info auto-detect

    pack_block_hash, pack_block_num = latest_block_hash(RPC)
    print(f"   packing@block #{pack_block_num} hash={pack_block_hash[:18]}…")
    pack_evidence = MORM_CORE / "output" / "evidence-l1" / "packing"
    subprocess.run([
        str(PYBIN), "-m", "morm_core.cli", "evidence",
        str(MORM_CORE / "samples" / "pack.mp4"),
        "--role", "packing", "--order-id", order_id,
        "--block-hash", pack_block_hash,
        "--out", str(pack_evidence.parent),
    ], cwd=MORM_CORE, check=True, capture_output=True)
    pack_meta = json.loads((pack_evidence.parent / "packing-pack" / "evidence.json").read_text())
    pack_proof = pack_meta["proof_hash"]
    print(f"   packing proof_hash={pack_proof[:18]}…")

    submit(seller_seed, lambda pub, n: Transaction.submit_proof(
        pub, n, order_id=order_id, role="packing", proof_hash=pack_proof))
    settle()

    # advance the chain a couple of blocks so opening lands on a later block
    for _ in range(2):
        post("/credit", {"to": "0xtreasury_dummy_no_op", "amount": 0}) if False else None
        time.sleep(1.1)

    open_block_hash, open_block_num = latest_block_hash(RPC)
    print(f"   opening@block #{open_block_num} hash={open_block_hash[:18]}…")
    open_evidence = MORM_CORE / "output" / "evidence-l1" / "opening"
    subprocess.run([
        str(PYBIN), "-m", "morm_core.cli", "evidence",
        str(MORM_CORE / "samples" / "open.mp4"),
        "--role", "opening", "--order-id", order_id,
        "--block-hash", open_block_hash,
        "--out", str(open_evidence.parent),
    ], cwd=MORM_CORE, check=True, capture_output=True)
    open_meta = json.loads((open_evidence.parent / "opening-open" / "evidence.json").read_text())
    open_proof = open_meta["proof_hash"]
    print(f"   opening proof_hash={open_proof[:18]}…")

    submit(buyer_seed, lambda pub, n: Transaction.submit_proof(
        pub, n, order_id=order_id, role="opening", proof_hash=open_proof))
    settle()

    # validator check: opening block# > packing block#
    chronology_ok = open_block_num > pack_block_num
    print(f"   chronology valid: {chronology_ok} (packing #{pack_block_num} → opening #{open_block_num})")

    # ── finalize ─────────────────────────────────────────────────────────
    print("\n══ Phase 4/10d: finalize ══")
    seller_b = get(f"/account/{seller_addr}")["balance"]
    submit(treas["seed_hex"], lambda pub, n: Transaction.finalize(
        pub, n, order_id=order_id, valid=chronology_ok))
    settle()
    seller_a = get(f"/account/{seller_addr}")["balance"]
    print(f"   ✓ Δseller={seller_a - seller_b} (expect +99000 if valid)")
    assert seller_a - seller_b == (99_000 if chronology_ok else 0)

    # ── final ledger ─────────────────────────────────────────────────────
    print("\n══ final ledger on MORM Chain ══")
    o = get(f"/order/{order_id}")
    print(f"   order status={o['status']} (4=Finalized, 5=Refunded)")
    print(f"   /content/{cid[:14]}… = {get(f'/content/{cid}')}")

    info = get("/info")
    latest = info["latest"][0]
    print(f"\n   latest block #{latest['height']} state_root={latest['state_root'][:16]}…")
    print(f"   total blocks produced: {latest['height']}")


if __name__ == "__main__":
    main()
