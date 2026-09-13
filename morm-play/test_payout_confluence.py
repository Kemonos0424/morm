#!/usr/bin/env python3
"""報酬合流(Phase2)のテスト環境: 実L1を触らず l1_transfer をスタブして送金先だけ検証する。
  - agent口座(owner=pool)の稼ぎ → pool へ着地
  - agent(owner未設定)     → 自分へ着地(安全側)
  - 人間の作者             → 自分へ着地(合流しない)
usage: python3 test_payout_confluence.py
"""
import os, tempfile, importlib.util, time

POOL = "m0rtp37vwh5vxxyxmibxxe6o2g3bzkeomtc"  # 報酬プール口座(owner_m0r)
BOT = "m0rBOT_agent_with_owner"
BOT2 = "m0rBOT_agent_no_owner"
HUMAN = "m0rHUMAN_creator"

def load():
    tmp = tempfile.mkdtemp()
    os.environ["CATALOG_DB"] = os.path.join(tmp, "t.db")
    os.environ["ADMIN_TOKEN"] = "t"
    os.environ["VIEW_RATE"] = "1"      # テスト用: 少数の再生で閾値超え
    os.environ["LIKE_RATE"] = "1"
    os.environ["PAYOUT_MIN"] = "1"
    spec = importlib.util.spec_from_file_location("ps", os.path.join(os.path.dirname(__file__), "play_server.py"))
    ps = importlib.util.module_from_spec(spec); spec.loader.exec_module(ps)
    ps._init_db()
    return ps

def add_content(ps, uploader, cid, views, likes):
    c = ps._db()
    c.execute("INSERT INTO content(id,play_cid,title,tags,uploader,created_at,views,likes,hue,ar,status)"
              " VALUES(?,?,?,?,?,?,?,?,?,?, 'approved')",
              (cid, "pc" + cid, "t" + cid, "", uploader, int(time.time()), views, likes, 0, "portrait"))
    c.commit(); c.close()

def main():
    ps = load()
    # l1_transfer をスタブ(実送金しない・宛先と額を記録)
    sent = []
    ps.l1_transfer = lambda to, amount, **kw: (sent.append((to, amount)) or f"txTEST{len(sent)}")

    # 口座セットアップ
    for m in (BOT, BOT2, HUMAN, POOL):
        ps.ensure_account(m)
    c = ps._db()
    c.execute("UPDATE accounts SET is_agent=1, owner_m0r=? WHERE m0r=?", (POOL, BOT))
    c.execute("UPDATE accounts SET is_agent=1, owner_m0r='' WHERE m0r=?", (BOT2,))  # agentだがowner未設定
    c.commit(); c.close()

    # 各作者に作品を用意。earnings は views×VIEW_RATE + 適格like×LIKE_RATE。
    # ここは合流ルーティング検証が目的なので views で金額を決める(like適格性はL1/L2側の別テスト)。
    add_content(ps, BOT, "aaa", views=5, likes=0)     # earned=5
    add_content(ps, BOT2, "bbb", views=4, likes=0)    # earned=4
    add_content(ps, HUMAN, "ccc", views=2, likes=0)   # earned=2

    r1 = ps.payout(BOT)
    r2 = ps.payout(BOT2)
    r3 = ps.payout(HUMAN)
    dest = {to: amt for to, amt in sent}

    ok = True
    def check(label, cond):
        nonlocal ok
        print(("PASS" if cond else "FAIL"), label)
        ok = ok and cond

    check("agent(owner=pool) の送金先が pool", (POOL in dest) and (POOL, 5) in sent)
    check("agent(owner未設定) は自分に着地", (BOT2, 4) in sent)
    check("人間の作者は自分に着地(合流なし)", (HUMAN, 2) in sent)
    check("pool宛は1回のみ(取り違えなし)", sum(1 for t, _ in sent if t == POOL) == 1)
    check("payout結果 paid 合計 = 5+4+2", (r1["paid"], r2["paid"], r3["paid"]) == (5, 4, 2))

    print("送金記録:", sent)
    print("=> ", "ALL PASS" if ok else "FAILED")
    raise SystemExit(0 if ok else 1)

if __name__ == "__main__":
    main()
