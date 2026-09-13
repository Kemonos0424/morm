#!/usr/bin/env python3
"""My Agent(#2) provision worker — hpmini 常駐。custodial な【投稿鍵のみ】を発行する。

  my_agents.status='pending' を拾い →
    ① nodes.morm_address(=funds受取・self-custody)を確認(無ければ保留)
    ② 投稿用 ed25519 鍵を keygen → vault(0600) 保管（★funds鍵ではない・投稿しかできない運用鍵）
    ③ agent_m0r を my_agents に書戻し(status='active')
    ④ bs_node_agent に bind(owner_payout_addr = nodes.morm_address)
  → Play同期(bandersnatch_sync)が agent_m0r を is_agent=1 + owner 反映。

funds/報酬受取は一切 custodial にしない(morm_address=ユーザー自己管理)。方針=morm-payout.py と同じ。
Turso は hrana-over-HTTP /v2/pipeline を stdlib で叩く。morm-payout.py と同居(config.env 共用)想定。
env(config.env): TURSO_DATABASE_URL / TURSO_AUTH_TOKEN / MORM_DIR / AGENTS_DIR / POLL_SEC
"""
import os, sys, json, time, base64, urllib.request, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
def load_env(p):
    d = {}
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1); d[k.strip()] = v.strip()
    return d
ENV = load_env(ROOT / 'config.env')
TURSO_URL = ENV['TURSO_DATABASE_URL'].replace('libsql://', 'https://').rstrip('/')
TURSO_TOKEN = ENV['TURSO_AUTH_TOKEN']
MORM_DIR = ENV.get('MORM_DIR', '/home/hpmini/morm/morm-l1')
AGENTS_DIR = os.path.expanduser(ENV.get('AGENTS_DIR', '/home/hpmini/morm/keys/agents'))
POLL_SEC = int(ENV.get('POLL_SEC', '30'))
os.makedirs(AGENTS_DIR, mode=0o700, exist_ok=True)

sys.path.insert(0, MORM_DIR)
from morm_l1 import crypto  # keygen/address

# ---------- Turso hrana-over-HTTP（morm-payout.py と同型） ----------
def _arg(v):
    if v is None: return {"type": "null"}
    if isinstance(v, bool): return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int): return {"type": "integer", "value": str(v)}
    if isinstance(v, float): return {"type": "float", "value": v}
    return {"type": "text", "value": str(v)}
def _dec(cell):
    t = cell.get("type")
    if t == "null": return None
    if t == "integer": return int(cell["value"])
    if t == "float": return float(cell["value"])
    if t == "blob": return base64.b64decode(cell.get("base64", ""))
    return cell.get("value")
def turso(sql, args=None):
    body = {"requests": [
        {"type": "execute", "stmt": {"sql": sql, "args": [_arg(a) for a in (args or [])]}},
        {"type": "close"},
    ]}
    req = urllib.request.Request(TURSO_URL + "/v2/pipeline",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer " + TURSO_TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.loads(r.read())
    res = out["results"][0]
    if res.get("type") != "ok":
        raise RuntimeError("turso error: " + json.dumps(res)[:300])
    result = res["response"]["result"]
    cols = [c["name"] for c in result["cols"]]
    return [dict(zip(cols, [_dec(c) for c in row])) for row in result["rows"]]

def ensure_schema():
    turso("""CREATE TABLE IF NOT EXISTS my_agents (
      node_id TEXT PRIMARY KEY, agent_m0r TEXT UNIQUE, pack_id TEXT NOT NULL,
      gen_mode TEXT DEFAULT 'central', status TEXT DEFAULT 'pending',
      created_at TEXT DEFAULT (datetime('now')))""")

def provision_one(row):
    node_id = row["node_id"]
    n = turso("SELECT morm_address FROM nodes WHERE id=?", [node_id])
    owner = (n[0]["morm_address"] if n else "") or ""
    if not owner.startswith("m0r"):
        print(f"[provision] skip {node_id}: morm_address 未発行(funds受取先が無いので保留)", flush=True)
        return
    # ★投稿鍵のみ custodial（funds鍵ではない）。keygen→vault(0600)。
    seed, pub = crypto.keygen()
    agent_m0r = crypto.address(pub)
    vault = os.path.join(AGENTS_DIR, f"{agent_m0r}.seed")
    fd = os.open(vault, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(seed.hex())
    now = int(time.time())
    turso("UPDATE my_agents SET agent_m0r=?, status='active' WHERE node_id=?", [agent_m0r, node_id])
    # bind（owner_payout_addr = self-custody な morm_address）。workerは信頼済=直INSERT。
    turso("""INSERT INTO bs_node_agent (node_id, agent_m0r, owner_payout_addr, bind_sig, bind_ts)
             VALUES (?,?,?, 'worker', ?)
             ON CONFLICT(node_id) DO UPDATE SET agent_m0r=excluded.agent_m0r,
               owner_payout_addr=excluded.owner_payout_addr, bind_sig='worker', bind_ts=excluded.bind_ts""",
          [node_id, agent_m0r, owner, now])
    print(f"[provision] {node_id} → agent {agent_m0r} bound(owner={owner}) vault=0600", flush=True)

def main():
    ensure_schema()
    print(f"[agent-provision] turso={TURSO_URL[:32]}… poll={POLL_SEC}s vault={AGENTS_DIR}", flush=True)
    while True:
        try:
            pending = turso("SELECT node_id FROM my_agents WHERE status='pending' ORDER BY created_at")
            for row in pending:
                try:
                    provision_one(row)
                except Exception as e:
                    print(f"[provision] error {row.get('node_id')}: {e}", flush=True)
        except Exception as e:
            print(f"[agent-provision] poll error: {e}", flush=True)
        time.sleep(POLL_SEC)

if __name__ == "__main__":
    raise SystemExit(main())
