#!/usr/bin/env python3
"""#2 フリート・マニフェスト・エクスポータ — hpmini で実行(Turso資格 + vault + morm_l1)。
active な My Agent(my_agents.status='active') を巡回し、agent_m0r/pack/pub(vault seedから導出)/seed_file
を agents.json として出す。fleet_run.py の入力。★seed本体は出さない(seed_fileパスのみ)。

usage(hpmini): cd ~/morm/morm-worker && /home/hpmini/morm/morm-l1/.venv/bin/python fleet_manifest.py > agents.json
env(config.env共用): TURSO_DATABASE_URL / TURSO_AUTH_TOKEN / MORM_DIR / AGENTS_DIR
"""
import os, sys, json, base64, urllib.request, pathlib

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
sys.path.insert(0, MORM_DIR)
from morm_l1 import crypto

def _arg(v):
    return {"type": "text", "value": str(v)} if v is not None else {"type": "null"}
def turso(sql, args=None):
    body = {"requests": [{"type": "execute", "stmt": {"sql": sql, "args": [_arg(a) for a in (args or [])]}}, {"type": "close"}]}
    req = urllib.request.Request(TURSO_URL + "/v2/pipeline", data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer " + TURSO_TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.loads(r.read())
    res = out["results"][0]["response"]["result"]
    cols = [c["name"] for c in res["cols"]]
    def dec(c):
        return None if c.get("type") == "null" else c.get("value")
    return [dict(zip(cols, [dec(c) for c in row])) for row in res["rows"]]

def main():
    rows = turso("SELECT node_id, agent_m0r, pack_id, prod_credits FROM my_agents WHERE status='active' AND agent_m0r IS NOT NULL")
    manifest = []
    for r in rows:
        m0r = r["agent_m0r"]; sf = os.path.join(AGENTS_DIR, f"{m0r}.seed")
        if not os.path.exists(sf):
            print(f"# warn: vault欠落 {m0r}", file=sys.stderr); continue
        seed = bytes.fromhex(open(sf).read().strip())
        pub = crypto.pubkey_from_seed(seed).hex()
        manifest.append({"agent_m0r": m0r, "pub": pub, "pack": r["pack_id"], "seed_file": sf,
                         "boost": int(r.get("prod_credits") or 0)})
    json.dump(manifest, sys.stdout, ensure_ascii=False, indent=2)
    print(f"\n# {len(manifest)} active agents", file=sys.stderr)

if __name__ == "__main__":
    main()
