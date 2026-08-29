#!/usr/bin/env python3
"""グリッドチョイス(分岐ストーリー) authoring ヘルパー。
ADMIN_TOKEN は launchd plist から自動取得するので手入力・貼り付け不要。
Mac Mini 上(localhost:8791)で実行する前提。決済台帳には触れない。

使い方:
  story_edge.py find <キーワード>            承認済みコンテンツを題名で検索して cid を出す
  story_edge.py add  <from> <to> [slot] [label] [cost]
                                             分岐エッジを張る/更新 (slot 0=上/1=右/2=下/3=左, cost=pt)
  story_edge.py del  <from> <to>             分岐エッジを削除
  story_edge.py show <cid>                   そのノードの中央+四方の分岐を表示
  story_edge.py ls                           分岐を持つ(=物語の起点になりうる)ノード一覧

例:
  story_edge.py find 滝
  story_edge.py add m0vf8bcfeb4e60f0 m0v5d5acc2df0232 0 "光へ近づく" 0
  story_edge.py show m0vf8bcfeb4e60f0
"""
import sys
import os
import json
import plistlib
import urllib.request
import sqlite3

BASE = os.environ.get("PLAY_BASE", "http://127.0.0.1:8791")
DB = os.environ.get("CATALOG_DB", os.path.expanduser("~/morm-play/play_catalog.db"))
PLIST = os.path.expanduser("~/Library/LaunchAgents/com.morm.play.plist")


def token():
    return plistlib.load(open(PLIST, "rb"))["EnvironmentVariables"]["ADMIN_TOKEN"]


def post(body):
    r = urllib.request.Request(BASE + "/api/admin/story/edge",
                               data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=8).read())


def get(path):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=8).read())


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    cmd = a[0]
    if cmd == "find":
        kw = a[1] if len(a) > 1 else ""
        c = sqlite3.connect(DB)
        rows = c.execute(
            "SELECT id,title,views FROM content WHERE status='approved' AND title LIKE ? "
            "ORDER BY created_at DESC LIMIT 40", (f"%{kw}%",)).fetchall()
        for cid, title, views in rows:
            print(f"{cid}  {title}  (👁{views})")
        if not rows:
            print("(該当なし)")
    elif cmd == "add":
        if len(a) < 3:
            print("usage: add <from> <to> [slot] [label] [cost]")
            return
        frm, to = a[1], a[2]
        slot = int(a[3]) if len(a) > 3 else 0
        label = a[4] if len(a) > 4 else "続きへ"
        cost = int(a[5]) if len(a) > 5 else 0
        d = post({"token": token(), "from": frm, "to": to,
                  "slot": slot, "label": label, "cost": cost})
        print("ok" if d.get("ok") else d)
    elif cmd == "del":
        if len(a) < 3:
            print("usage: del <from> <to>")
            return
        d = post({"token": token(), "from": a[1], "to": a[2], "op": "delete"})
        print("deleted" if d.get("ok") else d)
    elif cmd == "show":
        d = get("/api/story/" + a[1])
        if d.get("error"):
            print(d)
            return
        n = d["node"]
        print(f'[{n["id"]}] {n["title"]}  (分岐 {n.get("story", 0)})')
        for c in d["choices"]:
            print(f'  slot{c["slot"]} "{c["label"]}" cost{c["cost"]} '
                  f'→ [{c["to"]}] {c["target"]["title"]}')
        if d["is_end"]:
            print("  (末端・この先の分岐なし)")
    elif cmd == "ls":
        c = sqlite3.connect(DB)
        rows = c.execute(
            "SELECT e.from_cid, COUNT(*) n, ct.title FROM story_edges e "
            "JOIN content ct ON ct.id=e.from_cid GROUP BY e.from_cid ORDER BY n DESC").fetchall()
        for cid, n, title in rows:
            print(f"{cid}  分岐{n}  {title}")
        if not rows:
            print("(まだ分岐エッジはありません)")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
