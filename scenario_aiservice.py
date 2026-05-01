"""End-to-end Generation ID + AI service attestation scenario.

  ① AI service generates a video deterministically (prompt+seed → bytes)
  ② Manifest is signed with the service's ed25519 key (gen_id || cid)
  ③ treasury REGISTER_AI_SERVICE — whitelist the issuing pubkey on chain
  ④ creator submits registerContent WITH attestation → ACCEPTED
  ⑤ attacker tries to claim the same generation_id under their own key
       → rejected (`ai_pubkey not whitelisted`)
  ⑥ attacker tries to forge a signature with the legitimate AI key but
     wrong cid → rejected (`invalid AI service signature`)
  ⑦ second AI generation with different prompt → different gen_id, ACCEPTED
"""
from __future__ import annotations
import hashlib, json, sys, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "morm-l1"))
from morm_l1 import crypto
from morm_l1.tx import Transaction

RPC = "http://127.0.0.1:8900"


def get(p): return json.loads(urllib.request.urlopen(RPC+p).read())
def post(p, b):
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        RPC+p, method="POST", data=json.dumps(b).encode(),
        headers={"Content-Type": "application/json"})).read())


def submit(seed, factory):
    pub = crypto.pubkey_from_seed(seed)
    nonce = get(f"/account/{crypto.address(pub)}")["nonce"]
    return post("/tx", factory(pub, nonce).sign(seed).to_dict())


def main():
    treas = json.loads(Path("/tmp/k_treas.json").read_text())
    treas_seed = bytes.fromhex(treas["seed_hex"])

    # ── ① generate via the AI service ────────────────────────────────────
    print("── ① AI service generates a video (deterministic) ──")
    import subprocess
    out = subprocess.run([
        sys.executable, str(ROOT/"morm-aiservice"/"aiservice.py"),
        "generate", "--prompt", "a swarm of glowing fireflies", "--seed", "42",
        "--bucket", "0",   # explicit bucket so deterministic across runs
    ], capture_output=True, text=True, check=True).stdout
    manifest1 = json.loads(out)
    print(f"   gen_id   = {manifest1['generation_id']}")
    print(f"   cid      = {manifest1['content_id']}")
    print(f"   ai_addr  = {manifest1['ai_service_address']}")

    # ── ② treasury registers the AI service ──────────────────────────────
    print("\n── ② treasury REGISTER_AI_SERVICE ──")
    res = submit(treas_seed, lambda pub, n: Transaction.register_ai_service(
        pub, n,
        ai_pubkey_hex=manifest1["ai_service_pubkey"],
        name="MORM-AI-v1",
    ))
    print(f"   {res}")
    time.sleep(1.5)
    print(f"   /ai-services: {get('/ai-services')}")

    # ── ③ creator submits registerContent WITH attestation ──────────────
    print("\n── ③ creator registerContent w/ Generation ID + signature ──")
    creator_seed, creator_pub = crypto.keygen()
    creator_addr = crypto.address(creator_pub)
    res = submit(creator_seed, lambda pub, n: Transaction.register_content(
        pub, n,
        content_id=manifest1["content_id"],
        root_hash="0x" + "ab"*32,
        generation_id=manifest1["generation_id"],
        ai_pubkey_hex=manifest1["ai_service_pubkey"],
        ai_signature_hex=manifest1["signature"],
    ))
    print(f"   {res}")
    time.sleep(1.5)
    on_chain = get(f"/content/{manifest1['content_id']}")
    print(f"   on-chain creator = {on_chain['creator']} (expect {creator_addr})")
    print(f"   matches? {on_chain['creator'] == creator_addr}")

    # ── ④ attacker claims same gen_id under their own key (no attestation) ─
    print("\n── ④ attacker claim same gen_id without attestation ──")
    att_seed, att_pub = crypto.keygen()
    fake_cid = "0x" + hashlib.sha256(b"fake-attacker-content").hexdigest()
    h0 = head_height()
    res = submit(att_seed, lambda pub, n: Transaction.register_content(
        pub, n,
        content_id=fake_cid,
        root_hash="0x" + "ff"*32,
        generation_id=manifest1["generation_id"],   # collision attempt
        ai_pubkey_hex=manifest1["ai_service_pubkey"],
        ai_signature_hex=manifest1["signature"],    # signed for a different cid
    ))
    print(f"   submitted: {res}")
    time.sleep(1.5)
    print(f"   block grew? {head_height() > h0} (must be False — gen_id collision OR sig invalid)")

    # ── ⑤ attacker forges with their own (non-whitelisted) AI key ────────
    print("\n── ⑤ attacker uses their own AI key (not whitelisted) ──")
    rogue_seed, rogue_pub = crypto.keygen()
    fake_gid = "0x" + hashlib.sha256(b"rogue-gen-id").hexdigest()
    fake_cid2 = "0x" + hashlib.sha256(b"rogue-content").hexdigest()
    msg = bytes.fromhex(fake_gid[2:]) + bytes.fromhex(fake_cid2[2:])
    rogue_sig = crypto.sign(rogue_seed, msg).hex()
    h0 = head_height()
    res = submit(att_seed, lambda pub, n: Transaction.register_content(
        pub, n,
        content_id=fake_cid2, root_hash="0x"+"ff"*32,
        generation_id=fake_gid,
        ai_pubkey_hex=rogue_pub.hex(),
        ai_signature_hex=rogue_sig,
    ))
    print(f"   submitted: {res}")
    time.sleep(1.5)
    print(f"   block grew? {head_height() > h0} (must be False — pubkey not whitelisted)")

    # ── ⑥ legit second generation with different prompt ──────────────────
    print("\n── ⑥ a different prompt → different gen_id, ACCEPTED ──")
    out2 = subprocess.run([
        sys.executable, str(ROOT/"morm-aiservice"/"aiservice.py"),
        "generate", "--prompt", "a calm forest at dawn", "--seed", "777",
        "--bucket", "0",
    ], capture_output=True, text=True, check=True).stdout
    manifest2 = json.loads(out2)
    print(f"   gen_id (new) = {manifest2['generation_id']}")
    print(f"   != orig     = {manifest1['generation_id'] != manifest2['generation_id']}")
    creator2_seed, creator2_pub = crypto.keygen()
    res = submit(creator2_seed, lambda pub, n: Transaction.register_content(
        pub, n,
        content_id=manifest2["content_id"],
        root_hash="0x"+"cd"*32,
        generation_id=manifest2["generation_id"],
        ai_pubkey_hex=manifest2["ai_service_pubkey"],
        ai_signature_hex=manifest2["signature"],
    ))
    print(f"   submitted: {res}")
    time.sleep(1.5)
    on2 = get(f"/content/{manifest2['content_id']}")
    print(f"   second on-chain creator = {on2.get('creator')}")


def head_height():
    bs = get("/blocks/latest?n=1")["blocks"]
    return bs[0]["height"] if bs else 0


if __name__ == "__main__":
    main()
