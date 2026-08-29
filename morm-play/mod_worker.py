#!/usr/bin/env python3
"""MORM Play モデレーション worker — status='pending' を pull → DGX分類 → verdict書戻し。

play_server とは HTTP(pull/verdict API)で疎結合。Mac Mini でも hpmini でも動く
（PLAY_URL を変えるだけ）。LLM推論は DGX Ollama で走る（moderation.py 経由）。

環境変数:
  PLAY_URL     play_server ベース (default http://127.0.0.1:8791)
  ADMIN_TOKEN  pull/verdict 用トークン (必須)
  POLL_EVERY   空振り時のポーリング間隔秒 (default 3)
"""
import json
import os
import time
import urllib.request

from moderation import moderate

PLAY_URL = os.environ.get("PLAY_URL", "http://127.0.0.1:8791").rstrip("/")
_tf = os.path.expanduser("~/.morm-worker-token")
# ★token はファイル優先(env より前)。ローテは ~/.morm-worker-token に書いて worker を kill するだけ
#   (systemd Restart=always が自動再起動)=root/sudo 不要。無ければ従来どおり env から。
ADMIN_TOKEN = (open(_tf).read().strip() if os.path.exists(_tf) else os.environ.get("ADMIN_TOKEN", ""))
POLL_EVERY = int(os.environ.get("POLL_EVERY", "3"))
GATEWAY = os.environ.get("GATEWAY", "http://100.80.207.111:8801")  # フレーム取得元


def _get(path):
    # ★token は URL ではなく X-Admin-Token ヘッダで送る(ログ/Referer 露出回避)。
    req = urllib.request.Request(PLAY_URL + path, headers={"X-Admin-Token": ADMIN_TOKEN})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def _post(path, obj):
    req = urllib.request.Request(PLAY_URL + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def main():
    if not ADMIN_TOKEN:
        print("ADMIN_TOKEN required", flush=True)
        return 2
    print(f"[mod-worker] play={PLAY_URL} model-host=DGX poll={POLL_EVERY}s", flush=True)
    while True:
        try:
            items = _get("/api/mod/pull?limit=1").get("items", [])
        except Exception as e:
            print(f"pull error: {e}", flush=True)
            time.sleep(POLL_EVERY)
            continue
        if not items:
            time.sleep(POLL_EVERY)
            continue
        it = items[0]
        verdict = moderate(it["title"], it["description"], it["tags"], it["tier"],
                           play_cid=it.get("play_cid"), gateway=GATEWAY)
        try:
            _post("/api/mod/verdict", {"token": ADMIN_TOKEN, "id": it["id"], "verdict": verdict})
            fl = verdict.get("frame_labels")
            print(f"[{it['id']}] {verdict['status']}/{verdict['category']}/{verdict['rating']} "
                  f"({verdict['model']}) reason={verdict['reason']}"
                  + (f" frame={ {k:round(v,2) for k,v in fl.items() if v>0} }" if fl else " frame=none"), flush=True)
        except Exception as e:
            print(f"verdict error {it['id']}: {e}", flush=True)
            time.sleep(POLL_EVERY)


if __name__ == "__main__":
    raise SystemExit(main())
