#!/usr/bin/env python3
"""Task C 検証: settle 4経路の予約先行(reservation-first)による二重支払い防止/失敗ロールバック。
l1_transfer をモックし、実チェーン無しでクラッシュ回復の冪等性を実証する。"""
import os, sys, tempfile, importlib

TMP = tempfile.mkdtemp()
os.environ["CATALOG_DB"] = os.path.join(TMP, "test.db")
os.environ["MORM_L1_RPC"] = "http://127.0.0.1:59999"  # 呼ばれない(l1_transferをモック)
os.environ.setdefault("PT_PER_MORM", "5")
os.environ.setdefault("PT_MIN_SETTLE", "5")

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import play_server as ps
ps._init_db()

FAILS = 0
def check(name, cond):
    global FAILS
    print(("  ok  " if cond else " FAIL ") + name)
    if not cond:
        FAILS += 1

# ---- l1_transfer モック(送金先/失敗条件を制御し、呼び出しを記録) --------------
class Bank:
    def __init__(self):
        self.calls = []          # [(to, amount)]
        self.fail_for = set()    # このアドレス宛は例外
    def transfer(self, to, amount, confirm_timeout=25):
        self.calls.append((to, int(amount)))
        if to in self.fail_for:
            raise RuntimeError("simulated on-chain fail")
        return "0x" + hex(len(self.calls))[2:].rjust(8, "0")
    def sent_to(self, to):
        return [a for (t, a) in self.calls if t == to]

def db():
    return ps._db()

def reset_bank():
    b = Bank()
    ps.l1_transfer = b.transfer
    return b

# =====================================================================
# settle_referrals — 2レッグ(被招待者+招待者)
# =====================================================================
print("\n[settle_referrals]")
REFR, REFE = "m0rreferrer", "m0rreferee"
def setup_ref():
    c = db()
    c.execute("DELETE FROM referrals")
    c.execute("INSERT INTO referrals(referee,referrer,created_at,qualified,rewarded) "
              "VALUES(?,?,?,1,0)", (REFE, REFR, 1))
    c.commit(); c.close()

# R1: 正常系 + 再実行で二重支払いしない
setup_ref()
b = reset_bank()
r1 = ps.settle_referrals()
n_after_first = len(b.calls)
r2 = ps.settle_referrals()          # 再実行
check("R1 初回で2レッグ送金", n_after_first == 2)
check("R1 再実行で追加送金ゼロ(=二重支払いしない)", len(b.calls) == n_after_first)
c = db(); row = c.execute("SELECT rewarded,reward_tx_referee,reward_tx_referrer FROM referrals WHERE referee=?", (REFE,)).fetchone(); c.close()
check("R1 rewarded=1 確定", row["rewarded"] == 1)
check("R1 両txハッシュ記録", row["reward_tx_referee"] and row["reward_tx_referrer"] and "pending" not in (row["reward_tx_referee"], row["reward_tx_referrer"]))

# R2: 被招待者レッグ失敗 → 完全ロールバック(rewarded=0で再試行可能)
setup_ref()
b = reset_bank(); b.fail_for = {REFE}
ps.settle_referrals()
c = db(); row = c.execute("SELECT rewarded FROM referrals WHERE referee=?", (REFE,)).fetchone(); c.close()
check("R2 被招待者失敗→rewarded=0にロールバック", row["rewarded"] == 0)
check("R2 招待者へは送っていない(被招待者で中断)", b.sent_to(REFR) == [])
# 復旧: 成功で再試行 → 今度は支払われる
b = reset_bank()
ps.settle_referrals()
check("R2 復旧後: 被招待者に1回だけ支払い", len(b.sent_to(REFE)) == 1)

# R3: 招待者レッグ失敗(被招待者は着地済み) → rewarded=1維持・被招待者を二重支払いしない
setup_ref()
b = reset_bank(); b.fail_for = {REFR}
ps.settle_referrals()
c = db(); row = c.execute("SELECT rewarded,reward_tx_referee,reward_tx_referrer FROM referrals WHERE referee=?", (REFE,)).fetchone(); c.close()
check("R3 招待者失敗でも rewarded=1 維持", row["rewarded"] == 1)
check("R3 被招待者txは記録", row["reward_tx_referee"] and row["reward_tx_referee"] != "pending")
check("R3 招待者は未払いマーカー('')=監査可(過少支払い)", row["reward_tx_referrer"] == "")
b = reset_bank()
ps.settle_referrals()                # 再実行しても
check("R3 再実行で被招待者を二重支払いしない", b.sent_to(REFE) == [])

