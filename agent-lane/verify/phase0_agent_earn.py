#!/usr/bin/env python3
"""MORM Agent Lane — Phase 0 proof.

Proves the full loop end-to-end on a REAL (ephemeral, local) MORM L1:

  1. an AI agent mints a fresh did:key-style Ed25519 identity -> m0r address
  2. the agent SIGNS a REGISTER_CONTENT (kind:1) tx and publishes on-chain
     (= "agent did something useful / published to MORM")
  3. the treasury pays the agent with a real TRANSFER (kind:6) tx
     (= the exact primitive MORM Play uses to pay creators)
  4. we confirm the agent now holds real, spendable on-chain MORM
  5. the agent SPENDS part of it (kind:6) to prove the balance is real

Zero production risk: spins up its own throwaway single-node chain in a temp
dir on port 8901, then tears it down. No Mac Mini / no ADMIN_TOKEN needed.

Run:  python3 phase0_agent_earn.py
"""
import json, os, secrets, subprocess, sys, tempfile, time, shutil, urllib.request

L1 = "/Users/akihisayachida/Desktop/MORM/morm-l1"
sys.path.insert(0, L1)
from morm_l1 import crypto
from morm_l1.tx import Transaction

PORT = 8901
RPC = f"http://127.0.0.1:{PORT}"


def rpc_get(path):
    return json.loads(urllib.request.urlopen(RPC + path, timeout=10).read())


def rpc_post(path, body):
    req = urllib.request.Request(RPC + path, method="POST",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def wait_up(timeout=25):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            return rpc_get("/info")
        except Exception:
            time.sleep(0.4)
    raise RuntimeError("node did not come up")


def wait_balance(addr, want, timeout=25):
    t0 = time.time()
    while time.time() - t0 < timeout:
        bal = rpc_get(f"/account/{addr}")["balance"]
        if bal >= want:
            return bal
        time.sleep(0.6)
    return rpc_get(f"/account/{addr}")["balance"]


def wait_content(cid, timeout=25):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = rpc_get(f"/content/{cid}")
            if "error" not in r:
                return r
        except Exception:
            pass
        time.sleep(0.6)
    return None


def hr(t): print("\n" + "=" * 68 + f"\n{t}\n" + "=" * 68)


def main():
    # ---- treasury / producer identity (funded 1e18 at genesis) -------------
    prod_seed, prod_pub = crypto.keygen()
    treasury = crypto.address(prod_pub)

    data_dir = tempfile.mkdtemp(prefix="morm-phase0-")
    env = {**os.environ, "MORM_PRODUCER_SEED": prod_seed.hex(), "PYTHONPATH": L1}
    proc = subprocess.Popen(
        [sys.executable, "-m", "morm_l1.cli", "node",
         "--data-dir", data_dir, "--treasury", treasury,
         "--host", "127.0.0.1", "--port", str(PORT),
         "--no-seed-discovery", "--genesis-lockdown-height", "0"],
        env=env, cwd=L1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        info = wait_up()
        hr("L1 NODE UP (ephemeral single-node chain)")
        print("rpc       :", RPC)
        print("treasury  :", treasury)
        tbal = rpc_get(f"/account/{treasury}")["balance"]
        print("treasury balance (genesis):", tbal, "MORM units", f"(=1e18? {tbal==10**18})")

        # ---- 1. agent identity --------------------------------------------
        agent_seed, agent_pub = crypto.keygen()
        agent = crypto.address(agent_pub)
        hr("1) AGENT IDENTITY MINTED (fresh Ed25519, no signup)")
        print("agent address :", agent)
        print("agent pubkey  :", agent_pub.hex())
        print("agent balance :", rpc_get(f"/account/{agent}")["balance"], "(starts at zero)")

        # ---- 2. agent publishes content (kind:1), self-signed -------------
        cid = "0x" + secrets.token_hex(16)
        root = "0x" + secrets.token_hex(32)
        tx1 = Transaction.register_content(agent_pub, 0, content_id=cid, root_hash=root)
        tx1.sign(agent_seed)
        r1 = rpc_post("/tx", tx1.to_dict())
        hr("2) AGENT PUBLISHES (REGISTER_CONTENT kind:1, agent-signed)")
        print("content_id :", cid)
        print("submit resp:", r1)
        rec = wait_content(cid)
        print("on-chain content record:", json.dumps(rec, ensure_ascii=False))
        assert rec and rec.get("creator") == agent, "agent should own the content"
        print("=> creator == agent  ✓  (verified on-chain authorship)")

        # ---- 3. treasury pays the agent (kind:6) — the Play payout primitive
        tnonce = rpc_get(f"/account/{treasury}")["nonce"]
        REWARD = 5000
        tx2 = Transaction.transfer(prod_pub, tnonce, to=agent, amount=REWARD)
        tx2.sign(prod_seed)
        r2 = rpc_post("/tx", tx2.to_dict())
        hr("3) TREASURY PAYS AGENT (TRANSFER kind:6 — real on-chain payout)")
        print("reward     :", REWARD, "MORM units")
        print("submit resp:", r2)
        bal = wait_balance(agent, REWARD)
        print("agent balance after payout:", bal)
        assert bal == REWARD, "agent should have received the reward"
        print("=> agent received real on-chain MORM  ✓")

        # ---- 4. agent SPENDS part (proves the balance is real & spendable) -
        sink_seed, sink_pub = crypto.keygen()
        sink = crypto.address(sink_pub)
        anonce = rpc_get(f"/account/{agent}")["nonce"]
        SPEND = 1500
        tx3 = Transaction.transfer(agent_pub, anonce, to=sink, amount=SPEND)
        tx3.sign(agent_seed)
        r3 = rpc_post("/tx", tx3.to_dict())
        hr("4) AGENT SPENDS ITS EARNINGS (TRANSFER kind:6, agent-signed)")
        print("spend      :", SPEND, "to", sink)
        print("submit resp:", r3)
        sbal = wait_balance(sink, SPEND)
        abal = rpc_get(f"/account/{agent}")["balance"]
        print("sink balance :", sbal, "| agent remaining:", abal)
        assert sbal == SPEND and abal == REWARD - SPEND
        print("=> earnings are real, spendable MORM  ✓")

        hr("PHASE 0 RESULT: LOOP PROVEN ✓")
        print("agent published on-chain, earned real MORM from treasury, and spent it.")
        print("This is exactly MORM Play's creator-payout primitive, driven by a")
        print("fresh agent identity instead of the studio account. Tx hashes:")
        print("  publish (kind1):", r1.get("tx_hash"))
        print("  payout  (kind6):", r2.get("tx_hash"))
        print("  spend   (kind6):", r3.get("tx_hash"))
        head = rpc_get("/info")["head_height"]
        print("chain head height:", head)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
