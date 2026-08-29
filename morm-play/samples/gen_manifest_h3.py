#!/usr/bin/env python3
"""H3サンプル100本のマニフェスト生成。DGXテキストLLMで各カテゴリの
非アダルト・縦型ショート案(H3プロンプト＋日本語タイトル/説明/タグ)を生成。
出力: manifest_h3.json
"""
import json, os, urllib.request, time

DGX = os.environ.get("TEXT_OLLAMA", "http://100.122.49.105:11434")  # dgx2
MODEL = os.environ.get("TEXT_MODEL", "qwen2.5:32b")
CATS = ["music","dance","art","gaming","vlog","comedy","food","travel","fashion",
        "beauty","tech","education","news","sports","pets","nature","asmr"]
PER = 6  # 17*6=102 → 100に丸め

def gen(cat, n):
    prompt = (
      f"あなたは縦型ショート動画(9:16)の企画ディレクター。カテゴリ『{cat}』の"
      f"3秒程度・非アダルト・安全・視覚的に映える案を{n}件、厳密なJSONのみで出力。"
      "各案は次のキー: "
      '"h3_prompt"(英語1〜2文。縦型フレーミングの鮮明な映像描写＋末尾に "Audio:" で音/音楽。'
      '文字テロップや実在人物の顔は不要。写実的でシネマティック), '
      '"title"(自然な日本語・20字以内・キャッチー), '
      '"description"(自然な日本語1文), '
      '"tags"(英語小文字2〜4個の配列・カテゴリに沿う)。'
      f'出力スキーマ: {{"items":[{{"h3_prompt":"...","title":"...","description":"...","tags":["{cat}"]}}]}}'
    )
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "format": "json", "options": {"temperature": 0.8}}).encode()
    req = urllib.request.Request(DGX + "/api/generate", data=body, headers={"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=120).read())["response"]
    items = json.loads(out).get("items", [])
    res = []
    for it in items[:n]:
        if not it.get("h3_prompt") or not it.get("title"):
            continue
        tags = it.get("tags") or [cat]
        if cat not in tags:
            tags = [cat] + [t for t in tags if t != cat]
        res.append({"category": cat, "h3_prompt": it["h3_prompt"].strip(),
                    "title": it["title"].strip()[:40], "description": (it.get("description") or "").strip()[:200],
                    "tags": [t.lower().strip() for t in tags][:4], "tier": "staked"})
    return res

def main():
    all_items = []
    for cat in CATS:
        for attempt in range(3):
            try:
                r = gen(cat, PER)
                if r:
                    all_items.extend(r)
                    print(f"{cat}: +{len(r)} (total {len(all_items)})", flush=True)
                    break
            except Exception as e:
                print(f"{cat} retry {attempt}: {e}", flush=True)
                time.sleep(2)
    all_items = all_items[:100]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest_h3.json")
    json.dump(all_items, open(out, "w"), ensure_ascii=False, indent=1)
    print(f"\nwrote {len(all_items)} items → {out}")

if __name__ == "__main__":
    main()
