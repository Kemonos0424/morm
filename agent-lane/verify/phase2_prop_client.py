#!/usr/bin/env python3
"""Phase 2-② verification: budget-capped PROPORTIONAL settlement in play_server.

Drives play_server.settle_points() in proportional mode against an ephemeral L1
and asserts the core tokenomics invariants:
  • total emitted == B_epoch (fixed budget; no runaway with more participants)
  • each account gets floor(B_units × P_i / ΣP)  (proportional to contribution)
  • payout is real on-chain MORM (l1_transfer / kind:6)
Env is set by the runner BEFORE import (play_server reads constants at import).
"""
import os, sys, time, json, urllib.request

PLAY = "/Users/akihisayachida/Desktop/MORM/morm-play"
L1 = "/Users/akihisayachida/Desktop/MORM/morm-l1"
sys.path.insert(0, PLAY)
sys.path.insert(0, L1)

RPC = os.environ["MORM_L1_RPC"]
from morm_l1 import crypto           # for making valid m0r recipient addresses
import play_server as ps


def l1_balance(addr):
    try:
        a = json.loads(urllib.request.urlopen(f"{RPC}/account/{addr}", timeout=10).read())
        return int(a.get("balance", 0))
    except Exception:
        return 0


def hr(t): print("\n" + "=" * 66 + f"\n{t}\n" + "=" * 66)
def assert_(c, m):
    if not c:
        print("ASSERT FAILED:", m); sys.exit(1)


def main():
    ps._init_db()
    hr("CONFIG")
    print("EMISSION_MODE      :", ps.EMISSION_MODE)
    print("MORM_BASE_UNITS    :", ps.MORM_BASE_UNITS_PER_MORM)
    print("B_EPOCH_MORM       :", ps.B_EPOCH_MORM)
    print("EPOCH_ACCT_CAP_FRAC:", ps.EPOCH_ACCT_CAP_FRAC)
    assert_(ps.EMISSION_MODE == "proportional", "mode must be proportional")

    # 3 recipients with contribution points 10 / 30 / 60 (Σ=100)
    accts = []
    for pts in (10, 30, 60):
        _, pub = crypto.keygen()
        accts.append({"addr": crypto.address(pub), "P": pts})
    total_P = sum(a["P"] for a in accts)

    # seed point_ledger directly (bypass grant_point caps; this is the accrual layer)
    conn = ps._db()
    for i, a in enumerate(accts):
        conn.execute("INSERT INTO point_ledger(account,kind,content_id,points,ts,settled) "
                     "VALUES(?,?,?,?,?,0)", (a["addr"], "view", f"0xc{i}", a["P"], int(time.time())))
    conn.commit(); conn.close()

    hr("BEFORE")
    for a in accts:
        a["b0"] = l1_balance(a["addr"])
        print(f'{a["addr"]}  P={a["P"]:>3}  bal={a["b0"]}')

    B_units = int(round(ps.B_EPOCH_MORM * ps.MORM_BASE_UNITS_PER_MORM))
    expected = {a["addr"]: (B_units * a["P"]) // total_P for a in accts}

    hr("SETTLE (proportional)")
    res = ps.settle_points()
    print(json.dumps(res, ensure_ascii=False))
    assert_(res.get("mode") == "proportional", "settle should run proportional")

    hr("AFTER / ASSERT")
    emitted = 0
    for a in accts:
        # wait for on-chain landing
        want = a["b0"] + expected[a["addr"]]
        b1 = a["b0"]
        for _ in range(20):
            b1 = l1_balance(a["addr"])
            if b1 >= want:
                break
            time.sleep(0.6)
        got = b1 - a["b0"]
        emitted += got
        share_frac = a["P"] / total_P
        print(f'{a["addr"]}  P={a["P"]:>3} ({share_frac:.0%})  got={got}  expected={expected[a["addr"]]}')
        assert_(got == expected[a["addr"]], f'proportional share wrong for {a["addr"]}')

    print(f"\nΣ emitted = {emitted} base units | B_units = {B_units}")
    assert_(emitted == B_units, "total emission must equal the fixed budget B (no runaway)")
    print(f"= {emitted / ps.MORM_BASE_UNITS_PER_MORM} MORM total, split 10/30/60 exactly.")

    # idempotency: a second settle with nothing unsettled emits 0
    hr("IDEMPOTENCY (re-settle)")
    res2 = ps.settle_points()
    print(json.dumps(res2, ensure_ascii=False))
    assert_(res2.get("accounts", 0) == 0, "re-settle should pay nobody (all settled)")

    hr("PHASE 2-② PROVEN")
    print("Budget-capped proportional emission: total = B (fixed), shares ∝ points,")
    print("real on-chain payout, idempotent. Fixed-rate inflation risk removed.")


if __name__ == "__main__":
    main()
