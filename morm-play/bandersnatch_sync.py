#!/usr/bin/env python3
"""Bandersnatch 束縛レジストリ → PLAY への定期同期（仕様(b)案）。

node-dashboard(Turso) の正典 `bs_node_agent` を PLAY(play_catalog.db) の accounts へ反映する。
PLAY は Turso を直接読めないため、node-dashboard の公開API `/api/bandersnatch/agents` を取得して
is_agent=1 / owner_m0r / node_id を upsert する。**加算的**（レジストリ外の admin 指定 agent は消さない
＝現行の投稿bot等を壊さない）。cron 数分間隔で実行。

env: NODE_BASE(既定 https://node.morm.one), CATALOG_DB(既定 ~/morm-play/play_catalog.db)
usage: python3 bandersnatch_sync.py [--once]
"""
import os, sys, json, time, sqlite3, urllib.request

NODE_BASE = os.environ.get("NODE_BASE", "https://node.morm.one").rstrip("/")
CATALOG_DB = os.environ.get("CATALOG_DB", os.path.expanduser("~/morm-play/play_catalog.db"))


def fetch_agents():
    url = f"{NODE_BASE}/api/bandersnatch/agents"
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read()).get("agents", [])


def sync_once():
    agents = fetch_agents()
    conn = sqlite3.connect(CATALOG_DB)
    n = 0
    for a in agents:
        m0r = (a.get("agent_m0r") or "").strip()
        owner = (a.get("owner_payout_addr") or "").strip()
        node_id = (a.get("node_id") or "").strip()
        if not m0r.startswith("m0r"):
            continue
        # ensure_account 相当（無ければ作る）＋ is_agent/owner/node を反映（加算的・消さない）
        conn.execute(
            "INSERT OR IGNORE INTO accounts(m0r,created_at,trust_score,verified,staked_morm,strikes,status)"
            " VALUES(?,?,0,0,0,0,'active')", (m0r, int(time.time())))
        conn.execute("UPDATE accounts SET is_agent=1, owner_m0r=?, node_id=? WHERE m0r=?",
                     (owner, node_id, m0r))
        n += 1
    conn.commit()
    conn.close()
    return n, len(agents)


def main():
    once = "--once" in sys.argv
    while True:
        try:
            synced, total = sync_once()
            print(f"[bs-sync] {time.strftime('%Y-%m-%d %H:%M:%S')} synced={synced}/{total} from {NODE_BASE}", flush=True)
        except Exception as e:
            print(f"[bs-sync] error: {e}", flush=True)
        if once:
            break
        time.sleep(int(os.environ.get("BS_SYNC_INTERVAL", "300")))


if __name__ == "__main__":
    main()