# =====================================================================
# settle_points (_settle_fixed) — 台帳 settled フラグ
# =====================================================================
print("\n[settle_points / fixed]")
ACC = "m0rpointer"
def setup_points(pts):
    c = db()
    c.execute("DELETE FROM point_ledger"); c.execute("DELETE FROM point_payouts")
    c.execute("DELETE FROM point_settle_runs")
    c.execute("INSERT INTO point_ledger(account,kind,content_id,points,ts,settled) VALUES(?,?,?,?,?,0)",
              (ACC, "like", "c1", pts, 1))
    c.commit(); c.close()

# F1: 正常 + 再実行で二重支払いしない
setup_points(10)                     # 10pt / 5 = 2 MORM
b = reset_bank()
ps.settle_points()
first = len(b.calls)
ps.settle_points()
check("F1 初回で1送金(2MORM)", first == 1 and b.calls[0][1] == 2)
check("F1 再実行で追加送金ゼロ", len(b.calls) == first)
c = db(); n_settled = c.execute("SELECT COUNT(*) FROM point_ledger WHERE account=? AND settled=1", (ACC,)).fetchone()[0]; c.close()
check("F1 台帳 settled=1", n_settled == 1)

# F2: 送金失敗 → settled=0 に巻き戻し・配分記録も減算(再試行可能)
setup_points(10)
b = reset_bank(); b.fail_for = {ACC}
ps.settle_points()
c = db()
n_unsettled = c.execute("SELECT COUNT(*) FROM point_ledger WHERE account=? AND settled=0", (ACC,)).fetchone()[0]
pr = c.execute("SELECT paid_morm FROM point_payouts WHERE account=?", (ACC,)).fetchone()
c.close()
check("F2 失敗→settled=0にロールバック", n_unsettled == 1)
check("F2 失敗→paid_morm=0に減算", (pr["paid_morm"] if pr else 0) == 0)
b = reset_bank()
ps.settle_points()
check("F2 復旧後に1回だけ支払い", len(b.sent_to(ACC)) == 1 and b.sent_to(ACC)[0] == 2)

# =====================================================================
# settle_challenge — PK(slug,m0r) 原子的クレーム
# =====================================================================
print("\n[settle_challenge]")
SLUG, WINNER = "chal-test", "m0rwinner"
def setup_challenge():
    c = db()
    c.execute("DELETE FROM challenges"); c.execute("DELETE FROM challenge_awards")
    c.execute("DELETE FROM content")
    c.execute("INSERT INTO challenges(slug,title,creator,created_at,reward_pool,status) "
              "VALUES(?,?,?,?,?, 'active')", (SLUG, "T", "m0radmin", 1, 100))
    c.execute("INSERT INTO content(id,play_cid,title,created_at,uploader,likes,views,status,challenge) "
              "VALUES(?,?,?,?,?,?,?, 'approved', ?)", ("cc1", "p1", "w", 1, WINNER, 10, 0, SLUG))
    c.commit(); c.close()

# C1: 正常 + 再実行で二重授与しない
setup_challenge()
b = reset_bank()
ps.settle_challenge(SLUG, pool=100, top=1)
first = len(b.calls)
ps.settle_challenge(SLUG, pool=100, top=1)
check("C1 初回で1授与送金", first == 1 and b.sent_to(WINNER) == [100])
check("C1 再実行で追加送金ゼロ(already)", len(b.calls) == first)
c = db(); aw = c.execute("SELECT tx FROM challenge_awards WHERE slug=? AND m0r=?", (SLUG, WINNER)).fetchone(); c.close()
check("C1 award.tx 記録(pending解消)", aw and aw["tx"] and aw["tx"] != "pending")

# C2: 送金失敗 → award行を削除(ロールバック)・再試行可能
setup_challenge()
b = reset_bank(); b.fail_for = {WINNER}
ps.settle_challenge(SLUG, pool=100, top=1)
c = db(); aw = c.execute("SELECT 1 FROM challenge_awards WHERE slug=? AND m0r=?", (SLUG, WINNER)).fetchone(); c.close()
check("C2 失敗→award行を削除(ロールバック)", aw is None)
b = reset_bank()
ps.settle_challenge(SLUG, pool=100, top=1)
check("C2 復旧後に1回だけ授与", b.sent_to(WINNER) == [100])

print("\n" + ("ALL PASS" if FAILS == 0 else f"{FAILS} FAILED"))
sys.exit(1 if FAILS else 0)
