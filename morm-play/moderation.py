"""カテゴリ分類 + カテゴリ別判定（最小規制）。play_server と mod_worker で共用。

AI = DGX Ollama（qwen2.5:32b・failover）優先、失敗時ルール。LLM推論はDGXで走る
（Mac Mini禁止・feedback_llm_host_policy）。この関数群はHTTP呼び出しのみ。
"""
import base64
import json
import os
import re
import subprocess
import tempfile
import urllib.request

DGX_HOSTS = [h.strip() for h in os.environ.get(
    "DGX_OLLAMA", "http://100.127.3.16:11434,http://100.122.49.105:11434").split(",") if h.strip()]
MOD_MODEL = os.environ.get("MOD_MODEL", "qwen2.5:32b")
MOD_AI = os.environ.get("MOD_AI", "on") == "on"
# 映像フレーム判定(裏取り)
VL_HOSTS = [h.strip() for h in os.environ.get("VL_OLLAMA", ",".join(DGX_HOSTS)).split(",") if h.strip()]
VL_MODEL = os.environ.get("VL_MODEL", "qwen2.5vl:7b")
FRAME_MOD = os.environ.get("FRAME_MOD", "on") == "on"
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

CATEGORIES = ["music", "dance", "art", "gaming", "vlog", "comedy", "food", "travel",
              "fashion", "beauty", "tech", "education", "news", "sports", "pets",
              "nature", "asmr", "adult", "other"]
# カテゴリ別ポリシー(最小規制): review=ai は低信頼だと必ずレビュー / rating既定。
CAT_POLICY = {
    "adult": {"rating": "r18", "review": "ai"},
    "news": {"rating": "sfw", "review": "ai"},
    "education": {"rating": "sfw", "review": "auto"},
}
_ADULT_KW = ["adult", "r18", "r-18", "18+", "nsfw", "エロ", "アダルト", "hentai",
             "ヌード", "nude", "porn", "セックス", "巨乳", "裸", "lingerie", "ランジェリー",
             "bikini", "ビキニ", "水着", "下着", "グラビア", "cowgirl"]
_SPAM_KW = ["無料配布", "稼げる", "副業", "登録はこちら", "今すぐクリック", "line登録",
            "free money", "click here", "join now", "投資で", "億り人", "配布中", "dm me"]

# 判定閾値(最小規制)
TH = {"csam_risk": 0.5, "nonconsensual": 0.6, "real_violence": 0.7, "illegal": 0.7,
      "spam": 0.7, "scam": 0.7}


def rules_classify(title, desc, tags):
    t = (title + " " + desc + " " + " ".join(tags)).lower()
    cat = "other"
    lower_tags = [x.lower() for x in tags]
    for c in CATEGORIES:
        if c in lower_tags or c in t:
            cat = c
            break
    labels = {k: 0.0 for k in ("illegal", "csam_risk", "real_violence", "scam", "spam", "nonconsensual")}
    if any(k in t for k in _SPAM_KW):
        labels["spam"], labels["scam"] = 0.75, 0.6
    rating = "sfw"
    if any(k in t for k in _ADULT_KW):
        rating = "r18"
        if cat == "other":
            cat = "adult"
    return {"category": cat, "rating": rating, "labels": labels, "model": "rules"}


