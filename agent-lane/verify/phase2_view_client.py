#!/usr/bin/env python3
"""Phase 2 view_by_other verification: a SIGNED other-viewer's qualified view
credits the CREATOR with a point, which the proportional settle pays out on-chain.
Guards: self-view earns nothing, unsigned view earns nothing, repeat viewer no double.
Env is set by the runner BEFORE import (play_server reads constants at import)."""
import os, sys, time, json, urllib.request

PLAY = "/Users/akihisayachida/Desktop/MORM/morm-play"
L1 = "/Users/akihisayachida/Desktop/MORM/morm-l1"
sys.path.insert(0, PLAY); sys.path.insert(0, L1)
RPC = os.environ["MORM_L1_RPC"]
from morm_l1 import crypto
import play_server as ps


def l1_balance(addr):
    try:
        a = json.loads(urllib.request.urlopen(f"{RPC}/account/{addr}", timeout=10).read())
        return int(a.get("balance", 0))
    except Exception:
        return 0

def hr(t): print("\n" + "=" * 64 + f"\n{t}\n" + "=" * 64)
def assert_(c, m):
    if not c: print("ASSERT FAILED:", m); sys.exit(1)
def addr():
    _, pub = crypto.keygen(); return crypto.address(pub)
def creator_points(acct):
    conn = ps._db()
    n = conn.execute("SELECT COALESCE(SUM(points),0) FROM point_ledger WHERE account=? AND kind='view'",
                     (acct,)).fetchone()[0]
    conn.close(); return n


def main():
    ps._init_db()
    hr("CONFIG"); print("VIEW_EARN:", ps.VIEW_EARN, "| EMISSION_MODE:", ps.EMISSION_MODE,
                        "| PT_VIEW:", ps.POINT_VALUES.get("view"))
    assert_(ps.VIEW_EARN == "on" and ps.EMISSION_MODE == "proportional", "need VIEW_EARN=on + proportional")

    creator, v1, v2 = addr(), addr(), addr()
    cid = "m0v" + creator[3:16]
    conn = ps._db()
    conn.execute("INSERT INTO content(id,play_cid,title,tags,uploader,created_at,views,likes,hue,ar) "
                 "VALUES(?,?,?,?,?,?,?,?,?,?)", (cid, "DEMO", "t", "", creator, int(time.time()), 0, 0, 0, "portrait"))
    conn.commit(); conn.close()
    print("creator:", creator, "\ncontent:", cid)

    hr("1) SIGNED other-viewer qualified view -> creator earns")
    r = ps.record_watch(cid, watched=5, completed=True, viewer=v1, ip_hash="ip1", viewer_verified=True)
    print("record_watch:", r)
    assert_(r.get("counted") and r.get("creator_awarded") == 1, "verified other-view should award creator 1")

    hr("2) same viewer again -> no double (dedup)")
    r = ps.record_watch(cid, watched=5, completed=True, viewer=v1, ip_hash="ip1", viewer_verified=True)
    print("record_watch:", r)
    assert_((r.get("creator_awarded") or 0) == 0, "repeat viewer must not double-award")

    hr("3) self-view (creator watches own) -> no award")
    r = ps.record_watch(cid, watched=5, completed=True, viewer=creator, ip_hash="ip3", viewer_verified=True)
    print("record_watch:", r)
    assert_((r.get("creator_awarded") or 0) == 0, "self-view must not award")

    hr("4) UNSIGNED viewer -> counts view but no award")
    r = ps.record_watch(cid, watched=5, completed=True, viewer=v2, ip_hash="ip4", viewer_verified=False)
    print("record_watch:", r)
    assert_((r.get("creator_awarded") or 0) == 0, "unsigned view must not award")

    pts = creator_points(creator)
    print("\ncreator 'view' points in ledger:", pts)
    assert_(pts == 1, "creator should have exactly 1 view point")

    hr("5) proportional settle -> creator paid on-chain")
    b0 = l1_balance(creator)
    res = ps.settle_points()
    print("settle:", json.dumps(res, ensure_ascii=False))
    B_units = int(round(ps.B_EPOCH_MORM * ps.MORM_BASE_UNITS_PER_MORM))
    b1 = b0
    for _ in range(20):
        b1 = l1_balance(creator)
        if b1 > b0: break
        time.sleep(0.6)
    print(f"creator balance {b0} -> {b1} (got {b1-b0}, budget {B_units})")
    assert_(b1 - b0 == B_units, "sole earner should receive the whole epoch budget")

    hr("view_by_other PROVEN")
    print("signed other-view -> creator earns -> proportional payout on-chain.")
    print("self/unsigned/repeat all correctly earn nothing.")


if __name__ == "__main__":
    main()
