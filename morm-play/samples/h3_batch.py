#!/usr/bin/env python3
"""dgx1 上で H3 サンプルを順次生成→ play_server へ署名投稿する自律バッチ。

manifest_h3.json を読み、各案について:
  1) h3_test_run.py で縦型3秒クリップ生成(EasyCache)
  2) 生成mp4を Ed25519署名アップロード(staked制作者アカウント)
worker が非同期でカテゴリ/フレーム判定→非アダルト→approved で公開。

env: PLAY_URL(既定 Mac Mini tailnet) / ADMIN_TOKEN / START / LIMIT
"""
import base64, hashlib, json, os, re, subprocess, sys, time, urllib.request, urllib.error
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PLAY = os.environ.get("PLAY_URL", "http://100.106.58.67:8791").rstrip("/")
ADMIN = os.environ.get("ADMIN_TOKEN", "")
HOME = os.path.expanduser("~")
MANIFEST = os.environ.get("MANIFEST", f"{HOME}/h3_samples/manifest_h3.json")
RUNNER = f"{HOME}/h3_test_run.py"
OUTDIR = f"{HOME}/ComfyUI/output/video"
W, H, L, STEP = "480", "848", "73", "10"
START = int(os.environ.get("START", "0"))
LIMIT = int(os.environ.get("LIMIT", "100"))


def canon(v):
    if v is None: return "null"
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, int): return str(v)
    if isinstance(v, str): return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list): return "[" + ",".join(canon(x) for x in v) + "]"
    return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + canon(v[k]) for k in sorted(v)) + "}"


def req(path, data=None, ct="application/json", timeout=240):
    r = urllib.request.Request(PLAY + path, data=data, headers={"content-type": ct, "User-Agent": "h3-batch"})
    try:
        return json.loads(urllib.request.urlopen(r, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def get(path):
    return json.loads(urllib.request.urlopen(urllib.request.Request(PLAY + path, headers={"User-Agent": "h3-batch"}), timeout=60).read())


class Signer:
    def __init__(self):
        self.sk = Ed25519PrivateKey.generate()
        pub = self.sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.pub = pub.hex()
        self.m0r = "m0r" + base64.b32encode(hashlib.blake2b(pub, digest_size=32).digest()[-20:]).decode().lower()

    def init(self, payload):
        env = {"kind": "upload.init", "sender": self.pub, "nonce": f"{time.time()}", "payload": payload}
        env["sig"] = self.sk.sign(canon({k: env[k] for k in ("kind", "sender", "nonce", "payload")}).encode()).hex()
        return req("/api/upload/init", json.dumps(env).encode())


def h3_generate(prompt, seed):
    pf = f"{HOME}/h3_samples/_cur.txt"
    open(pf, "w").write(prompt)
    env = dict(os.environ, EC="1")
    p = subprocess.run(["python3", RUNNER, pf, W, H, L, STEP, str(seed)],
                       capture_output=True, text=True, timeout=900, env=env)
    m = re.search(r"'filename': '([^']+\.mp4)'", p.stdout)
    if m:
        return os.path.join(OUTDIR, m.group(1))
    # フォールバック: 最新mp4
    files = sorted([os.path.join(OUTDIR, f) for f in os.listdir(OUTDIR) if f.endswith(".mp4")],
                   key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def main():
    items = json.load(open(MANIFEST))[START:START + LIMIT]
    s = Signer()
    get(f"/api/me?pub={s.pub}")
    r = req("/api/admin/set-stake", json.dumps({"token": ADMIN, "m0r": s.m0r, "staked_morm": 50000}).encode())
    print(f"studio account {s.m0r} tier={r.get('tier')}  items={len(items)}", flush=True)
    ok = fail = 0
    for i, it in enumerate(items):
        idx = START + i
        seed = 1000 + idx
        t0 = time.time()
        try:
            mp4 = h3_generate(it["h3_prompt"], seed)
            if not mp4 or not os.path.exists(mp4):
                print(f"[{idx}] GEN FAIL {it['title']}", flush=True); fail += 1; continue
            payload = {"title": it["title"], "description": it.get("description", ""),
                       "tags": it.get("tags", [])[:4], "ar": "portrait", "duration": 3, "links": []}
            init = s.init(payload)
            if not init.get("id"):
                print(f"[{idx}] INIT FAIL {it['title']}: {init.get('error')}", flush=True); fail += 1; continue
            up = req(f"/api/upload/{init['id']}/media?token={init['token']}", open(mp4, "rb").read(), "application/octet-stream")
            if up.get("ok"):
                print(f"[{idx}] OK {it['category']:9s} {int(time.time()-t0):3d}s  {it['title']}", flush=True); ok += 1
            else:
                print(f"[{idx}] UP FAIL {it['title']}: {up.get('error')}", flush=True); fail += 1
        except Exception as e:
            print(f"[{idx}] ERR {it.get('title')}: {e}", flush=True); fail += 1
    print(f"\nBATCH DONE: {ok} ok / {fail} fail", flush=True)


if __name__ == "__main__":
    if not ADMIN:
        sys.exit("ADMIN_TOKEN required")
    main()