def classify_via_dgx(title, desc, tags, timeout=25):
    prompt = (
        "あなたは動画SNSのコンテンツ分類器です。方針は『最小規制』＝違法・実在被害"
        "（児童性的搾取/実在の暴力・虐待/詐欺/非同意）とスパムのみを高く評価し、"
        "通常の過激/性的な『表現』は違法ではありません。以下のメタデータを分類し、"
        "厳密なJSONのみを返してください（前後の文章禁止）。\n"
        f"category は次から1つ: {','.join(CATEGORIES)}\n"
        "rating は sfw|r15|r18（成人向け・性的表現は r18）。labels は各0.0-1.0。\n"
        'スキーマ: {"category":"...","rating":"sfw|r15|r18","labels":'
        '{"illegal":0,"csam_risk":0,"real_violence":0,"scam":0,"spam":0,"nonconsensual":0}}\n\n'
        f"title: {title}\ndescription: {desc}\ntags: {', '.join(tags)}\n")
    body = json.dumps({"model": MOD_MODEL, "prompt": prompt, "stream": False,
                       "format": "json", "options": {"temperature": 0}}).encode()
    for base in DGX_HOSTS:
        try:
            req = urllib.request.Request(base + "/api/generate", data=body,
                                         headers={"Content-Type": "application/json"})
            out = json.loads(urllib.request.urlopen(req, timeout=timeout).read())["response"]
            d = json.loads(out)
            cat = d.get("category", "other")
            if cat not in CATEGORIES:
                cat = "other"
            rating = d.get("rating", "sfw")
            if rating not in ("sfw", "r15", "r18"):
                rating = "sfw"
            lb = d.get("labels", {}) or {}
            labels = {k: max(0.0, min(1.0, float(lb.get(k, 0) or 0))) for k in
                      ("illegal", "csam_risk", "real_violence", "scam", "spam", "nonconsensual")}
            return {"category": cat, "rating": rating, "labels": labels, "model": MOD_MODEL}
        except Exception:
            continue
    return None


def classify_and_judge(title, desc, tags, tier):
    """分類→カテゴリ別判定。返り: {status,rating,category,labels,model,reason}。tier=effective_tier(int)。"""
    c = (classify_via_dgx(title, desc, tags) if MOD_AI else None) or rules_classify(title, desc, tags)
    lb = c["labels"]
    pol = CAT_POLICY.get(c["category"], {})
    rating = pol.get("rating", c["rating"])
    if (lb.get("csam_risk", 0) >= TH["csam_risk"] or lb.get("nonconsensual", 0) >= TH["nonconsensual"]
            or lb.get("real_violence", 0) >= TH["real_violence"] or lb.get("illegal", 0) >= TH["illegal"]):
        status, reason = "rejected", "illegal_or_harmful"
    elif lb.get("spam", 0) >= TH["spam"] or lb.get("scam", 0) >= TH["scam"]:
        status, reason = "pending_review", "spam_suspected"
    else:
        status, reason = ("approved" if tier >= 2 else "pending_review"), "ok"
        if pol.get("review") == "ai" and tier < 2:
            status, reason = "pending_review", "category_review"
    return {"status": status, "rating": rating, "category": c["category"],
            "labels": lb, "model": c["model"], "reason": reason}


# --- 映像フレーム判定 (Qwen2.5-VL・裏取り) -----------------------------------

