#!/usr/bin/env python3
"""samples/manifest.json の動画を MORM Play へ実投稿してカタログを埋める。

- staked エントリ = ステーク済み「サンプル制作者」アカウントで投稿(worker が承認)。
- new エントリ    = 新規T0アカウントで投稿(worker が pending_review へ→人手UIデモ用)。
署名は既存ウォレットと同じ Ed25519 + canonical。encode/分類は本番pipelineが実施。

使い方: PLAY=https://play.morm.one ADMIN=<token> python3 seed_samples.py
"""
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PLAY = os.environ.get("PLAY", "https://play.morm.one").rstrip("/")
ADMIN = os.environ.get("ADMIN", "")
HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "samples", "manifest.json")


def canon(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ",".join(canon(x) for x in v) + "]"
    return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + canon(v[k]) for k in sorted(v)) + "}"


def req(path, data=None, ct="application/json", timeout=200):
    r = urllib.request.Request(PLAY + path, data=data,
                               headers={"content-type": ct, "User-Agent": "morm-seed/1.0"})
    try:
        return json.loads(urllib.request.urlopen(r, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def get(path, timeout=60):
    r = urllib.request.Request(PLAY + path, headers={"User-Agent": "morm-seed/1.0"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())


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


def main():
    items = json.load(open(MANIFEST))
    skip = int(os.environ.get("SKIP", "0"))
    staked = Signer()
    get(f"/api/me?pub={staked.pub}")
    # ステーク付与: T3(無制限)でサンプル一括投入。'new'は都度フレッシュ鍵(各T0=1/日)で人手キュー分散。
    print("stake:", req("/api/admin/set-stake",
          json.dumps({"token": ADMIN, "m0r": staked.m0r, "staked_morm": 50000}).encode()).get("tier"))
    ok = fail = 0
    for i, it in enumerate(items):
        if i < skip:
            continue
        if it.get("tier") == "staked":
            s = staked
        else:
            s = Signer()  # 'new' は毎回新規T0アカウント(1件ずつ→人手キューに複数入る)
            get(f"/api/me?pub={s.pub}")
        payload = {"title": it["title"], "description": it.get("description", ""),
                   "tags": it.get("tags", []), "ar": "portrait", "duration": 5, "links": []}
        r = s.init(payload)
        if not r.get("id"):
            print(f"[{i+1}/{len(items)}] INIT FAIL {it['title']}: {r.get('error')}")
            fail += 1
            continue
        try:
            with open(it["path"], "rb") as f:
                raw = f.read()
        except Exception as e:
            print(f"[{i+1}] read fail {it['path']}: {e}")
            fail += 1
            continue
        up = req(f"/api/upload/{r['id']}/media?token={r['token']}", raw, "application/octet-stream")
        if up.get("ok"):
            print(f"[{i+1}/{len(items)}] {up['status']:14s} {it.get('tier','staked'):6s} {it['title']}")
            ok += 1
        else:
            print(f"[{i+1}/{len(items)}] MEDIA FAIL {it['title']}: {up.get('error')}")
            fail += 1
    print(f"\ndone: {ok} ok / {fail} fail. worker がAI審査を進めます。")
    print(f"staked m0r={staked.m0r}\nnew m0r={newbie.m0r}")


if __name__ == "__main__":
    if not ADMIN:
        raise SystemExit("ADMIN token required")
    main()
