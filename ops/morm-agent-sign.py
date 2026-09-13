#!/usr/bin/env python3
"""#2 My Agent 署名プロキシ — hpmini・tailnet限定。custodial 投稿鍵(vault seed)を【外に出さず】
Mac側フリートの代理投稿に署名だけ提供する。seedはhpminiから一切出ない=custodial isolation維持。

POST /sign {"agent_m0r":"m0r…","msg_hex":"<canonical(env)のhex>"} → {"sig_hex":…,"pub_hex":…}
  vault(/home/hpmini/morm/keys/agents/<agent_m0r>.seed) がある(=provision済)agentのみ署名。
GET /health → ok。
tailnet(100.64/10)からのみ到達させる想定でtailnet IPにbind(公開しない)。

env(config.env共用): MORM_DIR / AGENTS_DIR / SIGN_BIND(既定 100.80.207.111) / SIGN_PORT(既定 8802)
"""
import os, sys, json, pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
MORM_DIR = ENV.get('MORM_DIR', '/home/hpmini/morm/morm-l1')
AGENTS_DIR = os.path.expanduser(ENV.get('AGENTS_DIR', '/home/hpmini/morm/keys/agents'))
BIND = ENV.get('SIGN_BIND', '100.80.207.111')  # tailnet IP(公開しない)
PORT = int(ENV.get('SIGN_PORT', '8802'))
sys.path.insert(0, MORM_DIR)
from morm_l1 import crypto

_M0R_RE = __import__('re').compile(r'^m0r[a-z2-7]{32}$')

def _seed_for(m0r):
    if not _M0R_RE.match(m0r or ''):
        return None
    sf = os.path.join(AGENTS_DIR, f"{m0r}.seed")
    if not os.path.exists(sf):
        return None
    return bytes.fromhex(open(sf).read().strip())

class H(BaseHTTPRequestHandler):
    def _j(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a):
        pass
    def do_GET(self):
        if self.path == '/health':
            return self._j(200, {"ok": True})
        return self._j(404, {"error": "not found"})
    def do_POST(self):
        if self.path != '/sign':
            return self._j(404, {"error": "not found"})
        try:
            ln = int(self.headers.get('Content-Length', '0') or '0')
            data = json.loads(self.rfile.read(ln) or b'{}')
        except Exception:
            return self._j(400, {"error": "bad json"})
        m0r = (data.get('agent_m0r') or '').strip()
        msg_hex = (data.get('msg_hex') or '').strip()
        seed = _seed_for(m0r)
        if seed is None:
            return self._j(403, {"error": "unknown/unprovisioned agent"})
        try:
            msg = bytes.fromhex(msg_hex)
        except Exception:
            return self._j(400, {"error": "msg_hex invalid"})
        sig = crypto.sign(seed, msg)
        pub = crypto.pubkey_from_seed(seed)
        return self._j(200, {"sig_hex": sig.hex(), "pub_hex": pub.hex()})

def main():
    print(f"[agent-sign] bind {BIND}:{PORT} vault={AGENTS_DIR}", flush=True)
    ThreadingHTTPServer((BIND, PORT), H).serve_forever()

if __name__ == "__main__":
    main()