def extract_frames(play_cid, gateway, n=2, timeout=30):
    """gateway の HLS(init+先頭seg)を取得→concat→ffmpegでnフレームJPEG(bytes)を返す。ffmpeg必須。"""
    base = f"{gateway.rstrip('/')}/api/video/{play_cid}"
    master = urllib.request.urlopen(base + "/master.m3u8", timeout=timeout).read().decode()
    variants = re.findall(r"(\d+p)/index\.m3u8", master)
    res = "480p" if "480p" in variants else (variants[len(variants) // 2] if variants else "360p")
    vpl = urllib.request.urlopen(f"{base}/{res}/index.m3u8", timeout=timeout).read().decode()
    im = re.search(r'EXT-X-MAP:URI="([^"]+)"', vpl)
    init_name = im.group(1).rsplit("/", 1)[-1] if im else None
    sm = re.search(r'([^/\s"]+\.m4s)', vpl)
    seg_name = sm.group(1) if sm else None
    if not init_name or not seg_name:
        return []
    init_b = urllib.request.urlopen(f"{base}/{res}/{init_name}", timeout=timeout).read()
    seg_b = urllib.request.urlopen(f"{base}/{res}/{seg_name}", timeout=timeout).read()
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "clip.mp4")
        with open(src, "wb") as f:
            f.write(init_b + seg_b)
        out = os.path.join(d, "f_%02d.jpg")
        subprocess.run([FFMPEG, "-y", "-i", src, "-vf", "scale=512:-1,fps=1",
                        "-frames:v", str(n), out], capture_output=True, timeout=timeout)
        frames = []
        for i in range(1, n + 1):
            p = os.path.join(d, f"f_{i:02d}.jpg")
            if os.path.exists(p):
                frames.append(open(p, "rb").read())
        return frames


def analyze_frames(frames_bytes, timeout=60):
    """VL(qwen2.5vl)に画像を渡し安全ラベルを返す。(labels, model) or (None, None)。"""
    if not frames_bytes:
        return None, None
    imgs = [base64.b64encode(b).decode() for b in frames_bytes]
    prompt = ("あなたはコンテンツ安全分類器です。画像を分析し厳密なJSONのみ返す(前後の文禁止)。"
              "方針=最小規制: 性的/成人向けは違法ではないが rating を上げる対象。児童・実在の暴力/被害のみ厳格に。"
              'スキーマ: {"adult":0.0-1.0,"nudity":0.0-1.0,"csam_risk":0.0-1.0,'
              '"real_violence":0.0-1.0,"gore":0.0-1.0}')
    body = json.dumps({"model": VL_MODEL, "prompt": prompt, "images": imgs, "stream": False,
                       "format": "json", "options": {"temperature": 0}}).encode()
    for host in VL_HOSTS:
        try:
            req = urllib.request.Request(host + "/api/generate", data=body,
                                         headers={"Content-Type": "application/json"})
            out = json.loads(urllib.request.urlopen(req, timeout=timeout).read())["response"]
            d = json.loads(out)
            labels = {k: max(0.0, min(1.0, float(d.get(k, 0) or 0)))
                      for k in ("adult", "nudity", "csam_risk", "real_violence", "gore")}
            return labels, VL_MODEL
        except Exception:
            continue
    return None, None


def moderate(title, desc, tags, tier, play_cid=None, gateway=None):
    """テキスト判定 + 映像フレーム判定(裏取り)を統合。フレームは severity を上げる方向のみ。"""
    v = classify_and_judge(title, desc, tags, tier)
    if not (FRAME_MOD and play_cid and gateway):
        return v
    try:
        frames = extract_frames(play_cid, gateway)
        fl, vlmodel = analyze_frames(frames)
    except Exception:
        fl, vlmodel = None, None
    if not fl:
        return v
    v["frame_labels"] = fl
    v["model"] = f"{v['model']}+{vlmodel}"
    lb = v["labels"]
    # 危害ラベルは text/frame の max(裏取り=厳しい方を採用)
    lb["csam_risk"] = max(lb.get("csam_risk", 0), fl.get("csam_risk", 0))
    lb["real_violence"] = max(lb.get("real_violence", 0), fl.get("real_violence", 0), fl.get("gore", 0))
    lb["adult"] = fl.get("adult", 0)      # 映像の成人度(監査/表示用)
    lb["nudity"] = fl.get("nudity", 0)
    # 映像に成人表現 → rating を r18 へ引き上げ(裏取り)
    if fl.get("adult", 0) >= 0.5 or fl.get("nudity", 0) >= 0.5:
        v["rating"] = "r18"
    # 統合ラベルで再判定(severity上げのみ)
    if lb["csam_risk"] >= TH["csam_risk"] or lb["real_violence"] >= TH["real_violence"]:
        v["status"] = "rejected"
        v["reason"] = "frame_" + ("csam" if lb["csam_risk"] >= TH["csam_risk"] else "violence")
    elif v["rating"] == "r18" and tier < 2 and v["status"] == "approved":
        v["status"], v["reason"] = "pending_review", "frame_adult_review"
    return v
