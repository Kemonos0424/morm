#!/usr/bin/env python3
"""実フレームから起こしたタイトル/タグに再キャプション(中身とinfoの不一致を是正)。

dgx1で実行: ffmpeg(フレーム抽出) + ローカルVL(qwen2.5vl) + Mac Mini API + hpmini gateway。
使い方: python3 recaption.py [--dry] [--limit N] [--only <id,id,...>]
env: PLAY_URL / GATEWAY / VL_OLLAMA / VL_MODEL / ADMIN_TOKEN
"""
import base64
import json
import os
import sys
import time
import urllib.request

from moderation import extract_frames

PLAY = os.environ.get("PLAY_URL", "http://100.106.58.67:8791")
GATEWAY = os.environ.get("GATEWAY", "http://100.80.207.111:8801")
VL_HOST = os.environ.get("VL_OLLAMA", "http://127.0.0.1:11434").split(",")[0]
VL_MODEL = os.environ.get("VL_MODEL", "qwen2.5vl:7b")
TOKEN = os.environ.get("ADMIN_TOKEN", "adm_1b378edd49741f4661bd")
CATS = ["music", "dance", "art", "gaming", "vlog", "comedy", "food", "travel",
        "fashion", "beauty", "tech", "education", "news", "sports", "pets",
        "nature", "asmr"]

DRY = "--dry" in sys.argv
LIMIT = None
ONLY = None
for i, a in enumerate(sys.argv):
    if a == "--limit":
        LIMIT = int(sys.argv[i + 1])
    if a == "--only":
        ONLY = set(sys.argv[i + 1].split(","))


def get_json(url, timeout=60, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def post_json(url, obj, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def caption(frames):
    imgs = [base64.b64encode(b).decode() for b in frames]
    prompt = (
        "これは短い縦型動画の実フレームです。実際に写っている内容だけを根拠に、"
        "日本語で魅力的かつ簡潔なタイトル(全角16文字以内・鉤括弧や引用符やハッシュタグを含めない)、"
        "内容を表す英小文字タグ3〜5個、カテゴリを1つだけ選び、厳密なJSONのみ返す"
        "(前後の文やコードフェンス禁止)。"
        "カテゴリ候補: " + ", ".join(CATS) + "。"
        '出力スキーマ: {"title":"...","tags":["...","..."],"category":"..."}'
    )
    body = json.dumps({"model": VL_MODEL, "prompt": prompt, "images": imgs,
                       "stream": False, "format": "json",
                       "options": {"temperature": 0.3}}).encode()
    req = urllib.request.Request(VL_HOST + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=150).read())["response"]
    d = json.loads(out)
    title = str(d.get("title", "")).strip().strip('「」『』"\'#').strip()[:40]
    tags = [str(t).strip().lower().lstrip("#") for t in (d.get("tags") or []) if str(t).strip()]
    tags = [t for t in tags if t][:5]
    cat = str(d.get("category", "")).strip().lower()
    if cat in CATS:
        tags = [cat] + [t for t in tags if t != cat]
    return title, tags[:5]


def main():
    # ★token は X-Admin-Token ヘッダで送る(URL/ログ露出回避)。
    cat = get_json(f"{PLAY}/api/admin/catalog?status=approved",
                   headers={"X-Admin-Token": TOKEN})["items"]
    if ONLY:
        cat = [c for c in cat if c["id"] in ONLY]
    if LIMIT:
        cat = cat[:LIMIT]
    print(f"catalog: {len(cat)} items  (DRY={DRY})", flush=True)
    ok = fail = 0
    for i, it in enumerate(cat):
        t0 = time.time()
        try:
            frames = extract_frames(it["play_cid"], GATEWAY)
            if not frames:
                print(f"[{i}] {it['id']} NO_FRAMES  ({it['title']})", flush=True)
                fail += 1
                continue
            title, tags = caption(frames)
            if not title:
                print(f"[{i}] {it['id']} NO_TITLE", flush=True)
                fail += 1
                continue
            dt = time.time() - t0
            print(f"[{i}] {it['id']} {dt:4.1f}s  '{it['title']}' -> '{title}' {tags}", flush=True)
            if not DRY:
                post_json(f"{PLAY}/api/admin/recaption",
                          {"token": TOKEN, "id": it["id"], "title": title, "tags": tags})
            ok += 1
        except Exception as e:
            print(f"[{i}] {it['id']} ERR {e}", flush=True)
            fail += 1
    print(f"DONE ok={ok} fail={fail}", flush=True)


main()
