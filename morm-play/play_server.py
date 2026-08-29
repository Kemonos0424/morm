#!/usr/bin/env python3
"""MORM Play — 動画ディスカバリ + 配信元(node)秘匿プロキシ (stdlib only).

play.morm.one のフロント。3つの責務を1プロセスに束ねる:

  1) カタログ (SQLite): メディアメタ(title/tags/uploader/likes/views/created_at)
     と推薦ランキング(人気×時間減衰)、検索、いいね。
  2) ★秘匿プロキシ /m/<id>/... : 住宅edge(edge-mcXXXX.ctai.online)から
     HLSをサーバ側で取得し、プレイリスト内の全URLを /m/<id>/ 相対へ書換、
     ノード識別ヘッダ(x-morm-edge等)を除去。クライアントには play.morm.one
     しか見えず、edgeのホスト/IP/実content-hashを一切露出しない。
  3) フロント: Pinterest風 masonry グリッド + 検索 + モーダルプレイヤー
     + いいね/シェア。ブランド=Vivid90s。

環境変数:
  PLAY_PORT     listen port (default 8791)
  CATALOG_DB    SQLite path (default ./play_catalog.db)
  EDGES         カンマ区切り候補edge (default DEFAULT_EDGES)
  PROBE_EVERY   ヘルス間隔秒 (default 30)
  ADMIN_TOKEN   /api/admin/* 用トークン (未設定なら admin API 無効)
"""
import base64
import hashlib
import hmac
import html
import json
import os
import random
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mormcrypto import ed25519_pubkey, ed25519_sign, ed25519_verify, m0r_address

GATEWAY = os.environ.get("GATEWAY", "http://100.80.207.111:8801")  # hpmini HLS encoder

# --- MORM 報酬レート(1 MORM=$0.01・env で調整可) ---
VIEW_RATE = float(os.environ.get("VIEW_RATE", "0.002"))   # MORM / 再生
LIKE_RATE = float(os.environ.get("LIKE_RATE", "0.05"))    # MORM / いいね
# 実配分(L1直送金)
MORM_L1_RPC = os.environ.get("MORM_L1_RPC", "http://127.0.0.1:8900")
TREASURY_SEED_FILE = os.environ.get("TREASURY_SEED_FILE", os.path.expanduser("~/.morm-l1/producer.seed"))
PAYOUT_MIN = int(os.environ.get("PAYOUT_MIN", "1"))       # この額(MORM整数)以上で配分

# --- エンゲージ報酬ポイント(いいね/コメント/シェア → 72h毎に集計しMORMをウォレットへ) ---
# 反farm: (口座,種別,コンテンツ)ごと恒久1回・自分の作品は対象外・approvedのみ・署名必須・72h窓上限。
POINT_VALUES = {"like": int(os.environ.get("PT_LIKE", "1")),
                "comment": int(os.environ.get("PT_COMMENT", "2")),
                "share": int(os.environ.get("PT_SHARE", "1")),
                "view": int(os.environ.get("PT_VIEW", "1"))}   # 他者の有効再生→クリエイターへ
# view_by_other 報酬(署名付き視聴のみ)。既定off=従来と完全同一(未署名視聴はview計数のみ・無報酬)。
VIEW_EARN = os.environ.get("VIEW_EARN", "off")
POINT_PER_MORM = int(os.environ.get("PT_PER_MORM", "5"))        # このポイントで 1 MORM
POINT_MIN_SETTLE = int(os.environ.get("PT_MIN_SETTLE", "5"))    # プール未満は次回へ繰越
POINT_WINDOW_SEC = int(os.environ.get("PT_WINDOW_SEC", str(72 * 3600)))   # 72h(獲得上限の窓)
POINT_72H_CAP = int(os.environ.get("PT_72H_CAP", "100"))        # 72h窓あたりの獲得上限(反farm)
POINT_SETTLE_INTERVAL = int(os.environ.get("PT_SETTLE_INTERVAL", str(72 * 3600)))  # 集計・配分の周期
POINT_TICK_SEC = int(os.environ.get("PT_TICK_SEC", "1800"))     # 集計デーモンのチェック間隔
# --- Phase 2: 予算上限つき比例配分(固定レートの代替) ------------------------
# EMISSION_MODE=fixed(既定=従来: points//POINT_PER_MORM の固定レート)
#             =proportional(Payout_i = B_EPOCH × P_i / ΣP。総発行B固定=参加者増でも暴走なし)
# 配分は base units(=L1整数)で計算。l1_transfer は amount を生のL1整数として送るため、
# BASE=1e6(µMORM)なら sub-MORM 配分も可能。既定 BASE=1/mode=fixed で現行と完全同一(非破壊)。
EMISSION_MODE = os.environ.get("EMISSION_MODE", "fixed")                       # fixed | proportional
MORM_BASE_UNITS_PER_MORM = int(os.environ.get("MORM_BASE_UNITS_PER_MORM", "1"))# dashboardと一致させる
B_EPOCH_MORM = float(os.environ.get("B_EPOCH_MORM", "5000"))                   # 1エポックの発行予算(MORM)
# エンゲージ・トラックの取り分(B_day の何割か)。node は dashboard 側 SPLIT_NODE を使う。
# 本番では SPLIT_ENGAGE + SPLIT_NODE (+ reserve) <= 1 に設定して二重発行を防ぐ。
# 既定 1.0 = 従来どおり engagement が B 全額(後方互換・単体検証用)。
SPLIT_ENGAGE = float(os.environ.get("SPLIT_ENGAGE", "1.0"))
EPOCH_ACCT_CAP_FRAC = float(os.environ.get("EPOCH_ACCT_CAP_FRAC", "0.005"))    # 単一口座上限=予算の0.5%

# --- 投稿動画スペック ---
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(512 * 1024 * 1024)))  # ハード上限
MIN_DURATION = 1.0            # これ未満/壊れは弾く
DUR_TOLERANCE = 1.5          # 実尺 tier判定の許容(秒)
# 入力=一般的な動画コンテナ(mp4/mov/webm/m4v/mkv/avi 等)。gatewayが ffmpeg で
# アダプティブHLS(1080/720/480/360・H.264/AAC・~3sセグ)へ自動変換=正規化。

# カテゴリ判定は moderation.py に集約し、非同期 mod_worker が実行する。
from moderation import CATEGORIES as _CATS  # noqa: E402 (queue表示でカテゴリ判定に使用)

PORT = int(os.environ.get("PLAY_PORT", "8791"))
CATALOG_DB = os.environ.get("CATALOG_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "play_catalog.db"))
PROBE_EVERY = int(os.environ.get("PROBE_EVERY", "30"))
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
DEMO_CID = os.environ.get("DEMO_CID", "78bb0540b0b8775f")  # 唯一の実再生可能テスト動画

DEFAULT_EDGES = ",".join(f"edge-mc{n}.ctai.online" for n in
    ["1000", "1001", "1003", "1004", "1006", "1014", "1015", "1016", "1018", "1019",
     "1021", "1023", "1024", "1043", "1045", "1061", "1062"])
EDGES = [e.strip() for e in os.environ.get("EDGES", DEFAULT_EDGES).split(",") if e.strip()]

# 住宅edgeが全滅しても配信を止めないための最終手段。CDN前段の公開originを直接引く。
# 空文字にすると無効化できる。
ORIGIN_FALLBACK = os.environ.get("ORIGIN_FALLBACK", "video.ctai.online").strip()

_state = {"healthy": list(EDGES), "updated": 0}
_lock = threading.Lock()

# --- 整合性/bot対策 (再生・いいねは報酬直結ゆえ水増しを防ぐ) --------------------
# 有効再生の閾値: この秒数 or 割合を満たした視聴のみ views に計上。
VIEW_MIN_SEC = float(os.environ.get("VIEW_MIN_SEC", "2.0"))
VIEW_MIN_FRAC = float(os.environ.get("VIEW_MIN_FRAC", "0.3"))
WATCH_DEDUP_TTL = int(os.environ.get("WATCH_DEDUP_TTL", "21600"))  # 6h: 同一視聴者×作品は窓内1回のみ計上
WATCH_IP_PER_MIN = int(os.environ.get("WATCH_IP_PER_MIN", "240"))   # 反フラッド backstop(主防御はdedup+閾値)
VIEW_IP_PER_MIN = int(os.environ.get("VIEW_IP_PER_MIN", "60"))
LIKE_IP_PER_MIN = int(os.environ.get("LIKE_IP_PER_MIN", "40"))
FOLLOW_IP_PER_MIN = int(os.environ.get("FOLLOW_IP_PER_MIN", "40"))
COMMENT_IP_PER_MIN = int(os.environ.get("COMMENT_IP_PER_MIN", "15"))
_INTEG_MAX = 200000                       # ★上限(破棄と同時に設定。TTLリーク防止)
_integ_lock = threading.Lock()
_seen_watch = OrderedDict()               # (cid,viewer) -> ts : watch_sec累積dedup
_seen_view = OrderedDict()                # (cid,viewer) -> ts : 有効再生(views)dedup
_rl_hits = OrderedDict()                  # bucket -> deque[ts] : レート制限
_IP_SALT = os.urandom(16)                 # 生IPは保存しない(プロセス内ソルトでハッシュ)


def _ip_hash(ip):
    if not ip:
        return ""
    return hmac.new(_IP_SALT, ip.encode(), hashlib.sha256).hexdigest()[:16]


def _rl_allow(key, limit, window=60):
    """key につき window 秒あたり limit 回まで許可。超過で False。"""
    now = time.time()
    with _integ_lock:
        dq = _rl_hits.get(key)
        if dq is None:
            dq = deque()
            _rl_hits[key] = dq
            if len(_rl_hits) > _INTEG_MAX:
                _rl_hits.popitem(last=False)
        while dq and dq[0] < now - window:
            dq.popleft()
        _rl_hits.move_to_end(key)
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


def _dedup_first(store, key, ttl):
    """key が ttl 窓内で初出なら True(計上可)、既出なら False。"""
    now = time.time()
    with _integ_lock:
        t = store.get(key)
        if t is not None and now - t < ttl:
            store.move_to_end(key)
            return False
        store[key] = now
        store.move_to_end(key)
        if len(store) > _INTEG_MAX:
            store.popitem(last=False)
        return True

# --- edge health (picker と同等・内部専用。外部には edge ホストを出さない) -----

def _probe_one(host, cid):
    url = f"https://{host}/api/video/{cid}/master.m3u8"
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "morm-play/1.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.status == 200
    except Exception:
        return False


def _health_loop():
    while True:
        healthy = [h for h in EDGES if _probe_one(h, DEMO_CID)]
        with _lock:
            # ★実測値をそのまま持つ。以前は全滅時に list(EDGES) へフェイルオープンして
            #   いたため、全edgeが落ちても /health が「17台healthy」と報告し続け、
            #   死んだedgeに振り続けて502になった(2026-08-15の障害)。
            #   全滅時は空のまま持ち、取得は ORIGIN_FALLBACK が引き受ける。
            _state["healthy"] = healthy
            _state["updated"] = int(time.time())
        time.sleep(PROBE_EVERY)


def _pick_edge():
    with _lock:
        pool = list(_state["healthy"]) or list(EDGES)
    return random.choice(pool)  # noqa: S311 振り分けに暗号強度不要

# --- catalog DB --------------------------------------------------------------

_TAG_POOL = [
    "shorts", "music", "dance", "art", "anime", "vlog", "gaming",
    "fashion", "food", "travel", "comedy", "tech", "nature", "sports",
    "asmr", "diy", "beauty", "pets",
]
_DEMO_TITLES = [
    ("ネオン東京 深夜ドライブ", "music,travel,shorts"),
    ("Generative Bloom #04", "art,tech"),
    ("渋谷 ストリートダンス", "dance,fashion,shorts"),
    ("Lo-fi study loop", "music,asmr"),
    ("猫と過ごす日曜日", "pets,vlog"),
    ("90s Vaporwave Cut", "art,music"),
    ("Ramen making ASMR", "food,asmr"),
    ("Mountain sunrise 4K", "nature,travel"),
    ("Speedrun any% WR", "gaming,sports"),
    ("Thrift haul 2026", "fashion,diy"),
    ("DIY ネオンサイン", "diy,art,tech"),
    ("Midnight skate line", "sports,shorts"),
    ("Coffee pour close-up", "food,asmr"),
    ("Retro synth jam", "music,tech"),
    ("桜 timelapse", "nature,art"),
    ("Cyber makeup look", "beauty,fashion"),
]
_ARS = ["portrait", "portrait", "portrait", "square", "landscape"]  # ショート主体


def _db():
    conn = sqlite3.connect(CATALOG_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS content(
          id TEXT PRIMARY KEY,
          play_cid TEXT NOT NULL,
          title TEXT NOT NULL,
          tags TEXT NOT NULL DEFAULT '',
          uploader TEXT NOT NULL DEFAULT '',
          created_at INTEGER NOT NULL,
          views INTEGER NOT NULL DEFAULT 0,
          likes INTEGER NOT NULL DEFAULT 0,
          hue INTEGER NOT NULL DEFAULT 0,
          ar TEXT NOT NULL DEFAULT 'portrait'
        );
        CREATE TABLE IF NOT EXISTS likes(
          id TEXT NOT NULL,
          account TEXT NOT NULL,
          sig TEXT,
          ts INTEGER NOT NULL,
          PRIMARY KEY(id, account)
        );
        CREATE INDEX IF NOT EXISTS idx_content_created ON content(created_at DESC);
        CREATE TABLE IF NOT EXISTS accounts(
          m0r TEXT PRIMARY KEY, created_at INTEGER, trust_score INTEGER DEFAULT 0,
          verified INTEGER DEFAULT 0, staked_morm INTEGER DEFAULT 0,
          strikes INTEGER DEFAULT 0, status TEXT DEFAULT 'active'
        );
        CREATE TABLE IF NOT EXISTS moderation_log(
          id INTEGER PRIMARY KEY AUTOINCREMENT, target_type TEXT, target_id TEXT,
          model TEXT, score REAL, labels TEXT, decision TEXT, reviewer TEXT, ts INTEGER
        );
        CREATE TABLE IF NOT EXISTS comments(
          id INTEGER PRIMARY KEY AUTOINCREMENT, content_id TEXT, account TEXT, text TEXT, ts INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_comments_c ON comments(content_id, ts DESC);
        CREATE TABLE IF NOT EXISTS payouts(
          account TEXT PRIMARY KEY, paid_morm INTEGER DEFAULT 0, last_tx TEXT, updated INTEGER
        );
        CREATE TABLE IF NOT EXISTS covers(
          content_id TEXT PRIMARY KEY, jpg BLOB, ts REAL, updated INTEGER
        );
        CREATE TABLE IF NOT EXISTS follows(
          follower TEXT NOT NULL, followee TEXT NOT NULL, ts INTEGER NOT NULL,
          PRIMARY KEY(follower, followee)
        );
        CREATE INDEX IF NOT EXISTS idx_follows_followee ON follows(followee);
        CREATE INDEX IF NOT EXISTS idx_follows_follower ON follows(follower);
        CREATE TABLE IF NOT EXISTS referrals(
          referee TEXT PRIMARY KEY, referrer TEXT NOT NULL, created_at INTEGER,
          qualified INTEGER DEFAULT 0, qualified_at INTEGER DEFAULT 0,
          rewarded INTEGER DEFAULT 0, rewarded_at INTEGER DEFAULT 0,
          reward_tx_referee TEXT, reward_tx_referrer TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_ref_referrer ON referrals(referrer);
        CREATE TABLE IF NOT EXISTS challenges(
          slug TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '',
          creator TEXT NOT NULL, created_at INTEGER NOT NULL, ends_at INTEGER DEFAULT 0,
          reward_pool INTEGER DEFAULT 0, status TEXT DEFAULT 'active', settled INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS challenge_awards(
          slug TEXT NOT NULL, m0r TEXT NOT NULL, rank INTEGER, amount INTEGER,
          tx TEXT, ts INTEGER, PRIMARY KEY(slug, m0r)
        );
        -- グリッドチョイス: ノード=既存 content 行、分岐(展開違い)=エッジ。
        -- from_cid の中央ノードから to_cid の続きへ。slot=四方の位置(0N/1E/2S/3W)。
        -- cost=続き解放の対価(初版は 0=無料。将来ポイント/実MORM課金の器)。
        CREATE TABLE IF NOT EXISTS story_edges(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          from_cid TEXT NOT NULL,
          to_cid TEXT NOT NULL,
          slot INTEGER NOT NULL DEFAULT 0,
          label TEXT NOT NULL DEFAULT '',
          cost INTEGER NOT NULL DEFAULT 0,
          created_at INTEGER NOT NULL DEFAULT 0,
          UNIQUE(from_cid, to_cid)
        );
        CREATE INDEX IF NOT EXISTS idx_story_from ON story_edges(from_cid);
        CREATE INDEX IF NOT EXISTS idx_story_to ON story_edges(to_cid);
        -- エンゲージ報酬ポイント台帳(append-only)。(account,kind,content_id)一意=恒久1回。
        CREATE TABLE IF NOT EXISTS point_ledger(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          account TEXT NOT NULL, kind TEXT NOT NULL, content_id TEXT NOT NULL,
          points INTEGER NOT NULL, ts INTEGER NOT NULL, settled INTEGER NOT NULL DEFAULT 0,
          UNIQUE(account, kind, content_id)
        );
        CREATE INDEX IF NOT EXISTS idx_point_acct ON point_ledger(account, settled);
        CREATE INDEX IF NOT EXISTS idx_point_ts ON point_ledger(account, ts);
        -- ポイント配分の冪等台帳(既存 payouts と同型)+端数繰越。
        CREATE TABLE IF NOT EXISTS point_payouts(
          account TEXT PRIMARY KEY, paid_points INTEGER DEFAULT 0, paid_morm INTEGER DEFAULT 0,
          carry_points INTEGER DEFAULT 0, last_tx TEXT, updated INTEGER
        );
        -- 集計実行ログ(72h周期の判定に MAX(ts) を使う)。
        CREATE TABLE IF NOT EXISTS point_settle_runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, accounts INTEGER, morm INTEGER
        );
        """
    )
    # --- P1 migration: content に投稿系の列を後付け ---
    have = {r[1] for r in conn.execute("PRAGMA table_info(content)").fetchall()}
    for col, ddl in [
        ("description", "TEXT DEFAULT ''"), ("status", "TEXT DEFAULT 'approved'"),
        ("links", "TEXT DEFAULT '[]'"), ("rating", "TEXT DEFAULT 'sfw'"),
        ("mod_score", "REAL DEFAULT 0"), ("mod_labels", "TEXT DEFAULT '{}'"),
        ("duration", "REAL DEFAULT 0"), ("upload_token", "TEXT DEFAULT ''"),
        ("comments", "INTEGER DEFAULT 0"), ("cover_ts", "REAL DEFAULT 0"),
        ("watch_sec", "REAL DEFAULT 0"), ("completions", "INTEGER DEFAULT 0"),
        ("remix_of", "TEXT DEFAULT ''"), ("challenge", "TEXT DEFAULT ''"),
    ]:
        if col not in have:
            conn.execute(f"ALTER TABLE content ADD COLUMN {col} {ddl}")
    conn.execute("UPDATE content SET status='approved' WHERE status IS NULL OR status=''")
    # accounts: 年齢認証カラム
    have_acc = {r[1] for r in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    for col, ddl in [("age_verified", "INTEGER DEFAULT 0"),
                     ("age_method", "TEXT DEFAULT ''"), ("birth_year", "INTEGER DEFAULT 0"),
                     ("display_name", "TEXT DEFAULT ''"), ("bio", "TEXT DEFAULT ''"),
                     ("ref_code", "TEXT DEFAULT ''")]:
        if col not in have_acc:
            conn.execute(f"ALTER TABLE accounts ADD COLUMN {col} {ddl}")
    # remix_of/challenge 列が揃ってから index を作成(既存DBでも安全)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_content_challenge ON content(challenge)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_content_remix ON content(remix_of)")
    conn.commit()
    # seed demo catalog (全item は実再生のため play_cid=DEMO_CID を指す)
    n = conn.execute("SELECT COUNT(*) FROM content").fetchone()[0]
    if n == 0:
        now = int(time.time())
        rng = random.Random(90)
        for i, (title, tags) in enumerate(_DEMO_TITLES):
            cid = "m0v" + hashlib.sha1(f"{title}{i}".encode()).hexdigest()[:13]
            age_h = rng.randint(1, 240)
            conn.execute(
                "INSERT INTO content(id,play_cid,title,tags,uploader,created_at,views,likes,hue,ar)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (cid, DEMO_CID, title, tags,
                 "m0r" + hashlib.sha1(f"u{i}".encode()).hexdigest()[:10],
                 now - age_h * 3600,
                 rng.randint(120, 48000), rng.randint(3, 2100),
                 rng.randint(0, 359), _ARS[i % len(_ARS)]),
            )
        conn.commit()
    conn.close()


def _row_public(r, liked=False):
    return {
        "id": r["id"], "title": r["title"],
        "tags": [t for t in r["tags"].split(",") if t],
        "uploader": r["uploader"], "views": r["views"], "likes": r["likes"],
        "created_at": r["created_at"], "hue": r["hue"], "ar": r["ar"],
        "thumb": f"/thumb/{r['id']}.svg", "liked": liked,
        "rating": r["rating"] if "rating" in r.keys() else "sfw",
        "comments": r["comments"] if "comments" in r.keys() else 0,
        "cover": (f"/cover/{r['id']}.jpg" if ("cover_ts" in r.keys() and r["cover_ts"]) else None),
        "remix_of": (r["remix_of"] if "remix_of" in r.keys() else "") or "",
        "challenge": (r["challenge"] if "challenge" in r.keys() else "") or "",
    }


COLD_MIN = int(os.environ.get("FYP_COLD_MIN", "25"))   # この視聴数未満=コールドスタート(探索枠)


def _col(r, k, d=0):
    return r[k] if (k in r.keys() and r[k] is not None) else d


def _fyp_score(r, now, affinity=None):
    """TikTok型FYP: 人気×(視聴維持率+エンゲージ質)×鮮度 + コールドスタート探索 + velocity + 興味一致。"""
    V = max(0, _col(r, "views"))
    L = max(0, _col(r, "likes"))
    C = max(0, _col(r, "comments"))
    W = max(0.0, _col(r, "watch_sec", 0.0))
    Cp = max(0, _col(r, "completions"))
    D = max(1.0, _col(r, "duration", 3.0))
    age_h = max(0.0, (now - r["created_at"]) / 3600.0)
    # 視聴維持率(信号不足は中立prior 0.5)
    retention = min(1.0, W / (V * D)) if V >= 5 else 0.5
    # 1視聴あたりエンゲージ質
    eng = min(1.5, (L * 1.0 + C * 1.6 + Cp * 0.6) / max(V, 1))
    quality = 0.6 * retention + 0.4 * min(1.0, eng)          # 0..1
    import math
    popularity = math.log1p(L * 3 + V * 0.1 + C * 2)
    freshness = 1.0 / ((age_h + 2.0) ** 0.6)
    velocity = min(6.0, (L + Cp * 2) / (age_h + 1.0))
    cold = 2.2 * (1.0 - V / COLD_MIN) if V < COLD_MIN else 0.0  # 新作に試し配信枠
    score = (popularity * (0.5 + quality) + 0.3 * velocity + cold) * freshness
    if affinity:  # 軽いパーソナライズ: 視聴者の好むタグと一致で加点
        tg = [t for t in r["tags"].split(",") if t]
        boost = sum(affinity.get(t, 0) for t in tg)
        score *= (1.0 + min(0.8, boost))
    return score


def viewer_tag_affinity(m0r):
    """視聴者が『いいね』した作品のタグから興味ベクトル(タグ→重み)。"""
    if not m0r:
        return None
    conn = _db()
    rows = conn.execute(
        "SELECT c.tags FROM likes l JOIN content c ON c.id=l.id WHERE l.account=? ORDER BY l.ts DESC LIMIT 60",
        (m0r,)).fetchall()
    conn.close()
    aff = {}
    for r in rows:
        for t in r["tags"].split(","):
            if t:
                aff[t] = aff.get(t, 0) + 0.12
    return aff or None


def feed(sort="hot", q="", tag="", limit=24, offset=0, zone="sfw", uid="", follow_of=""):
    conn = _db()
    rows = conn.execute("SELECT * FROM content").fetchall()
    conn.close()
    now = time.time()
    items = []
    ql = q.lower().strip()
    fset = following_set(follow_of) if follow_of else None
    for r in rows:
        if r["status"] != "approved":  # pending/reserved/rejected は公開feedに出さない
            continue
        if fset is not None and r["uploader"] not in fset:  # フォロー中フィード
            continue
        is_adult = (r["rating"] == "r18")
        if zone == "adult":
            if not is_adult:
                continue
        elif is_adult:  # おすすめ(既定)には R18 を載せない
            continue
        if ql and ql not in r["title"].lower() and ql not in r["tags"].lower():
            continue
        if tag and tag not in (r["tags"].split(",")):
            continue
        items.append(r)
    if sort == "new":
        items.sort(key=lambda r: r["created_at"], reverse=True)
    else:  # fyp (おすすめ)
        aff = viewer_tag_affinity(uid) if uid and not uid.startswith("m0rplay") else None
        items.sort(key=lambda r: _fyp_score(r, now, aff), reverse=True)
    # 重複コンテンツ是正: 同一タイトル(正規化)は最良1本だけ表示(既にスコア/新着順ゆえ先勝ち)。
    # 別実体でも同名が並ぶと重複に見えるため、閲覧フィードでは畳む(DBは保持=非破壊)。
    _seen_titles, _deduped = set(), []
    for r in items:
        k = (r["title"] or "").strip().lower()
        if k and k in _seen_titles:
            continue
        _seen_titles.add(k)
        _deduped.append(r)
    items = _deduped
    total = len(items)
    page = items[offset:offset + limit]
    pub = _attach_meta(_attach_names([_row_public(r) for r in page]))
    vf = following_set(uid) if (uid and uid.startswith("m0r")) else set()
    for it in pub:
        it["following"] = it["uploader"] in vf
        it["is_self"] = bool(uid and it["uploader"] == uid)
    return {"items": pub,
            "total": total, "next": (offset + limit) if offset + limit < total else None}


def record_watch(cid, watched, completed, viewer="", ip_hash="", viewer_verified=False):
    """視聴ビーコン。★同一視聴者×作品は窓内1回のみ計上(pump防止)、閾値超えのみ有効再生としてviews加算。
    viewer_verified=True(署名付き視聴)かつ VIEW_EARN=on のとき、新規有効再生でクリエイターへ視聴ポイント付与。"""
    vk = (viewer or "").strip() or ("ip:" + ip_hash if ip_hash else "anon")
    if not _rl_allow("w:" + vk, WATCH_IP_PER_MIN):                       # per視聴者(常に端末単位)
        return {"ok": True, "rl": True}
    if ip_hash and not _rl_allow("wip:" + ip_hash, WATCH_IP_PER_MIN * 6):  # IP backstop(有効時)
        return {"ok": True, "rl": True}
    conn = _db()
    r = conn.execute("SELECT duration FROM content WHERE id=? AND status='approved'", (cid,)).fetchone()
    if not r:
        conn.close()
        return {"ok": False}
    d = max(1.0, r["duration"] or 3.0)
    conn.close()
    w = max(0.0, min(float(watched or 0), d * 1.5))  # バッファ先読み等の過大値を抑制
    qualified = (w >= VIEW_MIN_SEC) or (d > 0 and w / d >= VIEW_MIN_FRAC)  # 有効再生(閾値)
    acc = _dedup_first(_seen_watch, (cid, vk), WATCH_DEDUP_TTL)            # watch_sec累積は視聴者1回
    view = (qualified and _dedup_first(_seen_view, (cid, vk), WATCH_DEDUP_TTL)
            and _rl_allow("v:" + vk, VIEW_IP_PER_MIN))                     # 有効再生も視聴者1回
    if not acc and not view:
        return {"ok": True, "dup": True}
    conn = _db()
    if acc:
        conn.execute("UPDATE content SET watch_sec=watch_sec+?, completions=completions+? WHERE id=?",
                     (w, 1 if completed else 0, cid))
    if view:
        conn.execute("UPDATE content SET views=views+1 WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    # view_by_other: 新規の有効再生かつ署名付き視聴のみ、作品のクリエイターへ視聴ポイント。
    awarded = 0
    if view and viewer_verified:
        awarded = grant_view_point(cid, viewer)
    return {"ok": True, "qualified": bool(qualified), "counted": bool(view),
            "creator_awarded": awarded}


def popular_tags(k=12):
    conn = _db()
    rows = conn.execute("SELECT tags FROM content").fetchall()
    conn.close()
    counts = {}
    for r in rows:
        for t in r["tags"].split(","):
            if t:
                counts[t] = counts.get(t, 0) + 1
    return [t for t, _ in sorted(counts.items(), key=lambda x: -x[1])[:k]]


def toggle_like(cid, account, sig=None):
    conn = _db()
    row = conn.execute("SELECT likes FROM content WHERE id=?", (cid,)).fetchone()
    if not row:
        conn.close()
        return None
    exists = conn.execute("SELECT 1 FROM likes WHERE id=? AND account=?", (cid, account)).fetchone()
    if exists:
        conn.execute("DELETE FROM likes WHERE id=? AND account=?", (cid, account))
        conn.execute("UPDATE content SET likes=MAX(0,likes-1) WHERE id=?", (cid,))
        liked = False
    else:
        conn.execute("INSERT OR IGNORE INTO likes(id,account,sig,ts) VALUES(?,?,?,?)",
                     (cid, account, sig, int(time.time())))
        conn.execute("UPDATE content SET likes=likes+1 WHERE id=?", (cid,))
        liked = True
    conn.commit()
    likes = conn.execute("SELECT likes FROM content WHERE id=?", (cid,)).fetchone()[0]
    conn.close()
    return {"likes": likes, "liked": liked}


def bump_view(cid):
    conn = _db()
    conn.execute("UPDATE content SET views=views+1 WHERE id=?", (cid,))
    conn.commit()
    conn.close()


def get_content(cid, account=None):
    conn = _db()
    r = conn.execute("SELECT * FROM content WHERE id=?", (cid,)).fetchone()
    liked = False
    if r and account:
        liked = bool(conn.execute("SELECT 1 FROM likes WHERE id=? AND account=?", (cid, account)).fetchone())
    conn.close()
    if not r:
        return None
    d = _row_public(r, liked)
    d["uname"] = display_name(r["uploader"])
    _attach_meta([d])   # remix_count / 親title / challenge_title
    if account and account.startswith("m0r"):
        d["following"] = is_following(account, r["uploader"])
        d["is_self"] = (account == r["uploader"])
    else:
        d["following"] = False
        d["is_self"] = False
    return d


_URL_IN_TEXT = re.compile(r"https?://|www\.", re.I)


def add_comment(cid, account, text):
    text = (text or "").strip()[:300]
    if not text:
        return {"error": "空です"}
    if len(_URL_IN_TEXT.findall(text)) > 1:
        return {"error": "リンクが多すぎます"}
    conn = _db()
    if not conn.execute("SELECT 1 FROM content WHERE id=? AND status='approved'", (cid,)).fetchone():
        conn.close()
        return {"error": "not found"}
    last = conn.execute("SELECT ts FROM comments WHERE account=? ORDER BY ts DESC LIMIT 1", (account,)).fetchone()
    if last and time.time() - last["ts"] < 8:  # 簡易スパム抑制(連投)
        conn.close()
        return {"error": "少し待ってから投稿してください"}
    conn.execute("INSERT INTO comments(content_id,account,text,ts) VALUES(?,?,?,?)",
                 (cid, account, text, int(time.time())))
    conn.execute("UPDATE content SET comments=comments+1 WHERE id=?", (cid,))
    conn.commit()
    n = conn.execute("SELECT comments FROM content WHERE id=?", (cid,)).fetchone()[0]
    conn.close()
    return {"ok": True, "comments": n, "text": text, "ts": int(time.time())}


def list_comments(cid, limit=60):
    conn = _db()
    rows = conn.execute("SELECT account,text,ts FROM comments WHERE content_id=? ORDER BY ts DESC LIMIT ?",
                        (cid, limit)).fetchall()
    conn.close()
    return [{"account": r["account"], "text": r["text"], "ts": r["ts"]} for r in rows]


def earnings(m0r):
    """作品の再生数×VIEW_RATE + いいね数×LIKE_RATE = 獲得MORM(整数)。paid/pending も返す。"""
    conn = _db()
    rows = conn.execute("SELECT views,likes FROM content WHERE uploader=? AND status='approved'", (m0r,)).fetchall()
    p = conn.execute("SELECT paid_morm FROM payouts WHERE account=?", (m0r,)).fetchone()
    conn.close()
    v = sum(r["views"] for r in rows)
    lk = sum(r["likes"] for r in rows)
    earned = int(v * VIEW_RATE + lk * LIKE_RATE)
    paid = p["paid_morm"] if p else 0
    return {"views": v, "likes": lk, "posts": len(rows),
            "earned_morm": earned, "paid_morm": paid, "pending_morm": max(0, earned - paid)}


def resolve_play_cid(cid):
    conn = _db()
    r = conn.execute("SELECT play_cid,status FROM content WHERE id=?", (cid,)).fetchone()
    conn.close()
    # 秘匿プロキシは approved のみ配信(pending/rejected はストリーム不可)
    if not r or r["status"] not in ("approved", "shadow"):
        return None
    return r["play_cid"]


def play_cid_any(cid):
    """status を問わず play_cid を返す(admin審査プレビュー専用・公開経路では使わない)。"""
    conn = _db()
    r = conn.execute("SELECT play_cid FROM content WHERE id=?", (cid,)).fetchone()
    conn.close()
    return r["play_cid"] if r else None

# --- accounts & hybrid gate --------------------------------------------------

# tier → 制限。effective_tier = max(信頼スコア由来, ステーク由来)
GATE = {
    0: {"posts_day": 1, "max_dur": 60, "links": "none", "comments_day": 3, "label": "新規"},
    1: {"posts_day": 3, "max_dur": 180, "links": "allowlist", "comments_day": 10, "label": "見習い"},
    2: {"posts_day": 10, "max_dur": 600, "links": "all", "comments_day": 30, "label": "信頼"},
    3: {"posts_day": 100000, "max_dur": 3600, "links": "all", "comments_day": 100, "label": "実績"},
}
STAKE_T2 = int(os.environ.get("STAKE_T2", "5000"))        # MORM で T2 相当
STAKE_UNLIMITED = int(os.environ.get("STAKE_UNLIMITED", "50000"))
LINK_ALLOWLIST = {"morm.one", "play.morm.one", "node.morm.one", "youtube.com",
                  "youtu.be", "x.com", "twitter.com", "instagram.com", "tiktok.com"}


def ensure_account(m0r):
    conn = _db()
    conn.execute(
        "INSERT OR IGNORE INTO accounts(m0r,created_at,trust_score,verified,staked_morm,strikes,status)"
        " VALUES(?,?,0,0,0,0,'active')", (m0r, int(time.time())))
    conn.commit()
    r = conn.execute("SELECT * FROM accounts WHERE m0r=?", (m0r,)).fetchone()
    conn.close()
    return r


def effective_tier(acc):
    s = acc["trust_score"]
    t = 3 if s >= 80 else 2 if s >= 40 else 1 if s >= 10 else 0
    st = acc["staked_morm"]
    if st >= STAKE_UNLIMITED:
        t = max(t, 3)
    elif st >= STAKE_T2:
        t = max(t, 2)
    return t


def posts_today(m0r):
    conn = _db()
    n = conn.execute("SELECT COUNT(*) FROM content WHERE uploader=? AND created_at>? AND status!='rejected'",
                     (m0r, int(time.time()) - 86400)).fetchone()[0]
    conn.close()
    return n


def _domain(u):
    try:
        h = urllib.parse.urlparse(u if "://" in u else "http://" + u).hostname or ""
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def gate_check_upload(acc, duration, links):
    if acc["status"] == "banned":
        return False, "アカウントが制限されています"
    t = effective_tier(acc)
    g = GATE[t]
    if posts_today(acc["m0r"]) >= g["posts_day"]:
        return False, f"本日の投稿上限（{g['posts_day']}件）に達しました"
    if duration and duration > g["max_dur"]:
        return False, f"この信頼レベルでは動画は{g['max_dur']}秒までです（現在 {int(duration)}秒）"
    if links:
        if g["links"] == "none":
            return False, "この信頼レベルではリンクを投稿できません"
        if g["links"] == "allowlist":
            for u in links:
                if _domain(u) not in LINK_ALLOWLIST:
                    return False, f"許可されていないリンクです: {_domain(u)}"
    return True, None


def account_public(acc):
    t = effective_tier(acc)
    g = GATE[t]
    return {"m0r": acc["m0r"], "tier": t, "tier_label": g["label"],
            "trust_score": acc["trust_score"], "staked_morm": acc["staked_morm"],
            "status": acc["status"], "verified": bool(acc["verified"]),
            "age_verified": bool(acc["age_verified"]),
            "limits": {"posts_day": g["posts_day"], "max_dur": g["max_dur"],
                       "links": g["links"], "comments_day": g["comments_day"]},
            "posts_today": posts_today(acc["m0r"]),
            "stake_next": {"t2": STAKE_T2, "unlimited": STAKE_UNLIMITED},
            "display_name": _acc_col(acc, "display_name", ""),
            "bio": _acc_col(acc, "bio", ""),
            "followers": follow_counts(acc["m0r"])[0],
            "following": follow_counts(acc["m0r"])[1],
            "ref_code": _acc_col(acc, "ref_code", "") or ref_code_for(acc["m0r"]),
            "referred_by": referred_by(acc["m0r"]),
            "earnings": earnings(acc["m0r"]),
            "rates": {"view": VIEW_RATE, "like": LIKE_RATE},
            "l1": l1_account_safe(acc["m0r"]),
            "points": point_status(acc["m0r"])}


# --- follow / profile (social graph) --------------------------------------
def _acc_col(acc, k, d=""):
    try:
        return acc[k] if (acc and k in acc.keys() and acc[k] is not None) else d
    except Exception:
        return d


def following_set(m0r):
    if not m0r:
        return set()
    conn = _db()
    rows = conn.execute("SELECT followee FROM follows WHERE follower=?", (m0r,)).fetchall()
    conn.close()
    return {r[0] for r in rows}


def is_following(follower, followee):
    if not follower or not followee:
        return False
    conn = _db()
    r = conn.execute("SELECT 1 FROM follows WHERE follower=? AND followee=?",
                     (follower, followee)).fetchone()
    conn.close()
    return bool(r)


def follow_counts(m0r):
    conn = _db()
    fr = conn.execute("SELECT COUNT(*) FROM follows WHERE followee=?", (m0r,)).fetchone()[0]
    fg = conn.execute("SELECT COUNT(*) FROM follows WHERE follower=?", (m0r,)).fetchone()[0]
    conn.close()
    return fr, fg


def toggle_follow(follower, followee, op="follow"):
    if not followee or not followee.startswith("m0r"):
        return {"error": "invalid followee"}
    if follower == followee:
        return {"error": "自分自身はフォローできません"}
    ensure_account(follower)
    ensure_account(followee)
    conn = _db()
    if op == "unfollow":
        conn.execute("DELETE FROM follows WHERE follower=? AND followee=?", (follower, followee))
        following = False
    else:
        conn.execute("INSERT OR IGNORE INTO follows(follower,followee,ts) VALUES(?,?,?)",
                     (follower, followee, int(time.time())))
        following = True
    conn.commit()
    fr = conn.execute("SELECT COUNT(*) FROM follows WHERE followee=?", (followee,)).fetchone()[0]
    conn.close()
    return {"ok": True, "following": following, "followers": fr}


def display_name(m0r):
    conn = _db()
    r = conn.execute("SELECT display_name FROM accounts WHERE m0r=?", (m0r,)).fetchone()
    conn.close()
    return (r["display_name"] or "") if r else ""


def set_profile(m0r, dn, bio):
    ensure_account(m0r)
    dn = (dn or "").strip()[:40]
    bio = (bio or "").strip()[:200]
    conn = _db()
    conn.execute("UPDATE accounts SET display_name=?, bio=? WHERE m0r=?", (dn, bio, m0r))
    conn.commit()
    conn.close()
    return {"ok": True, "display_name": dn, "bio": bio}


def _attach_names(items):
    """公開行リストに投稿者の表示名(uname)を付与(バッチ解決)。"""
    m0rs = list({it["uploader"] for it in items if it.get("uploader")})
    nm = {}
    if m0rs:
        conn = _db()
        qm = ",".join("?" * len(m0rs))
        for r in conn.execute(f"SELECT m0r,display_name FROM accounts WHERE m0r IN ({qm})", m0rs).fetchall():
            nm[r["m0r"]] = r["display_name"] or ""
        conn.close()
    for it in items:
        it["uname"] = nm.get(it.get("uploader", ""), "")
    return items


def creator_profile(m0r, viewer=""):
    conn = _db()
    acc = conn.execute("SELECT * FROM accounts WHERE m0r=?", (m0r,)).fetchone()
    rows = conn.execute("SELECT * FROM content WHERE uploader=? AND status='approved'"
                        " ORDER BY created_at DESC LIMIT 60", (m0r,)).fetchall()
    agg = conn.execute("SELECT COALESCE(SUM(views),0),COALESCE(SUM(likes),0),COUNT(*)"
                       " FROM content WHERE uploader=? AND status='approved'", (m0r,)).fetchone()
    conn.close()
    fr, fg = follow_counts(m0r)
    tier = effective_tier(acc) if acc else 0
    e = earnings(m0r)
    items = _attach_names([_row_public(r) for r in rows])
    return {
        "m0r": m0r, "display_name": _acc_col(acc, "display_name", ""),
        "bio": _acc_col(acc, "bio", ""), "tier": tier, "tier_label": GATE[tier]["label"],
        "verified": bool(acc["verified"]) if acc else False,
        "stats": {"posts": agg[2], "views": agg[0], "likes": agg[1],
                  "earned_morm": e.get("earned_morm", 0), "followers": fr, "following": fg},
        "following": is_following(viewer, m0r) if viewer else False,
        "is_self": bool(viewer and viewer == m0r),
        "items": items,
    }


# --- 年齢認証(自己申告MVP・署名+HMAC cookie) -------------------------------
AGE_SECRET = hashlib.sha256(("morm-age:" + ADMIN_TOKEN).encode()).digest()
AGE_TTL = 180 * 86400


def make_age_token(m0r):
    exp = int(time.time()) + AGE_TTL
    sig = hmac.new(AGE_SECRET, f"{m0r}.{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{m0r}.{exp}.{sig}"


def check_age_token(tok):
    try:
        m0r, exp, sig = tok.split(".")
        if int(exp) < time.time():
            return None
        good = hmac.new(AGE_SECRET, f"{m0r}.{exp}".encode(), hashlib.sha256).hexdigest()[:32]
        return m0r if hmac.compare_digest(sig, good) else None
    except Exception:
        return None


def is_age_verified(m0r):
    if not m0r:
        return False
    conn = _db()
    r = conn.execute("SELECT age_verified FROM accounts WHERE m0r=?", (m0r,)).fetchone()
    conn.close()
    return bool(r and r["age_verified"])


def set_age_verified(m0r, birth_year, method="self"):
    conn = _db()
    ensure_account(m0r)
    conn.execute("UPDATE accounts SET age_verified=1, age_method=?, birth_year=? WHERE m0r=?",
                 (method, birth_year, m0r))
    conn.commit()
    conn.close()


# --- MORM 実配分 (L1 直送金・トレジャリー署名) ------------------------------
_TREASURY = {}


def _treasury():
    if "seed" not in _TREASURY:
        raw = open(TREASURY_SEED_FILE).read().strip()
        seed = bytes.fromhex(raw) if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw) else raw.encode()[:32]
        pub = ed25519_pubkey(seed)
        _TREASURY.update(seed=seed, pub_hex=pub.hex(), addr=m0r_address(pub))
    return _TREASURY


def l1_get(path, timeout=15):
    return json.loads(urllib.request.urlopen(MORM_L1_RPC.rstrip("/") + path, timeout=timeout).read())


def l1_account_safe(m0r, timeout=3):
    """L1の実残高/ステーク/ロックを読む(表示専用)。到達不能/遅延時は None を返し、
    /api/me を止めない。短いtimeoutでハングを防ぐ。決済台帳には一切触れない読み取り。"""
    try:
        a = l1_get(f"/account/{m0r}", timeout=timeout)
        return {"balance": int(a.get("balance", 0)),
                "stake": int(a.get("stake", 0)),
                "locked": int(a.get("locked", 0))}
    except Exception:
        return None


_l1_lock = threading.Lock()


def l1_transfer(to, amount, confirm_timeout=25):
    """トレジャリー→to へ amount(MORM整数)送金。★着地(受取残高の増加)を確認してから返す。
    確認できなければ例外(呼び出し側は paid を記録しない)。nonce競合回避に直列化。"""
    amount = int(amount)
    t = _treasury()
    with _l1_lock:  # nonce競合を避けるため送金は直列化
        b0 = int(l1_get(f"/account/{to}").get("balance", 0))
        nonce = int(l1_get(f"/account/{t['addr']}").get("nonce", 0))
        payload = {"to": to, "amount": amount}
        body = canonical({"kind": 6, "sender": t["pub_hex"], "nonce": nonce, "payload": payload}).encode()
        tx = {"kind": 6, "sender": t["pub_hex"], "nonce": nonce, "payload": payload,
              "signature": ed25519_sign(t["seed"], body).hex()}
        req = urllib.request.Request(MORM_L1_RPC.rstrip("/") + "/tx", data=json.dumps(tx).encode(),
                                     headers={"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())
        if not r.get("ok"):
            raise RuntimeError(r.get("error") or "tx rejected")
        txh = r.get("tx_hash")
        deadline = time.time() + confirm_timeout
        while time.time() < deadline:
            time.sleep(2)
            if int(l1_get(f"/account/{to}").get("balance", 0)) >= b0 + amount:
                return txh
        raise RuntimeError("on-chain 未確認(未着地)")


_payout_lock = threading.Lock()


def payout(m0r):
    """未払いMORM(=earned-paid)を L1 送金し台帳を更新。冪等(paid累積)。

    ★二重支払い対策: 従来は「送金確認→台帳更新」の順で、確認後クラッシュすると次回
    再送し実MORMを二重支払いしていた(回復不能)。ここでは paid を送金前に予約(加算)し、
    送金失敗時のみ巻き戻す。クラッシュ時は最悪「過少支払い(要監査で回復可)」に留まる。
    _payout_lock で read-earnings→予約→送金 を直列化し TOCTOU(並行二重支払い)も防ぐ。"""
    with _payout_lock:
        e = earnings(m0r)
        amt = e["pending_morm"]
        if amt < PAYOUT_MIN:
            return {"ok": True, "paid": 0, "pending": amt}
        now = int(time.time())
        conn = _db()
        # ① 予約: 送金前に paid を加算（この時点で他の payout からは pending=0 に見える）
        conn.execute(
            "INSERT INTO payouts(account,paid_morm,last_tx,updated) VALUES(?,?,?,?) "
            "ON CONFLICT(account) DO UPDATE SET paid_morm=paid_morm+?, updated=?",
            (m0r, amt, "pending", now, amt, now))
        conn.commit()
        try:
            txh = l1_transfer(m0r, amt)          # ② 送金（着地確認まで）
        except Exception:
            # ③ 送金失敗 → 予約を巻き戻し（二重支払いも過少支払いも避ける）
            conn.execute("UPDATE payouts SET paid_morm=paid_morm-?, updated=? WHERE account=?",
                         (amt, int(time.time()), m0r))
            conn.commit()
            conn.close()
            raise
        conn.execute("UPDATE payouts SET last_tx=?, updated=? WHERE account=?", (txh, now, m0r))
        conn.commit()
        conn.close()
        return {"ok": True, "paid": amt, "tx": txh}


# --- 紹介(リファラル): 1段のみ・上限あり・被招待者の実活動(承認投稿)連動 -------
# ★多段MLM/月利保証にしない(feedback_matrix_mlm_caution・MORM設計3原則)。
REF_BONUS_REFERRER = int(os.environ.get("REF_BONUS_REFERRER", "10"))  # 招待者への一度きり報酬(MORM)
REF_BONUS_REFEREE = int(os.environ.get("REF_BONUS_REFEREE", "10"))    # 被招待者への一度きり報酬(MORM)
REF_CAP = int(os.environ.get("REF_CAP", "50"))                        # 報酬対象の招待上限/1人
_ref_lock = threading.Lock()
_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _b36(n):
    n = int(n)
    if n == 0:
        return "0"
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = _B36[r] + s
    return s


def ref_code_for(m0r):
    if not m0r or not m0r.startswith("m0r"):
        return None
    ensure_account(m0r)
    conn = _db()
    r = conn.execute("SELECT ref_code FROM accounts WHERE m0r=?", (m0r,)).fetchone()
    if r and r["ref_code"]:
        conn.close()
        return r["ref_code"]
    base = _b36(int.from_bytes(hashlib.sha256(("morm-ref:" + m0r).encode()).digest()[:8], "big"))
    cand = (base[:7] or "0")
    i = 0
    while conn.execute("SELECT 1 FROM accounts WHERE ref_code=?", (cand,)).fetchone():
        i += 1
        cand = (base + _b36(i))[:8]
    conn.execute("UPDATE accounts SET ref_code=? WHERE m0r=?", (cand, m0r))
    conn.commit()
    conn.close()
    return cand


def m0r_by_code(code):
    if not code:
        return None
    conn = _db()
    r = conn.execute("SELECT m0r FROM accounts WHERE ref_code=?", (code.strip(),)).fetchone()
    conn.close()
    return r["m0r"] if r else None


def _has_approved_post(m0r):
    conn = _db()
    r = conn.execute("SELECT 1 FROM content WHERE uploader=? AND status='approved' LIMIT 1", (m0r,)).fetchone()
    conn.close()
    return bool(r)


def referred_by(m0r):
    conn = _db()
    r = conn.execute("SELECT referrer FROM referrals WHERE referee=?", (m0r,)).fetchone()
    conn.close()
    return r["referrer"] if r else None


def attach_referral(referee, code):
    referrer = m0r_by_code(code)
    if not referrer:
        return {"error": "無効な招待コードです"}
    if referrer == referee:
        return {"error": "自分の招待は使えません"}
    if referred_by(referee):
        return {"error": "already_referred"}
    if _has_approved_post(referee):   # 既に活動済み=招待成立の窓を過ぎている(後付け防止)
        return {"error": "not_eligible"}
    ensure_account(referrer)
    ensure_account(referee)
    conn = _db()
    conn.execute("INSERT OR IGNORE INTO referrals(referee,referrer,created_at) VALUES(?,?,?)",
                 (referee, referrer, int(time.time())))
    conn.commit()
    conn.close()
    settle_async()
    return {"ok": True, "referrer": referrer}


def referral_stats(m0r):
    conn = _db()
    invited = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer=?", (m0r,)).fetchone()[0]
    qualified = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer=? AND qualified=1", (m0r,)).fetchone()[0]
    rewarded = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer=? AND rewarded=1", (m0r,)).fetchone()[0]
    mine = conn.execute("SELECT referrer,qualified,rewarded FROM referrals WHERE referee=?", (m0r,)).fetchone()
    conn.close()
    return {
        "ref_code": ref_code_for(m0r), "invited": invited, "qualified": qualified,
        "rewarded": rewarded, "cap": REF_CAP, "remaining": max(0, REF_CAP - rewarded),
        "bonus_referrer": REF_BONUS_REFERRER, "bonus_referee": REF_BONUS_REFEREE,
        "earned_bonus_morm": rewarded * REF_BONUS_REFERRER,
        "referred_by": (mine["referrer"] if mine else None),
        "my_status": ("rewarded" if (mine and mine["rewarded"]) else
                      "qualified" if (mine and mine["qualified"]) else
                      "pending" if mine else None),
    }


def settle_referrals(limit=25):
    """実活動(承認投稿)した被招待者を qualify → 双方へ一度きり報酬(上限・L1直列送金)。"""
    if not _ref_lock.acquire(blocking=False):
        return {"skipped": True}
    try:
        conn = _db()
        conn.execute("UPDATE referrals SET qualified=1, qualified_at=? WHERE qualified=0 AND referee IN "
                     "(SELECT DISTINCT uploader FROM content WHERE status='approved')", (int(time.time()),))
        conn.commit()
        pend = conn.execute("SELECT referee,referrer FROM referrals WHERE qualified=1 AND rewarded=0 LIMIT ?",
                            (limit,)).fetchall()
        conn.close()
        paid = 0
        for row in pend:
            referee, referrer = row["referee"], row["referrer"]
            conn = _db()
            rc = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer=? AND rewarded=1",
                              (referrer,)).fetchone()[0]
            # ① 予約: 送金前に rewarded=1 を確定(rewarded=0 の時のみ=原子的クレーム)。
            #    l1着地後・DB更新前にクラッシュしても次回再送(二重支払い)しない。
            cur = conn.execute("UPDATE referrals SET rewarded=1, rewarded_at=?, "
                               "reward_tx_referee='pending', reward_tx_referrer='pending' "
                               "WHERE referee=? AND rewarded=0", (int(time.time()), referee))
            conn.commit()
            claimed = cur.rowcount
            conn.close()
            if not claimed:
                continue  # 既に他で確定済み(競合/再入)
            tx_e = tx_r = ""
            # 被招待者レッグ: 未着地なら何も送っていない→全巻き戻し(rewarded=0で次回再試行)。
            try:
                if REF_BONUS_REFEREE > 0:
                    tx_e = l1_transfer(referee, REF_BONUS_REFEREE) or ""
            except Exception:
                conn = _db()
                conn.execute("UPDATE referrals SET rewarded=0, rewarded_at=0, "
                             "reward_tx_referee='', reward_tx_referrer='' WHERE referee=?", (referee,))
                conn.commit()
                conn.close()
                continue
            # 招待者レッグ: ここで失敗しても被招待者は既に着地済み→巻き戻すと二重支払い。
            # rewarded=1 を維持し被招待者txのみ記録、招待者は未払いマーカー('')で残す
            # (payout()同様「最悪でも過少支払い=監査で回復可・二重支払いはしない」方針)。
            try:
                if rc < REF_CAP and REF_BONUS_REFERRER > 0:
                    tx_r = l1_transfer(referrer, REF_BONUS_REFERRER) or ""
            except Exception:
                conn = _db()
                conn.execute("UPDATE referrals SET reward_tx_referee=?, reward_tx_referrer='' "
                             "WHERE referee=?", (tx_e, referee))
                conn.commit()
                conn.close()
                continue
            conn = _db()
            conn.execute("UPDATE referrals SET reward_tx_referee=?, reward_tx_referrer=? WHERE referee=?",
                         (tx_e, tx_r, referee))
            conn.commit()
            conn.close()
            paid += 1
        return {"ok": True, "rewarded": paid}
    finally:
        _ref_lock.release()


def settle_async():
    threading.Thread(target=settle_referrals, daemon=True).start()


# --- エンゲージ報酬ポイント: 付与 / 集計(72h) / 状態 ---------------------------
_points_lock = threading.Lock()


def grant_point(account, kind, content_id):
    """like/comment/share の報酬ポイントを付与。対象外/重複/上限は静かにスキップ(本来の操作は妨げない)。
    反farm: 署名済みm0rのみ・approvedのみ・自分の作品は除外・(account,kind,content_id)恒久1回・72h窓上限。
    ※決済台帳(payouts/referrals/challenge_awards)には一切触れない。"""
    if not account or not account.startswith("m0r"):
        return 0
    pts = POINT_VALUES.get(kind, 0)
    if pts <= 0 or not content_id:
        return 0
    conn = _db()
    try:
        c = conn.execute("SELECT uploader,status FROM content WHERE id=?", (content_id,)).fetchone()
        if not c or c["status"] != "approved" or c["uploader"] == account:
            return 0
        since = int(time.time()) - POINT_WINDOW_SEC
        earned = conn.execute("SELECT COALESCE(SUM(points),0) FROM point_ledger WHERE account=? AND ts>?",
                              (account, since)).fetchone()[0]
        if earned >= POINT_72H_CAP:
            return 0
        try:
            conn.execute("INSERT INTO point_ledger(account,kind,content_id,points,ts,settled) "
                         "VALUES(?,?,?,?,?,0)", (account, kind, content_id, pts, int(time.time())))
            conn.commit()
            return pts
        except Exception:
            return 0   # UNIQUE違反=既に付与済み(恒久1回)
    finally:
        conn.close()


def grant_view_point(cid, viewer):
    """他者の有効再生1回につき、その作品の【クリエイター】へ視聴ポイントを付与(view_by_other)。
    反farm: 呼び出し側で【署名検証済みviewer】のみ渡す・approvedのみ・自己視聴除外・
    (creator,'view',cid|viewer)で恒久1回(=同一視聴者からは1回だけ)・クリエイターの72h窓上限。
    ※決済台帳(payouts/referrals/challenge_awards)には一切触れない。エンゲージ点と同じΣPに乗る。"""
    if VIEW_EARN != "on":
        return 0
    if not viewer or not viewer.startswith("m0r"):
        return 0
    pts = POINT_VALUES.get("view", 0)
    if pts <= 0 or not cid:
        return 0
    conn = _db()
    try:
        c = conn.execute("SELECT uploader,status FROM content WHERE id=?", (cid,)).fetchone()
        if not c or c["status"] != "approved":
            return 0
        creator = c["uploader"]
        if not creator or creator == viewer or not creator.startswith("m0r"):
            return 0  # 自己視聴・無効クリエイターは対象外
        since = int(time.time()) - POINT_WINDOW_SEC
        earned = conn.execute("SELECT COALESCE(SUM(points),0) FROM point_ledger WHERE account=? AND ts>?",
                              (creator, since)).fetchone()[0]
        if earned >= POINT_72H_CAP:
            return 0
        key = f"{cid}|{viewer}"   # per-(creator,content,viewer) 恒久1回
        try:
            conn.execute("INSERT INTO point_ledger(account,kind,content_id,points,ts,settled) "
                         "VALUES(?,?,?,?,?,0)", (creator, "view", key, pts, int(time.time())))
            conn.commit()
            return pts
        except Exception:
            return 0   # UNIQUE違反=同一視聴者から付与済み
    finally:
        conn.close()


def point_status(m0r):
    """口座の未配分ポイント/繰越/次回配分予定などを返す(表示用・非破壊読み取り)。"""
    if not m0r or not m0r.startswith("m0r"):
        return {"pending": 0, "carry": 0, "paid_points": 0, "paid_morm": 0,
                "per_action": POINT_VALUES, "per_morm": POINT_PER_MORM,
                "min_settle": POINT_MIN_SETTLE, "next_settle_ts": 0}
    conn = _db()
    unsettled = conn.execute("SELECT COALESCE(SUM(points),0) FROM point_ledger WHERE account=? AND settled=0",
                             (m0r,)).fetchone()[0]
    pr = conn.execute("SELECT paid_points,paid_morm,carry_points FROM point_payouts WHERE account=?",
                      (m0r,)).fetchone()
    last = conn.execute("SELECT MAX(ts) FROM point_settle_runs").fetchone()[0] or 0
    conn.close()
    carry = pr["carry_points"] if pr else 0
    pending = unsettled + carry
    return {"pending": pending, "carry": carry,
            "paid_points": (pr["paid_points"] if pr else 0),
            "paid_morm": (pr["paid_morm"] if pr else 0),
            "est_morm": pending // POINT_PER_MORM,
            "per_action": POINT_VALUES, "per_morm": POINT_PER_MORM,
            "min_settle": POINT_MIN_SETTLE,
            "next_settle_ts": (last + POINT_SETTLE_INTERVAL) if last else 0}


def _record_settle_run(accounts, amount):
    conn = _db()
    conn.execute("INSERT INTO point_settle_runs(ts,accounts,morm) VALUES(?,?,?)",
                 (int(time.time()), accounts, amount))
    conn.commit()
    conn.close()


def settle_points():
    """未配分ポイントをL1送金して settled化。EMISSION_MODE で配分式を選択:
      fixed(既定)        = points//POINT_PER_MORM の固定レート(従来と完全同一)
      proportional       = Payout_i = B_EPOCH × P_i / ΣP(予算上限つき比例配分)
    どちらも未着地は次回再試行(settled=0のまま=冪等・settle_referrals と同型)。"""
    if not _points_lock.acquire(blocking=False):
        return {"skipped": True}
    try:
        if EMISSION_MODE == "proportional":
            return _settle_proportional()
        return _settle_fixed()
    finally:
        _points_lock.release()


def _settle_fixed():
    """従来: 口座別に pool=未配分+carry を POINT_PER_MORM で整数MORM化・端数carry。"""
    conn = _db()
    accts = [r[0] for r in conn.execute(
        "SELECT DISTINCT account FROM point_ledger WHERE settled=0").fetchall()]
    conn.close()
    paid_accounts = 0
    paid_morm_total = 0
    for acct in accts:
        conn = _db()
        rows = conn.execute("SELECT id,points FROM point_ledger WHERE account=? AND settled=0",
                            (acct,)).fetchall()
        P = sum(r["points"] for r in rows)
        pr = conn.execute("SELECT carry_points FROM point_payouts WHERE account=?", (acct,)).fetchone()
        carry = pr["carry_points"] if pr else 0
        pool = P + carry
        morm = pool // POINT_PER_MORM
        if pool < POINT_MIN_SETTLE or morm < 1:
            conn.close()
            continue  # 繰越(rows は settled=0 のまま・carry据え置き)
        remainder = pool - morm * POINT_PER_MORM
        ids = [(r["id"],) for r in rows]
        now = int(time.time())
        # ① 予約: 送金前に台帳(settled=1)と配分記録(carry更新)を確定。着地後・記録前に
        #    クラッシュしても再集計されず二重支払いしない(settle_referrals/payout と同型)。
        conn.executemany("UPDATE point_ledger SET settled=1 WHERE id=?", ids)
        conn.execute(
            "INSERT INTO point_payouts(account,paid_points,paid_morm,carry_points,last_tx,updated) "
            "VALUES(?,?,?,?,'pending',?) ON CONFLICT(account) DO UPDATE SET "
            "paid_points=paid_points+?, paid_morm=paid_morm+?, carry_points=?, last_tx='pending', updated=?",
            (acct, P, morm, remainder, now, P, morm, remainder, now))
        conn.commit()
        try:
            txh = l1_transfer(acct, morm) or ""
        except Exception:
            # ③ 送金失敗 → 予約を巻き戻し(settled=0・配分記録を減算・carryを元へ)
            conn.executemany("UPDATE point_ledger SET settled=0 WHERE id=?", ids)
            conn.execute("UPDATE point_payouts SET paid_points=paid_points-?, paid_morm=paid_morm-?, "
                         "carry_points=?, last_tx='', updated=? WHERE account=?",
                         (P, morm, carry, int(time.time()), acct))
            conn.commit()
            conn.close()
            continue  # 未着地=次回 settle で再試行
        conn.execute("UPDATE point_payouts SET last_tx=?, updated=? WHERE account=?",
                     (txh, int(time.time()), acct))
        conn.commit()
        conn.close()
        paid_accounts += 1
        paid_morm_total += morm
    _record_settle_run(paid_accounts, paid_morm_total)
    return {"ok": True, "mode": "fixed", "accounts": paid_accounts, "morm": paid_morm_total}


def _settle_proportional():
    """予算上限つき比例配分。総発行 = B_EPOCH(固定) を、当エポック未配分ポイントの総和で按分。
      Payout_i(base units) = floor(B_units × P_i / ΣP)、口座上限=B_units×EPOCH_ACCT_CAP_FRAC。
    ・配分は base units(=L1整数)で計算 → BASE=1e6 なら sub-MORM 配分可。
    ・share<1 unit は繰越(settled=0据え置き)。上限超過分は当エポック不払い(反whale)。
    ・総発行は B_units を超えない(=参加者が増えても暴走しない)。"""
    conn = _db()
    rows = conn.execute("SELECT account, id, points FROM point_ledger WHERE settled=0").fetchall()
    conn.close()
    if not rows:
        _record_settle_run(0, 0)
        return {"ok": True, "mode": "proportional", "accounts": 0, "units": 0}
    per = {}
    for r in rows:
        d = per.setdefault(r["account"], {"P": 0, "ids": []})
        d["P"] += r["points"]
        d["ids"].append(r["id"])
    total_P = sum(d["P"] for d in per.values())
    if total_P <= 0:
        _record_settle_run(0, 0)
        return {"ok": True, "mode": "proportional", "accounts": 0, "units": 0}
    B_units = int(round(B_EPOCH_MORM * SPLIT_ENGAGE * MORM_BASE_UNITS_PER_MORM))
    cap_units = int(B_units * EPOCH_ACCT_CAP_FRAC)
    paid_accounts = 0
    paid_units_total = 0
    for acct, d in per.items():
        share = (B_units * d["P"]) // total_P          # floor, base units
        if cap_units > 0 and share > cap_units:
            share = cap_units                          # 反whale(超過は不払い)
        if share < 1:
            continue                                    # 端数=次回へ(settled=0据え置き)
        ids = [(i,) for i in d["ids"]]
        now = int(time.time())
        conn = _db()
        # ① 予約: 送金前に台帳(settled=1)と配分記録を確定(着地後クラッシュでも再送しない)。
        # proportional では paid_morm 列に base units を積む(carry_points は据え置き=固定モード用)。
        conn.executemany("UPDATE point_ledger SET settled=1 WHERE id=?", ids)
        conn.execute(
            "INSERT INTO point_payouts(account,paid_points,paid_morm,carry_points,last_tx,updated) "
            "VALUES(?,?,?,?,'pending',?) ON CONFLICT(account) DO UPDATE SET "
            "paid_points=paid_points+?, paid_morm=paid_morm+?, last_tx='pending', updated=?",
            (acct, d["P"], share, 0, now, d["P"], share, now))
        conn.commit()
        try:
            txh = l1_transfer(acct, share) or ""        # amount=生のL1整数(=base units)
        except Exception:
            # ③ 送金失敗 → 予約を巻き戻し(settled=0・配分記録を減算)
            conn.executemany("UPDATE point_ledger SET settled=0 WHERE id=?", ids)
            conn.execute("UPDATE point_payouts SET paid_points=paid_points-?, paid_morm=paid_morm-?, "
                         "last_tx='', updated=? WHERE account=?",
                         (d["P"], share, int(time.time()), acct))
            conn.commit()
            conn.close()
            continue                                    # 未着地=次回再試行
        conn.execute("UPDATE point_payouts SET last_tx=?, updated=? WHERE account=?",
                     (txh, int(time.time()), acct))
        conn.commit()
        conn.close()
        paid_accounts += 1
        paid_units_total += share
    _record_settle_run(paid_accounts, paid_units_total)
    return {"ok": True, "mode": "proportional", "accounts": paid_accounts,
            "units": paid_units_total, "budget_units": B_units, "total_points": total_P}


def _points_loop():
    """72h毎にポイントを集計・配分する常駐デーモン(restart耐性=最終実行tsで判定)。"""
    while True:
        try:
            conn = _db()
            last = conn.execute("SELECT MAX(ts) FROM point_settle_runs").fetchone()[0] or 0
            conn.close()
            if int(time.time()) - last >= POINT_SETTLE_INTERVAL:
                settle_points()
        except Exception:
            pass
        time.sleep(POINT_TICK_SEC)


# --- チャレンジ(お題) + リミックス(系譜) ---------------------------------------
# ★MORM設計3原則/多段MLM回避を踏襲: 参加=承認投稿(実活動連動)。報酬プールの配分は
#   admin決裁でトレジャリー→上位クリエイターへ一度きり(challenge_awardsで冪等)。
#   ユーザー資金の移動は伴わない(プール funding は admin のみ)。
CHALLENGE_MIN_TIER = int(os.environ.get("CHALLENGE_MIN_TIER", "1"))  # 作成に必要な信頼レベル(admin除く)
CHALLENGE_PER_DAY = int(os.environ.get("CHALLENGE_PER_DAY", "3"))    # 1アカウント/日 作成上限
_chal_lock = threading.Lock()


def _slugify(title):
    base = "".join(c if (c.isalnum() and c.isascii()) else " " for c in title.lower())
    base = "-".join(base.split())[:32].strip("-")
    if not base:
        base = "c" + hashlib.sha1(title.encode()).hexdigest()[:8]
    return base


def _unique_slug(conn, title):
    base = _slugify(title)
    slug, i = base, 2
    while conn.execute("SELECT 1 FROM challenges WHERE slug=?", (slug,)).fetchone():
        slug = f"{base}-{i}"
        i += 1
    return slug


def create_challenge(creator, title, description="", ends_days=0, reward_pool=0):
    title = (title or "").strip()[:60]
    if not title:
        return {"error": "タイトルが必要です"}
    ensure_account(creator)
    conn = _db()
    slug = _unique_slug(conn, title)
    try:
        ends_days = max(0, int(ends_days or 0))
    except Exception:
        ends_days = 0
    ends_at = int(time.time()) + ends_days * 86400 if ends_days else 0
    conn.execute("INSERT INTO challenges(slug,title,description,creator,created_at,ends_at,reward_pool,status)"
                 " VALUES(?,?,?,?,?,?,?,'active')",
                 (slug, title, (description or "").strip()[:600], creator,
                  int(time.time()), ends_at, max(0, int(reward_pool or 0))))
    conn.commit()
    conn.close()
    return {"ok": True, "slug": slug, "title": title, "ends_at": ends_at}


def challenge_active(slug):
    if not slug:
        return False
    conn = _db()
    r = conn.execute("SELECT status,ends_at FROM challenges WHERE slug=?", (slug,)).fetchone()
    conn.close()
    if not r or r["status"] != "active":
        return False
    return not (r["ends_at"] and r["ends_at"] < time.time())


def _challenge_cover(conn, slug):
    r = conn.execute("SELECT id,cover_ts FROM content WHERE challenge=? AND status='approved'"
                     " ORDER BY (cover_ts>0) DESC, likes DESC, views DESC LIMIT 1", (slug,)).fetchone()
    if not r:
        return None
    return f"/cover/{r['id']}.jpg" if r["cover_ts"] else f"/thumb/{r['id']}.svg"


def list_challenges(status="active"):
    now = time.time()
    conn = _db()
    rows = conn.execute("SELECT * FROM challenges ORDER BY created_at DESC").fetchall()
    counts = {r[0]: r[1] for r in conn.execute(
        "SELECT challenge, COUNT(*) FROM content WHERE status='approved' AND challenge!=''"
        " GROUP BY challenge").fetchall()}
    out = []
    for r in rows:
        active = r["status"] == "active" and not (r["ends_at"] and r["ends_at"] < now)
        if status == "active" and not active:
            continue
        out.append({"slug": r["slug"], "title": r["title"], "description": r["description"],
                    "creator": r["creator"], "creator_name": display_name(r["creator"]),
                    "created_at": r["created_at"], "ends_at": r["ends_at"],
                    "reward_pool": r["reward_pool"], "status": "active" if active else "closed",
                    "settled": bool(r["settled"]), "entries": counts.get(r["slug"], 0),
                    "cover": _challenge_cover(conn, r["slug"])})
    conn.close()
    return out


def challenge_detail(slug, sort="hot", viewer=""):
    conn = _db()
    c = conn.execute("SELECT * FROM challenges WHERE slug=?", (slug,)).fetchone()
    if not c:
        conn.close()
        return None
    rows = conn.execute("SELECT * FROM content WHERE challenge=? AND status='approved'", (slug,)).fetchall()
    conn.close()
    now = time.time()
    entries = [r for r in rows if r["rating"] != "r18"]  # 一覧はSFWのみ(R18は年齢ゾーン扱い)
    if sort == "new":
        entries.sort(key=lambda r: r["created_at"], reverse=True)
    else:
        aff = viewer_tag_affinity(viewer) if (viewer and viewer.startswith("m0r")) else None
        entries.sort(key=lambda r: _fyp_score(r, now, aff), reverse=True)
    board = sorted(rows, key=lambda r: (r["likes"], r["views"]), reverse=True)[:10]
    items = _attach_meta(_attach_names([_row_public(r) for r in entries[:60]]))
    active = c["status"] == "active" and not (c["ends_at"] and c["ends_at"] < now)
    return {
        "slug": c["slug"], "title": c["title"], "description": c["description"],
        "creator": c["creator"], "creator_name": display_name(c["creator"]),
        "created_at": c["created_at"], "ends_at": c["ends_at"], "reward_pool": c["reward_pool"],
        "status": "active" if active else "closed", "settled": bool(c["settled"]),
        "entries": len(rows), "items": items,
        "leaderboard": [{"m0r": r["uploader"], "name": display_name(r["uploader"]), "id": r["id"],
                         "title": r["title"], "likes": r["likes"], "views": r["views"]} for r in board],
    }


def remix_counts(cids):
    """{cid: 承認済みリミックス数}(バッチ)。"""
    cids = [c for c in cids if c]
    if not cids:
        return {}
    conn = _db()
    qm = ",".join("?" * len(cids))
    rows = conn.execute(
        f"SELECT remix_of, COUNT(*) c FROM content WHERE status='approved' AND remix_of IN ({qm})"
        " GROUP BY remix_of", cids).fetchall()
    conn.close()
    return {r["remix_of"]: r["c"] for r in rows}


def _attach_meta(items):
    """公開行に remix_count / 親(remix_of)の title,name / challenge の title を付与(バッチ)。"""
    if not items:
        return items
    rc = remix_counts([it["id"] for it in items])
    sc = story_counts([it["id"] for it in items])
    parents = list({it.get("remix_of") for it in items if it.get("remix_of")})
    chals = list({it.get("challenge") for it in items if it.get("challenge")})
    pmap, cmap = {}, {}
    conn = _db()
    if parents:
        qm = ",".join("?" * len(parents))
        for r in conn.execute(f"SELECT id,title,uploader FROM content WHERE id IN ({qm})", parents).fetchall():
            pmap[r["id"]] = (r["title"], r["uploader"])
    if chals:
        qm = ",".join("?" * len(chals))
        for r in conn.execute(f"SELECT slug,title FROM challenges WHERE slug IN ({qm})", chals).fetchall():
            cmap[r["slug"]] = r["title"]
    conn.close()
    for it in items:
        it["remix_count"] = rc.get(it["id"], 0)
        it["story"] = sc.get(it["id"], 0)
        p = pmap.get(it.get("remix_of"))
        if p:
            it["remix_of_title"], it["remix_of_name"] = p[0], display_name(p[1])
        if it.get("challenge"):
            it["challenge_title"] = cmap.get(it["challenge"], it["challenge"])
    return items


# --- グリッドチョイス(分岐ストーリー): ノード=content 行、分岐=story_edges --------
def story_counts(cids):
    """{cid: 承認済みの分岐数}(バッチ)。フィード/プレイヤーに「🕸 分岐 N」チップを出す用。"""
    cids = [c for c in cids if c]
    if not cids:
        return {}
    conn = _db()
    qm = ",".join("?" * len(cids))
    rows = conn.execute(
        f"SELECT e.from_cid, COUNT(*) c FROM story_edges e "
        f"JOIN content t ON t.id=e.to_cid AND t.status='approved' "
        f"WHERE e.from_cid IN ({qm}) GROUP BY e.from_cid", cids).fetchall()
    conn.close()
    return {r["from_cid"]: r["c"] for r in rows}


def story_node(cid, account=None):
    """グリッドチョイスの1ノード: 中央=cid のコンテンツ + 四方の分岐(story_edges の子)。
    分岐が無ければ choices=[](=物語の末端)。決済台帳には一切触れない読み取り。"""
    node = get_content(cid, account)
    if not node:
        return None
    conn = _db()
    rows = conn.execute(
        "SELECT e.to_cid, e.slot, e.label, e.cost FROM story_edges e "
        "JOIN content t ON t.id=e.to_cid AND t.status='approved' "
        "WHERE e.from_cid=? ORDER BY e.slot ASC, e.id ASC LIMIT 4", (cid,)).fetchall()
    parents = [r["from_cid"] for r in conn.execute(
        "SELECT DISTINCT from_cid FROM story_edges WHERE to_cid=? LIMIT 4", (cid,)).fetchall()]
    conn.close()
    choices = []
    for r in rows:
        t = get_content(r["to_cid"])
        if not t:
            continue
        choices.append({"to": r["to_cid"], "slot": r["slot"], "label": r["label"],
                        "cost": r["cost"], "target": {
                            "id": t["id"], "title": t["title"], "cover": t["cover"],
                            "thumb": t["thumb"], "likes": t["likes"], "views": t["views"]}})
    return {"node": node, "choices": choices, "parents": parents,
            "is_end": len(choices) == 0}


def list_remixes(cid, limit=60):
    conn = _db()
    rows = conn.execute("SELECT * FROM content WHERE remix_of=? AND status='approved'"
                        " ORDER BY created_at DESC LIMIT ?", (cid, limit)).fetchall()
    parent = conn.execute("SELECT id,title,uploader FROM content WHERE id=?", (cid,)).fetchone()
    conn.close()
    items = _attach_meta(_attach_names([_row_public(r) for r in rows]))
    return {"parent": ({"id": parent["id"], "title": parent["title"], "uploader": parent["uploader"],
                        "uname": display_name(parent["uploader"])} if parent else None),
            "items": items, "total": len(items)}


def settle_challenge(slug, pool=None, top=3, weights=None):
    """報酬プールを上位クリエイターへ配分(admin決裁・トレジャリー→L1・冪等)。"""
    with _chal_lock:
        conn = _db()
        c = conn.execute("SELECT * FROM challenges WHERE slug=?", (slug,)).fetchone()
        if not c:
            conn.close()
            return {"error": "not found"}
        rows = conn.execute("SELECT uploader,likes,views,id FROM content"
                            " WHERE challenge=? AND status='approved'", (slug,)).fetchall()
        conn.close()
        pool = int(pool if pool is not None else c["reward_pool"])
        if pool <= 0:
            return {"error": "報酬プールが0です"}
        best = {}  # クリエイター単位に集約(1人1作の代表スコア)
        for r in rows:
            sc = r["likes"] * 3 + r["views"] * 0.05
            if r["uploader"] not in best or sc > best[r["uploader"]][0]:
                best[r["uploader"]] = (sc, r["id"])
        ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:max(1, int(top))]
        if not ranked:
            return {"error": "参加作品がありません"}
        w = weights or ([0.5, 0.3, 0.2] if len(ranked) >= 3 else None)
        if not w or len(w) < len(ranked):
            w = [1.0 / len(ranked)] * len(ranked)   # 均等配分
        wsum = sum(w[:len(ranked)])
        results = []
        for i, (m0r, (sc, cid)) in enumerate(ranked):
            amt = int(pool * w[i] / wsum)
            if amt <= 0:
                continue
            # ① 予約: 送金前に award 行を確定(PK(slug,m0r)で原子的クレーム)。既存=授与
            #    済み(または予約中)→skip。着地後・記録前クラッシュでも再授与(二重支払い)しない。
            conn = _db()
            try:
                conn.execute("INSERT INTO challenge_awards(slug,m0r,rank,amount,tx,ts)"
                             " VALUES(?,?,?,?,'pending',?)", (slug, m0r, i + 1, amt, int(time.time())))
                conn.commit()
            except Exception:
                conn.close()
                results.append({"m0r": m0r, "amount": amt, "skipped": "already"})
                continue
            conn.close()
            try:
                tx = l1_transfer(m0r, amt) or ""
            except Exception as e:
                # ③ 送金失敗 → 予約を巻き戻し(次回admin決裁で再試行可能に)
                conn = _db()
                conn.execute("DELETE FROM challenge_awards WHERE slug=? AND m0r=?", (slug, m0r))
                conn.commit()
                conn.close()
                results.append({"m0r": m0r, "amount": amt, "error": str(e)})
                continue
            conn = _db()
            conn.execute("UPDATE challenge_awards SET rank=?, amount=?, tx=?, ts=? WHERE slug=? AND m0r=?",
                         (i + 1, amt, tx, int(time.time()), slug, m0r))
            conn.commit()
            conn.close()
            results.append({"m0r": m0r, "rank": i + 1, "amount": amt, "tx": tx})
        conn = _db()
        conn.execute("UPDATE challenges SET settled=1 WHERE slug=?", (slug,))
        conn.commit()
        conn.close()
        return {"ok": True, "slug": slug, "pool": pool,
                "paid": sum(x.get("amount", 0) for x in results if x.get("tx")), "results": results}


def content_rating(cid):
    conn = _db()
    r = conn.execute("SELECT rating,status FROM content WHERE id=?", (cid,)).fetchone()
    conn.close()
    return (r["rating"], r["status"]) if r else (None, None)


def content_owner(cid):
    conn = _db()
    r = conn.execute("SELECT uploader FROM content WHERE id=?", (cid,)).fetchone()
    conn.close()
    return r["uploader"] if r else None


def set_cover(cid, jpg_bytes, ts):
    conn = _db()
    conn.execute("INSERT INTO covers(content_id,jpg,ts,updated) VALUES(?,?,?,?) "
                 "ON CONFLICT(content_id) DO UPDATE SET jpg=?, ts=?, updated=?",
                 (cid, jpg_bytes, ts, int(time.time()), jpg_bytes, ts, int(time.time())))
    conn.execute("UPDATE content SET cover_ts=? WHERE id=?", (ts if ts > 0 else 0.001, cid))
    conn.commit()
    conn.close()


def clear_cover(cid):
    conn = _db()
    conn.execute("DELETE FROM covers WHERE content_id=?", (cid,))
    conn.execute("UPDATE content SET cover_ts=0 WHERE id=?", (cid,))
    conn.commit()
    conn.close()


def get_cover(cid):
    conn = _db()
    r = conn.execute("SELECT jpg FROM covers WHERE content_id=?", (cid,)).fetchone()
    conn.close()
    return r["jpg"] if r else None


def canonical(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def verify_signed(data, kind):
    """data={kind,sender(pub hex),nonce,payload,sig(hex)} を検証し (m0r, payload) を返す。失敗時 (None, err)。"""
    try:
        if data.get("kind") != kind:
            return None, "kind mismatch"
        pub = bytes.fromhex(data["sender"])
        sig = bytes.fromhex(data["sig"])
        msg = canonical({"kind": kind, "sender": data["sender"],
                         "nonce": data["nonce"], "payload": data["payload"]}).encode()
        if not ed25519_verify(pub, msg, sig):
            return None, "署名が無効です"
        return m0r_address(pub), data["payload"]
    except Exception as e:
        return None, f"bad request: {e}"


def pub_to_m0r(pub_hex):
    """32byte ed25519 公開鍵(hex)から m0r を導出。空/不正長は例外。
    ★私的read(earnings/mine/me)のIDOR封鎖: m0r=blake2b(pub) は一方向でアドレスから pub は逆算不可。"""
    raw = bytes.fromhex(pub_hex or "")
    if len(raw) != 32:
        raise ValueError("pub must be 32 bytes")
    return m0r_address(raw)


def probe_encoded(play_cid, timeout=20):
    """エンコード後の実尺(EXTINF合計)と実解像度(master RESOLUTION)を gateway から取得。"""
    base = f"{GATEWAY}/api/video/{play_cid}"
    m = urllib.request.urlopen(base + "/master.m3u8", timeout=timeout).read().decode()
    w = h = 0
    mm = re.search(r"RESOLUTION=(\d+)x(\d+)", m)
    if mm:
        w, h = int(mm.group(1)), int(mm.group(2))
    dur = 0.0
    var = re.search(r"(\d+p)/index\.m3u8", m)
    if var:
        vpl = urllib.request.urlopen(f"{base}/{var.group(1)}/index.m3u8", timeout=timeout).read().decode()
        dur = sum(float(x) for x in re.findall(r"#EXTINF:([\d.]+)", vpl))
    ar = "portrait" if h > w else "landscape" if w > h else "square"
    return {"duration": round(dur, 1), "w": w, "h": h, "ar": ar}


def apply_verdict(cid, verdict):
    """worker からの判定を content に反映(category を tags に追加・rating/labels/status)。"""
    conn = _db()
    r = conn.execute("SELECT status,tags FROM content WHERE id=?", (cid,)).fetchone()
    if not r or r["status"] != "pending":
        conn.close()
        return False
    tags = [t for t in r["tags"].split(",") if t]
    if verdict["category"] and verdict["category"] not in tags:
        tags.append(verdict["category"])
    score = max(verdict["labels"].values()) if verdict["labels"] else 0.0
    conn.execute("UPDATE content SET status=?,rating=?,tags=?,mod_score=?,mod_labels=? WHERE id=?",
                 (verdict["status"], verdict["rating"], ",".join(tags), score,
                  json.dumps(verdict["labels"]), cid))
    conn.execute("INSERT INTO moderation_log(target_type,target_id,model,score,labels,decision,reviewer,ts)"
                 " VALUES('content',?,?,?,?,?,'ai-worker',?)",
                 (cid, verdict["model"], score, json.dumps(verdict["labels"]),
                  f"{verdict['status']}:{verdict['reason']}", int(time.time())))
    if verdict["status"] == "rejected":
        conn.execute("UPDATE accounts SET strikes=strikes+1 WHERE m0r=(SELECT uploader FROM content WHERE id=?)", (cid,))
    conn.commit()
    conn.close()
    if verdict["status"] == "approved":   # 被招待者の実活動→紹介成立チェック
        settle_async()
    return True


def pull_pending(limit=1):
    """worker用: status='pending' を取り、判定に必要な情報(+uploaderのtier)を返す。"""
    conn = _db()
    rows = conn.execute("SELECT * FROM content WHERE status='pending' ORDER BY created_at ASC LIMIT ?",
                        (limit,)).fetchall()
    items = []
    for r in rows:
        acc = conn.execute("SELECT * FROM accounts WHERE m0r=?", (r["uploader"],)).fetchone()
        tier = effective_tier(acc) if acc else 0
        items.append({"id": r["id"], "title": r["title"], "description": r["description"],
                      "tags": [t for t in r["tags"].split(",") if t], "tier": tier,
                      "play_cid": r["play_cid"]})
    conn.close()
    return items


def gateway_encode(raw_bytes, filename="upload.mp4", timeout=120):
    """hpmini gateway に生バイトをPOST→ジョブ完了ポーリング→content_id を返す。"""
    up = urllib.request.Request(
        f"{GATEWAY}/api/video/upload?filename={urllib.parse.quote(filename)}",
        data=raw_bytes, method="POST",
        headers={"Content-Type": "application/octet-stream"})
    j = json.loads(urllib.request.urlopen(up, timeout=timeout).read())
    job = j.get("job_id")
    if not job:
        raise RuntimeError("no job_id")
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = json.loads(urllib.request.urlopen(f"{GATEWAY}/api/video/job/{job}", timeout=20).read())
        if s.get("state") == "done" and s.get("content_id"):
            return s["content_id"]
        if s.get("state") == "error":
            raise RuntimeError(s.get("error") or "encode error")
        time.sleep(1.5)
    raise TimeoutError("encode timeout")


def create_reservation(m0r, payload, token):
    cid = "m0v" + hashlib.sha1(f"{m0r}{payload.get('title')}{token}".encode()).hexdigest()[:13]
    tags = [t.strip() for t in (payload.get("tags") or [])[:8] if t.strip()]
    # リミックス元: 存在し承認済みのみ採用(なりすまし系譜を防ぐ)
    remix_of = (payload.get("remix_of") or "").strip()
    if remix_of:
        conn0 = _db()
        ok = conn0.execute("SELECT 1 FROM content WHERE id=? AND status='approved'", (remix_of,)).fetchone()
        conn0.close()
        if not ok:
            remix_of = ""
        elif "remix" not in tags:
            tags.append("remix")
    # チャレンジ: active のみ採用し、slug を tag にも付与(タグ導線でも拾える)
    challenge = (payload.get("challenge") or "").strip()
    if challenge and not challenge_active(challenge):
        challenge = ""
    if challenge and challenge not in tags:
        tags.append(challenge)
    tags = ",".join(tags[:8])
    conn = _db()
    conn.execute(
        "INSERT INTO content(id,play_cid,title,tags,uploader,created_at,views,likes,hue,ar,"
        "description,status,links,rating,duration,upload_token,remix_of,challenge)"
        " VALUES(?,?,?,?,?,?,0,0,?,?,?,'reserved',?,'sfw',0,?,?,?)",
        (cid, "", (payload.get("title") or "untitled")[:120], tags, m0r, int(time.time()),
         random.randint(0, 359), payload.get("ar", "portrait"),
         (payload.get("description") or "")[:2000],
         json.dumps(payload.get("links") or []), token, remix_of, challenge))
    conn.commit()
    conn.close()
    return cid


def finalize_reservation(cid, token, play_cid, duration, ar):
    """メディア束縛→status='pending'(AI審査待ち)。実尺/実arを確定。分類は worker が非同期で行う。"""
    conn = _db()
    r = conn.execute("SELECT upload_token,status FROM content WHERE id=?", (cid,)).fetchone()
    if not r or r["upload_token"] != token or r["status"] != "reserved":
        conn.close()
        return None
    conn.execute("UPDATE content SET play_cid=?,duration=?,ar=?,status='pending',upload_token='' WHERE id=?",
                 (play_cid, duration, ar, cid))
    conn.commit()
    conn.close()
    return "pending"

# --- secrecy proxy -----------------------------------------------------------

# edge が返すプレイリスト内の絶対URL: https://<any-host>/api/video/<play_cid>/...
# → /m/<catalog_id>/... へ書換。ホスト・実content-hash 双方を隠蔽。
_URL_RE = re.compile(rb"https?://[^/\s\"']+/api/video/[0-9a-fA-F]+/")
_SEG_HOP = ("connection", "keep-alive", "transfer-encoding", "server", "date",
            "x-morm-edge", "x-morm-served-by", "x-morm-cache", "x-morm-origin-peer",
            "cf-ray", "cf-cache-status", "alt-svc", "nel", "report-to",
            "access-control-allow-origin", "set-cookie", "via")


def _edge_fetch(play_cid, rest, range_hdr=None):
    """1台のhealthy edgeから /api/video/<play_cid>/<rest> を取得。(status, headers, body)"""
    last = None
    with _lock:
        pool = list(_state["healthy"])
    order = random.sample(pool, len(pool))
    # 住宅edgeを全部試して駄目なら公開originへ落とす。edge全滅でも再生は止めない。
    if ORIGIN_FALLBACK and ORIGIN_FALLBACK not in order:
        order.append(ORIGIN_FALLBACK)
    for host in order:
        url = f"https://{host}/api/video/{play_cid}/{rest}"
        req = urllib.request.Request(url, headers={"User-Agent": "morm-play/1.0"})
        if range_hdr:
            req.add_header("Range", range_hdr)
        try:
            r = urllib.request.urlopen(req, timeout=12)
            return r.status, dict(r.getheaders()), r.read()
        except urllib.error.HTTPError as e:
            if e.code in (206, 416):
                return e.code, dict(e.headers), e.read()
            last = e
            continue
        except Exception as e:
            last = e
            continue
    raise last or RuntimeError("no edge")


def _rewrite_playlist(body, cid):
    return _URL_RE.sub(f"/m/{cid}/".encode(), body)

# --- generative Vivid90s thumbnail (deterministic from id) -------------------

_PAL = ["#1E37E6", "#EC1E79", "#FF4A17", "#0EA24A", "#FFD11A", "#6B2CE6"]


def thumb_svg(cid, title=""):
    h = hashlib.sha256(cid.encode()).digest()
    b = list(h)
    c1 = _PAL[b[0] % len(_PAL)]
    c2 = _PAL[b[1] % len(_PAL)]
    if c2 == c1:
        c2 = _PAL[(b[1] + 1) % len(_PAL)]
    W, H = 400, 400
    rot = b[2] % 360
    marks = []
    for i in range(3, 3 + 5):
        x = 40 + (b[i] % 320)
        y = 40 + (b[(i * 2) % 32] % 320)
        rr = 24 + (b[(i * 3) % 32] % 90)
        op = 0.16 + (b[(i * 5) % 32] % 30) / 100.0
        kind = b[(i * 7) % 32] % 3
        col = _PAL[b[(i * 11) % 32] % len(_PAL)]
        if kind == 0:
            marks.append(f'<circle cx="{x}" cy="{y}" r="{rr}" fill="{col}" opacity="{op:.2f}"/>')
        elif kind == 1:
            marks.append(f'<rect x="{x - rr}" y="{y - rr}" width="{rr * 2}" height="{rr * 2}" fill="none" stroke="{col}" stroke-width="6" opacity="{op:.2f}"/>')
        else:
            marks.append(f'<path d="M{x - rr} {y} L{x} {y - rr} L{x + rr} {y} L{x} {y + rr} Z" fill="{col}" opacity="{op:.2f}"/>')
    initial = html.escape((title.strip()[:1] or "M").upper())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>
<rect width="{W}" height="{H}" fill="url(#g)"/>
<g transform="rotate({rot} {W//2} {H//2})">{''.join(marks)}</g>
<text x="28" y="356" font-family="Helvetica Neue,Arial,sans-serif" font-weight="800" font-size="150" fill="#F4F2EA" opacity="0.9">{initial}</text>
</svg>'''

# --- frontend ----------------------------------------------------------------

INDEX_HTML = r"""<!doctype html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MORM Play</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.13/dist/hls.min.js"></script>
<style>
:root{--paper:#F4F2EA;--card:#FBFAF4;--ink:#0C0C0E;--soft:#4A4A4E;--line:#0C0C0E;
--blue:#1E37E6;--magenta:#EC1E79;--orange:#FF4A17;--accent:var(--blue)}
@media(prefers-color-scheme:dark){:root{--paper:#0C0C0E;--card:#151517;--ink:#F4F2EA;--soft:#B7B7B0;--line:#F4F2EA;--blue:#4A5CFF;--magenta:#FF3E93;--orange:#FF6A3D}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Helvetica Neue",Helvetica,Arial,"Hiragino Kaku Gothic ProN",sans-serif;-webkit-font-smoothing:antialiased}
header{position:sticky;top:0;z-index:20;background:var(--paper);border-bottom:1px solid var(--line);padding:14px 18px}
.bar{display:flex;align-items:center;gap:14px;max-width:1300px;margin:0 auto}
.logo{font-weight:900;font-size:22px;letter-spacing:-.04em;color:var(--magenta);text-decoration:none;white-space:nowrap}
.logo b{color:var(--blue)}
.search{flex:1;display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:999px;padding:9px 16px;background:var(--card)}
.search input{border:0;outline:0;background:transparent;color:var(--ink);font-size:15px;width:100%}
.tabs{display:flex;gap:6px}
.tab{font-family:ui-monospace,monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:999px;padding:8px 14px;cursor:pointer}
.tab.on{background:var(--ink);color:var(--paper)}
.chips{max-width:1300px;margin:12px auto 0;display:flex;gap:8px;overflow-x:auto;padding:0 18px 2px;scrollbar-width:none}
.chips::-webkit-scrollbar{display:none}
.chip{white-space:nowrap;font-size:13px;border:1px solid var(--line);border-radius:999px;padding:6px 13px;cursor:pointer;background:var(--card);color:var(--ink)}
.chip.on{background:var(--accent);color:#fff;border-color:var(--accent)}
main{max-width:1300px;margin:16px auto 60px;padding:0 14px}
.grid{column-gap:14px;column-width:230px}
.card{break-inside:avoid;margin:0 0 14px;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;cursor:pointer;transition:transform .12s}
.card:hover{transform:translateY(-3px)}
.card .thumb{width:100%;height:auto;display:block;background:var(--paper)}
.card .meta{padding:9px 11px 11px}
.card .t{font-weight:700;font-size:14px;line-height:1.25;margin:0 0 6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card .r{display:flex;align-items:center;justify-content:space-between;color:var(--soft);font-size:12px}
.card .r .u{font-family:ui-monospace,monospace;font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:60%}
.like{display:inline-flex;align-items:center;gap:4px;border:0;background:transparent;color:var(--soft);cursor:pointer;font-size:12px;padding:0}
.like.on{color:var(--magenta)}
.sentinel{height:40px}
.empty{text-align:center;color:var(--soft);padding:60px 0;font-size:15px}
/* modal */
.ov{position:fixed;inset:0;z-index:50;background:rgba(4,4,6,.82);display:none;align-items:center;justify-content:center;padding:16px}
.ov.on{display:flex}
.modal{background:var(--card);border:1px solid var(--line);border-radius:16px;max-width:520px;width:100%;overflow:hidden}
.modal video{width:100%;background:#000;display:block;max-height:70vh}
.mbody{padding:14px 16px 18px}
.mbody h3{margin:0 0 6px;font-size:18px}
.mtags{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.mtag{font-size:11px;font-family:ui-monospace,monospace;border:1px solid var(--line);border-radius:999px;padding:3px 9px;color:var(--soft)}
.mact{display:flex;gap:10px;margin-top:12px}
.btn{flex:1;border:1px solid var(--line);border-radius:999px;padding:11px;font-weight:700;font-size:14px;cursor:pointer;background:transparent;color:var(--ink)}
.btn.pri{background:var(--magenta);color:#fff;border-color:var(--magenta)}
.src{font-family:ui-monospace,monospace;font-size:10px;color:var(--soft);margin-top:10px}
.x{position:absolute;top:18px;right:20px;color:#fff;font-size:30px;cursor:pointer;background:0;border:0;z-index:51}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:var(--ink);color:var(--paper);padding:10px 18px;border-radius:999px;font-size:13px;opacity:0;transition:opacity .2s;z-index:60}
.toast.on{opacity:1}
</style></head><body>
<header><div class="bar">
<a class="logo" href="/">M<b>0</b>RM<span style="color:var(--orange)"> Play</span></a>
<div class="search"><span>⌕</span><input id="q" placeholder="作品・タグを検索" autocomplete="off"></div>
<div class="tabs"><button class="tab on" data-sort="hot">HOT</button><button class="tab" data-sort="new">NEW</button></div>
<a href="/upload" class="tab" style="text-decoration:none;background:var(--magenta);color:#fff;border-color:var(--magenta)">＋投稿</a>
</div><div class="chips" id="chips"></div></header>
<main><div class="grid" id="grid"></div><div class="empty" id="empty" style="display:none">見つかりませんでした</div><div class="sentinel" id="sentinel"></div></main>
<div class="ov" id="ov"><button class="x" id="x">×</button><div class="modal" id="modal"></div></div>
<div class="toast" id="toast"></div>
<script>
const grid=document.getElementById('grid'),chips=document.getElementById('chips'),qEl=document.getElementById('q');
let sort='hot',q='',tag='',offset=0,loading=false,done=false,seen=new Set();
function uid(){let u=localStorage.getItem('morm_play_uid');if(!u){u='m0r'+Math.random().toString(36).slice(2,12);localStorage.setItem('morm_play_uid',u);}return localStorage.getItem('morm_m0r')||u;}
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('on');setTimeout(()=>t.classList.remove('on'),1600);}
function nfmt(n){return n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?(n/1e3).toFixed(1)+'k':n;}
function reset(){offset=0;done=false;seen=new Set();grid.innerHTML='';document.getElementById('empty').style.display='none';load();}
async function load(){
  if(loading||done)return;loading=true;
  const u=`/api/feed?sort=${sort}&q=${encodeURIComponent(q)}&tag=${encodeURIComponent(tag)}&offset=${offset}&limit=24&uid=${encodeURIComponent(uid())}`;
  const d=await fetch(u).then(r=>r.json());
  if(offset===0&&d.items.length===0)document.getElementById('empty').style.display='block';
  for(const it of d.items){if(seen.has(it.id))continue;seen.add(it.id);grid.appendChild(cardEl(it));}
  if(d.next==null)done=true;else offset=d.next;
  loading=false;
}
function cardEl(it){
  const ar={portrait:[3,4],square:[1,1],landscape:[16,9]}[it.ar]||[3,4];
  const c=document.createElement('div');c.className='card';
  c.innerHTML=`<img class="thumb" loading="lazy" style="aspect-ratio:${ar[0]}/${ar[1]}" src="${it.thumb}">
  <div class="meta"><p class="t">${esc(it.title)}</p>
  <div class="r"><span class="u">${esc(it.uploader)}</span>
  <button class="like ${it.liked?'on':''}" data-id="${it.id}">♥ <span>${nfmt(it.likes)}</span></button></div></div>`;
  c.querySelector('.thumb').onclick=()=>open(it.id);
  c.querySelector('.t').onclick=()=>open(it.id);
  c.querySelector('.like').onclick=e=>{e.stopPropagation();like(it.id,e.currentTarget);};
  return c;
}
function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML;}
async function like(id,btn){
  const d=await fetch('/api/like',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({id,account:uid()})}).then(r=>r.json());
  if(d.error)return;
  btn.classList.toggle('on',d.liked);btn.querySelector('span').textContent=nfmt(d.likes);
}
let hls=null;
async function open(id){
  const d=await fetch('/api/content/'+id+'?uid='+encodeURIComponent(uid())).then(r=>r.json());
  if(d.error){toast('読み込めません');return;}
  const m=document.getElementById('modal');
  m.innerHTML=`<video id="pv" controls autoplay playsinline muted></video><div class="mbody">
  <h3>${esc(d.title)}</h3>
  <div class="r" style="color:var(--soft);font-size:12px">${esc(d.uploader)} ・ ${nfmt(d.views)} 回視聴</div>
  <div class="mtags">${d.tags.map(t=>`<span class="mtag">#${esc(t)}</span>`).join('')}</div>
  <div class="mact"><button class="btn pri" id="ml">♥ いいね <span>${nfmt(d.likes)}</span></button>
  <button class="btn" id="ms">シェア</button></div>
  <div class="src">配信元 = MORM（住宅edge・秘匿プロキシ経由）</div></div>`;
  document.getElementById('ov').classList.add('on');
  const ml=document.getElementById('ml');if(d.liked)ml.classList.add('on');
  ml.onclick=()=>like(id,ml);
  document.getElementById('ms').onclick=()=>share(id,d.title);
  const v=document.getElementById('pv'),src='/m/'+id+'/master.m3u8';
  if(window.Hls&&Hls.isSupported()){hls=new Hls();hls.loadSource(src);hls.attachMedia(v);
    hls.on(Hls.Events.MANIFEST_PARSED,()=>v.play().catch(()=>{}));}
  else if(v.canPlayType('application/vnd.apple.mpegurl')){v.src=src;}
}
function share(id,title){
  const url=location.origin+'/watch?id='+id;
  if(navigator.share){navigator.share({title:'MORM Play — '+title,url}).catch(()=>{});}
  else{navigator.clipboard.writeText(url).then(()=>toast('リンクをコピーしました'));}
}
function closeM(){document.getElementById('ov').classList.remove('on');
  if(hls){hls.destroy();hls=null;}document.getElementById('modal').innerHTML='';}
document.getElementById('x').onclick=closeM;
document.getElementById('ov').onclick=e=>{if(e.target.id==='ov')closeM();};
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));t.classList.add('on');
  sort=t.dataset.sort;reset();});
let qt;qEl.oninput=()=>{clearTimeout(qt);qt=setTimeout(()=>{q=qEl.value.trim();reset();},280);};
new IntersectionObserver(es=>{if(es[0].isIntersecting)load();}).observe(document.getElementById('sentinel'));
fetch('/api/tags').then(r=>r.json()).then(ts=>{
  const all=document.createElement('button');all.className='chip on';all.textContent='すべて';
  all.onclick=()=>{tag='';document.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));all.classList.add('on');reset();};
  chips.appendChild(all);
  ts.tags.forEach(t=>{const c=document.createElement('button');c.className='chip';c.textContent='#'+t;
    c.onclick=()=>{tag=t;document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));c.classList.add('on');reset();};
    chips.appendChild(c);});});
// deep-link /watch?id=
const p=new URLSearchParams(location.search);
load();if(p.get('id'))setTimeout(()=>open(p.get('id')),300);
</script></body></html>"""

# 縦スワイプ自動再生フィード(TikTok型)を外部ファイルで上書き可能に(あればそちら優先)
_idx_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
if os.path.exists(_idx_file):
    with open(_idx_file, encoding="utf-8") as _f:
        INDEX_HTML = _f.read()

UPLOAD_HTML = r"""<!doctype html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>投稿 — MORM Play</title>
<style>
:root{--paper:#F4F2EA;--card:#FBFAF4;--ink:#0C0C0E;--soft:#4A4A4E;--line:#0C0C0E;
--blue:#1E37E6;--magenta:#EC1E79;--orange:#FF4A17;--green:#0EA24A}
@media(prefers-color-scheme:dark){:root{--paper:#0C0C0E;--card:#151517;--ink:#F4F2EA;--soft:#B7B7B0;--line:#F4F2EA;--blue:#4A5CFF;--magenta:#FF3E93;--orange:#FF6A3D;--green:#22C466}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Helvetica Neue",Helvetica,Arial,"Hiragino Kaku Gothic ProN",sans-serif}
header{position:sticky;top:0;background:var(--paper);border-bottom:1px solid var(--line);padding:14px 18px;display:flex;align-items:center;gap:14px}
.logo{font-weight:900;font-size:20px;letter-spacing:-.04em;color:var(--magenta);text-decoration:none}
.logo b{color:var(--blue)}
.back{margin-left:auto;font-size:13px;color:var(--ink);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:7px 14px}
main{max-width:640px;margin:20px auto 80px;padding:0 16px}
.acct{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:18px}
.acct .row{display:flex;justify-content:space-between;align-items:center;gap:10px}
.addr{font-family:ui-monospace,monospace;font-size:12px;color:var(--soft);word-break:break-all}
.badge{font-family:ui-monospace,monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase;border:1px solid var(--line);border-radius:999px;padding:4px 10px}
.lim{margin-top:10px;font-size:13px;color:var(--soft);line-height:1.6}
.lim b{color:var(--ink)}
.stake{margin-top:10px;font-size:12px;color:var(--soft);border-top:1px dashed var(--line);padding-top:10px}
label{display:block;font-weight:700;font-size:13px;margin:16px 0 6px}
input[type=text],textarea,select{width:100%;border:1px solid var(--line);border-radius:10px;padding:11px 13px;background:var(--paper);color:var(--ink);font:inherit;font-size:15px}
textarea{min-height:80px;resize:vertical}
.drop{border:2px dashed var(--line);border-radius:14px;padding:26px;text-align:center;color:var(--soft);cursor:pointer;background:var(--card)}
.drop.has{border-style:solid;color:var(--ink)}
video.prev{width:100%;max-height:280px;border-radius:12px;margin-top:12px;background:#000;display:none}
.submit{width:100%;margin-top:22px;border:0;border-radius:999px;padding:15px;font-weight:800;font-size:16px;background:var(--magenta);color:#fff;cursor:pointer}
.submit:disabled{opacity:.5;cursor:not-allowed}
.msg{margin-top:14px;padding:12px 14px;border-radius:10px;font-size:14px;display:none}
.msg.err{background:rgba(236,30,121,.12);color:var(--magenta);display:block}
.msg.ok{background:rgba(14,162,74,.14);color:var(--green);display:block}
.msg.info{background:var(--card);border:1px solid var(--line);color:var(--soft);display:block}
h3{margin:34px 0 10px;font-size:16px}
.mine{display:flex;flex-direction:column;gap:8px}
.mi{display:flex;align-items:center;gap:10px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:9px 12px;font-size:13px}
.mi img{width:44px;height:56px;object-fit:cover;border-radius:6px}
.st{margin-left:auto;font-family:ui-monospace,monospace;font-size:10px;padding:3px 8px;border-radius:999px}
.st.approved{background:rgba(14,162,74,.16);color:var(--green)}
.st.pending_review{background:rgba(255,74,23,.16);color:var(--orange)}
.st.rejected{background:rgba(236,30,121,.16);color:var(--magenta)}
.st.pending{background:rgba(30,55,230,.16);color:var(--blue)}
</style></head><body>
<header><a class="logo" href="/">M<b>0</b>RM<span style="color:var(--orange)"> Play</span></a>
<a class="back" href="/">← フィード</a></header>
<main>
<div id="ctx" style="display:none;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:14px;font-size:13.5px;line-height:1.5"></div>
<div class="acct" id="acct"><div class="row"><span class="addr" id="addr">ウォレット準備中…</span>
<span class="badge" id="tier">—</span></div>
<div class="lim" id="lim"></div><div class="stake" id="stake"></div></div>

<label>動画ファイル</label>
<div class="drop" id="drop">タップして動画を選択（自動でHLSエンコードされます）</div>
<input type="file" id="file" accept="video/*" style="display:none">
<div class="lim" id="spec" style="margin-top:8px">対応形式: MP4 / MOV / WebM / MKV など一般的な動画（アダプティブHLS 1080/720/480/360 に自動変換）。最大 <b>512MB</b>、長さは信頼レベル上限まで。</div>
<video class="prev" id="prev" controls muted playsinline></video>

<label>タイトル</label><input type="text" id="title" maxlength="120" placeholder="作品タイトル">
<label>概要（リンクは信頼レベルにより制限されます）</label><textarea id="desc" maxlength="2000" placeholder="説明・情報…"></textarea>
<label>タグ（カンマ区切り・最大8）</label><input type="text" id="tags" placeholder="music, shorts, art">
<label>アスペクト比</label><select id="ar"><option value="portrait">縦型 3:4</option><option value="square">正方形 1:1</option><option value="landscape">横型 16:9</option></select>

<button class="submit" id="go" disabled>投稿する</button>
<div class="msg" id="msg"></div>

<h3>マイ投稿</h3><div class="mine" id="mine"><div class="lim">まだ投稿がありません</div></div>
</main>
<script>
const $=id=>document.getElementById(id);
const esc=s=>{const d=document.createElement('div');d.textContent=s||'';return d.innerHTML;};
const hex=b=>[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('');
const _p=new URLSearchParams(location.search);
const REMIX=(_p.get('remix')||'').trim();const CHAL=(_p.get('challenge')||'').trim();
async function renderCtx(){if(!REMIX&&!CHAL)return;let h='';
  if(CHAL){try{const c=await fetch('/api/challenge/'+encodeURIComponent(CHAL)).then(r=>r.json());if(c&&!c.error)h+=`🏆 チャレンジ「<b>${esc(c.title)}</b>」に参加して投稿します`;}catch(e){}}
  if(REMIX){try{const r=await fetch('/api/content/'+encodeURIComponent(REMIX)).then(r=>r.json());if(r&&!r.error)h+=(h?'<br>':'')+`🔁 「<b>${esc(r.title)}</b>」のリミックスとして投稿します`;}catch(e){}}
  if(h){$('ctx').innerHTML=h;$('ctx').style.display='block';}}
// canonical: Python json.dumps(sort_keys,separators=(',',':'),ensure_ascii=False) と一致
function canon(v){
  if(v===null)return'null';
  if(Array.isArray(v))return'['+v.map(canon).join(',')+']';
  if(typeof v==='object')return'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canon(v[k])).join(',')+'}';
  return JSON.stringify(v);
}
// --- IndexedDB (play.morm.one origin の端末鍵) ---
function idb(){return new Promise((res,rej)=>{const r=indexedDB.open('morm-play-wallet',1);
  r.onupgradeneeded=()=>r.result.createObjectStore('kv');r.onsuccess=()=>res(r.result);r.onerror=()=>rej(r.error);});}
async function kvGet(k){const d=await idb();return new Promise((res)=>{const t=d.transaction('kv').objectStore('kv').get(k);t.onsuccess=()=>res(t.result);t.onerror=()=>res(null);});}
async function kvSet(k,v){const d=await idb();return new Promise((res)=>{const t=d.transaction('kv','readwrite').objectStore('kv').put(v,k);t.onsuccess=()=>res();});}
let KEY=null,PUBHEX=null,ME=null;
async function wallet(){
  let pk=await kvGet('pkcs8'),pub=await kvGet('pubraw');
  if(!pk||!pub){
    const kp=await crypto.subtle.generateKey({name:'Ed25519'},true,['sign','verify']);
    pk=await crypto.subtle.exportKey('pkcs8',kp.privateKey);
    pub=new Uint8Array(await crypto.subtle.exportKey('raw',kp.publicKey));
    await kvSet('pkcs8',pk);await kvSet('pubraw',pub);
  }
  KEY=await crypto.subtle.importKey('pkcs8',pk,{name:'Ed25519'},false,['sign']);
  PUBHEX=hex(pub);
  ME=await fetch('/api/me?pub='+PUBHEX).then(r=>r.json());
  renderAcct();
  // Play識別子をlocalStorageにも（いいね等で流用）
  localStorage.setItem('morm_m0r',ME.m0r);
}
async function sign(bytes){return new Uint8Array(await crypto.subtle.sign({name:'Ed25519'},KEY,bytes));}
function renderAcct(){
  $('addr').textContent=ME.m0r;
  $('tier').textContent='T'+ME.tier+' '+ME.tier_label;
  const L=ME.limits;
  $('lim').innerHTML=`本日の投稿 <b>${ME.posts_today}/${L.posts_day>=100000?'∞':L.posts_day}</b>　`+
    `最大尺 <b>${L.max_dur}s</b>　リンク <b>${{none:'不可',allowlist:'許可先のみ',all:'可'}[L.links]}</b>　コメント <b>${L.comments_day}/日</b>`;
  $('stake').innerHTML=`ステークで上限解放: <b>${ME.stake_next.t2.toLocaleString()} MORM</b> で信頼(T2)相当 / `+
    `<b>${ME.stake_next.unlimited.toLocaleString()} MORM</b> で無制限（違反なければ返却）`;
  $('go').disabled=!selFile;
}
// --- file select ---
let selFile=null,selDur=0;
$('drop').onclick=()=>$('file').click();
const MAXB=512*1024*1024;
$('file').onchange=e=>{const f=e.target.files[0];if(!f)return;
  const msg=$('msg');msg.className='msg';
  if(!f.type.startsWith('video/')){msg.className='msg err';msg.textContent='動画ファイルを選択してください';return;}
  if(f.size>MAXB){msg.className='msg err';msg.textContent='ファイルが大きすぎます（最大512MB）';return;}
  selFile=f;
  $('drop').classList.add('has');$('drop').textContent=f.name+' ('+(f.size/1e6).toFixed(1)+'MB)';
  const v=$('prev');v.src=URL.createObjectURL(f);v.style.display='block';
  v.onloadedmetadata=()=>{selDur=Math.round(v.duration||0);
    $('ar').value=v.videoWidth<v.videoHeight?'portrait':v.videoWidth>v.videoHeight?'landscape':'square';
    const lim=ME&&ME.limits.max_dur;
    if(lim&&selDur>lim){msg.className='msg err';
      msg.textContent=`この信頼レベルでは最大 ${lim}s（選択: ${selDur}s）。ステークで上限解放できます。`;
      $('go').disabled=true;}
    else{msg.className='msg';msg.textContent='';$('go').disabled=!ME;}};
  if(ME)$('go').disabled=false;};
function extractLinks(t){return(t.match(/https?:\/\/[^\s]+/g)||[]);}
// --- submit ---
$('go').onclick=async()=>{
  const msg=$('msg');msg.className='msg info';msg.textContent='署名して投稿中…';$('go').disabled=true;
  try{
    const desc=$('desc').value.trim();
    const payload={title:$('title').value.trim()||'untitled',description:desc,
      tags:$('tags').value.split(',').map(s=>s.trim()).filter(Boolean).slice(0,8),
      ar:$('ar').value,duration:selDur,links:extractLinks(desc)};
    if(REMIX)payload.remix_of=REMIX;
    if(CHAL)payload.challenge=CHAL;
    const nonce=Date.now()+'-'+Math.random().toString(36).slice(2,8);
    const env={kind:'upload.init',sender:PUBHEX,nonce,payload};
    const sig=hex(await sign(new TextEncoder().encode(canon(env))));
    const init=await fetch('/api/upload/init',{method:'POST',headers:{'content-type':'application/json'},
      body:JSON.stringify({...env,sig})}).then(r=>r.json());
    if(init.error){msg.className='msg err';msg.textContent=(init.gate?'⛔ ':'')+init.error;$('go').disabled=false;return;}
    msg.className='msg info';msg.textContent='エンコード中…（数秒）';
    const up=await fetch('/api/upload/'+init.id+'/media?token='+init.token,{method:'POST',
      headers:{'content-type':'application/octet-stream'},body:selFile}).then(r=>r.json());
    if(up.error){msg.className='msg err';msg.textContent=up.error+(up.gate?'（ゲート）':'');$('go').disabled=false;return;}
    msg.className='msg ok';
    msg.innerHTML=`✅ 投稿を受け付けました（実尺 ${up.duration||selDur}s）。AI審査中です — 通過後に公開されます。<br>下の「マイ投稿」で状態が更新されます。`;
    pollMine=8;  // しばらく mine を追跡
    $('title').value='';$('desc').value='';$('tags').value='';selFile=null;selDur=0;
    $('drop').classList.remove('has');$('drop').textContent='タップして動画を選択';$('prev').style.display='none';
    ME=await fetch('/api/me?pub='+PUBHEX).then(r=>r.json());renderAcct();loadMine();
  }catch(e){msg.className='msg err';msg.textContent='エラー: '+e;$('go').disabled=false;}
};
async function loadMine(){
  if(!ME||!PUBHEX)return;const d=await fetch('/api/mine?pub='+PUBHEX).then(r=>r.json());
  if(!d.items||!d.items.length)return;
  $('mine').innerHTML=d.items.map(it=>`<div class="mi"><img src="${it.thumb}">
    <div><div style="font-weight:700">${it.title.replace(/</g,'&lt;')}</div>
    <div style="color:var(--soft);font-size:11px">♥${it.likes} ・ ${it.views}回</div></div>
    <span class="st ${it.status}">${{approved:'公開中',pending:'AI審査中',pending_review:'審査中(人手)',rejected:'却下',shadow:'制限'}[it.status]||it.status}</span></div>`).join('');
}
let pollMine=0;
setInterval(()=>{if(pollMine>0){pollMine--;loadMine();}},4000);
(async()=>{
  if(!window.crypto||!crypto.subtle){$('msg').className='msg err';$('msg').textContent='この端末はWebCrypto非対応です';return;}
  try{await wallet();$('go').disabled=!selFile;loadMine();renderCtx();}
  catch(e){$('msg').className='msg err';$('msg').textContent='ウォレット初期化に失敗（Ed25519非対応ブラウザの可能性）: '+e;}
})();
</script></body></html>"""

ADMIN_MOD_HTML = r"""<!doctype html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>モデレーション — MORM Play</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.13/dist/hls.min.js"></script>
<style>
:root{--paper:#0C0C0E;--card:#151517;--ink:#F4F2EA;--soft:#B7B7B0;--line:#2a2a2e;
--blue:#4A5CFF;--magenta:#FF3E93;--orange:#FF6A3D;--green:#22C466}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Helvetica Neue",Arial,sans-serif}
header{position:sticky;top:0;background:var(--paper);border-bottom:1px solid var(--line);padding:12px 18px;display:flex;align-items:center;gap:14px;z-index:10}
.logo{font-weight:900;font-size:18px;color:var(--magenta)}
.logo b{color:var(--blue)}
.stat{margin-left:auto;font-family:ui-monospace,monospace;font-size:12px;color:var(--soft)}
.stat b{color:var(--ink)}
input{border:1px solid var(--line);border-radius:8px;padding:8px 12px;background:var(--card);color:var(--ink);font:inherit}
main{max-width:1100px;margin:18px auto;padding:0 14px;display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
.card video{width:100%;max-height:360px;background:#000;aspect-ratio:9/16;object-fit:contain}
.body{padding:12px 14px;flex:1;display:flex;flex-direction:column;gap:8px}
.t{font-weight:700;font-size:15px}
.meta{font-size:12px;color:var(--soft);font-family:ui-monospace,monospace;word-break:break-all}
.badges{display:flex;gap:6px;flex-wrap:wrap}
.b{font-size:11px;font-family:ui-monospace,monospace;border-radius:999px;padding:3px 9px;border:1px solid var(--line)}
.b.cat{color:var(--blue);border-color:var(--blue)}
.b.r18{color:var(--magenta);border-color:var(--magenta)}
.b.sfw{color:var(--green);border-color:var(--green)}
.b.rev{color:var(--orange);border-color:var(--orange)}
.desc{font-size:12px;color:var(--soft);white-space:pre-wrap;max-height:60px;overflow:auto}
.labels{display:flex;flex-direction:column;gap:3px;font-size:10px;font-family:ui-monospace,monospace}
.lb{display:flex;align-items:center;gap:6px}.lb span{width:96px;color:var(--soft)}
.bar{flex:1;height:5px;background:#2a2a2e;border-radius:3px;overflow:hidden}
.bar i{display:block;height:100%}
.act{display:flex;gap:8px;margin-top:auto;padding-top:6px}
.act button{flex:1;border:0;border-radius:999px;padding:10px;font-weight:800;font-size:13px;cursor:pointer}
.ok{background:var(--green);color:#04140a}.no{background:var(--magenta);color:#fff}
.empty{grid-column:1/-1;text-align:center;color:var(--soft);padding:60px}
.gate{grid-column:1/-1;text-align:center;padding:40px}
</style></head><body>
<header><span class="logo">M<b>0</b>RM モデレーション</span>
<span class="stat" id="stat"></span></header>
<main id="grid"><div class="gate" id="gate">
<p>ADMIN_TOKEN を入力してください</p><input id="tok" type="password" placeholder="admin token" style="width:280px">
<button onclick="saveTok()" style="margin-left:8px;padding:9px 16px;border:0;border-radius:8px;background:var(--blue);color:#fff;cursor:pointer">開く</button>
</div></main>
<script>
const grid=document.getElementById('grid');
let TOK=sessionStorage.getItem('mod_tok')||'';
function saveTok(){TOK=document.getElementById('tok').value.trim();sessionStorage.setItem('mod_tok',TOK);load();}
const LB=['illegal','csam_risk','real_violence','scam','spam','nonconsensual','adult','nudity'];
function col(v){return v>=0.7?'var(--magenta)':v>=0.4?'var(--orange)':'var(--green)';}
function esc(s){const d=document.createElement('div');d.textContent=s||'';return d.innerHTML;}
async function decide(id,decision,btn){
  btn.disabled=true;
  const r=await fetch('/api/admin/moderation/decide',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({token:TOK,id,decision})}).then(r=>r.json());
  if(r.ok){const c=document.getElementById('c_'+id);if(c)c.remove();}else{btn.disabled=false;alert(r.error||'失敗');}
}
async function load(){
  if(!TOK)return;
  const d=await fetch('/api/admin/moderation/queue',{headers:{'X-Admin-Token':TOK}}).then(r=>r.json());
  if(d.error){grid.innerHTML='<div class="gate">認証失敗（トークンを確認）<br><input id="tok" type="password" placeholder="admin token"><button onclick="saveTok()">再試行</button></div>';return;}
  document.getElementById('stat').innerHTML=`人手待ち <b>${d.items.filter(i=>i.status==='pending_review').length}</b> ／ AI処理中 <b>${d.in_ai}</b>`;
  if(!d.items.length){grid.innerHTML='<div class="empty">✓ 審査待ちはありません（AI処理中: '+d.in_ai+'）</div>';return;}
  grid.innerHTML=d.items.map(it=>{
    const ai=it.status==='pending';
    const labels=LB.map(k=>{const v=(it.labels&&it.labels[k])||0;return `<div class="lb"><span>${k}</span><div class="bar"><i style="width:${Math.round(v*100)}%;background:${col(v)}"></i></div></div>`;}).join('');
    return `<div class="card" id="c_${it.id}">
      <video id="v_${it.id}" muted controls playsinline preload="none"></video>
      <div class="body"><div class="t">${esc(it.title)}</div>
      <div class="badges"><span class="b cat">${it.category||'?'}</span>
        <span class="b ${it.rating==='r18'?'r18':'sfw'}">${(it.rating||'sfw').toUpperCase()}</span>
        <span class="b rev">${ai?'AI処理中':'人手待ち'}</span>
        <span class="b">${it.duration||0}s</span></div>
      <div class="meta">${esc(it.uploader)}</div>
      ${it.description?`<div class="desc">${esc(it.description)}</div>`:''}
      <div class="labels">${labels}</div>
      <div class="act"><button class="ok" onclick="decide('${it.id}','approved',this)">承認</button>
      <button class="no" onclick="decide('${it.id}','rejected',this)">却下</button></div></div></div>`;
  }).join('');
  // lazy attach hls players
  // ★admin審査プレビュー: X-Admin-Token を全HLSリクエストに付与(pending/未approvedも視聴可・token-in-URL回避)。
  // 注: Safari native HLS(v.src)はヘッダ付与不可 → pending審査はhls.js対応ブラウザ(Chrome/FF)で。
  const att=(v,src)=>{if(v._h)return;if(window.Hls&&Hls.isSupported()){const h=new Hls({xhrSetup:x=>x.setRequestHeader('X-Admin-Token',TOK)});v._h=h;h.loadSource(src);h.attachMedia(v);}else{v.src=src;}};
  d.items.forEach(it=>{const v=document.getElementById('v_'+it.id);if(!v)return;const src='/m/'+it.id+'/master.m3u8';
    v.addEventListener('play',()=>att(v,src),{once:true});
    v.addEventListener('click',()=>att(v,src),{once:true});
  });
}
if(TOK)load();
setInterval(()=>{if(TOK)load();},15000);
</script></body></html>"""

# --- HTTP handler ------------------------------------------------------------

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "MORMPlay/1.0"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json", extra=None, head=False):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not head and self.command != "HEAD":
            self.wfile.write(b)

    def _json(self, code, obj, extra=None):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8", extra)

    def _q(self):
        q = {}
        if "?" in self.path:
            for kv in self.path.split("?", 1)[1].split("&"):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    q[k] = urllib.parse.unquote_plus(v)
        return q

    def _iph(self):
        """クライアントIPをソルト付きハッシュで(生IPは保存しない)。CF/nginx経由のヘッダ優先。"""
        ip = (self.headers.get("CF-Connecting-IP") or "").strip()
        if not ip:
            xff = self.headers.get("X-Forwarded-For") or ""
            ip = xff.split(",")[0].strip() if xff else ""
        if not ip:
            ip = (self.headers.get("X-Real-IP") or "").strip()
        if not ip and self.client_address:
            ip = self.client_address[0]
        return _ip_hash(ip)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range,Content-Type")
        self.end_headers()

    def _age_cookie_m0r(self):
        for part in (self.headers.get("Cookie", "") or "").split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                if k == "morm_age":
                    return check_age_token(v)
        return None

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        q = self._q()
        # --- secrecy proxy ---
        m = re.match(r"^/m/([A-Za-z0-9]+)/(.+)$", path)
        if m:
            return self._proxy(m.group(1), m.group(2))
        # --- api ---
        if path == "/api/feed":
            zone = q.get("zone", "sfw")
            if zone == "adult":  # R18ゾーンは年齢認証必須(cookie or 認証済みm0r)
                if not (self._age_cookie_m0r() or is_age_verified(q.get("uid", ""))):
                    return self._json(403, {"error": "age_verification_required", "adult": True})
            return self._json(200, feed(q.get("sort", "hot"), q.get("q", ""), q.get("tag", ""),
                                        int(q.get("limit", "24")), int(q.get("offset", "0")), zone,
                                        q.get("uid", ""), q.get("follow", "")))
        m = re.match(r"^/api/profile/(m0r[A-Za-z0-9]+)$", path)
        if m:
            return self._json(200, creator_profile(m.group(1), q.get("viewer", "")))
        if path == "/api/referral/stats":
            m0r = q.get("m0r", "")
            if not m0r.startswith("m0r"):
                return self._json(400, {"error": "m0r required"})
            settle_async()   # 実活動済みの成立/報酬を反映(非同期)
            return self._json(200, referral_stats(m0r))
        if path == "/api/tags":
            return self._json(200, {"tags": popular_tags()})
        if path == "/api/challenges":
            return self._json(200, {"items": list_challenges(q.get("status", "active"))})
        m = re.match(r"^/api/challenge/([A-Za-z0-9\-]+)$", path)
        if m:
            d = challenge_detail(m.group(1), q.get("sort", "hot"), q.get("viewer", ""))
            return self._json(200, d) if d else self._json(404, {"error": "not found"})
        m = re.match(r"^/api/remixes/([A-Za-z0-9]+)$", path)
        if m:
            return self._json(200, list_remixes(m.group(1)))
        m = re.match(r"^/api/story/([A-Za-z0-9]+)$", path)
        if m:
            d = story_node(m.group(1), q.get("uid"))
            return self._json(200, d) if d else self._json(404, {"error": "not found"})
        m = re.match(r"^/api/comments/([A-Za-z0-9]+)$", path)
        if m:
            return self._json(200, {"items": list_comments(m.group(1))})
        if path == "/api/earnings":
            # ★IDOR封鎖: 生の m0r(公開アドレス)ではなく pubkey を要求(本人のみ閲覧可・/api/me と同型)。
            try:
                m0r = pub_to_m0r(q.get("pub", ""))
            except Exception:
                return self._json(400, {"error": "pub required (32-byte hex)"})
            return self._json(200, earnings(m0r))
        m = re.match(r"^/api/content/([A-Za-z0-9]+)$", path)
        if m:
            # ★GETでは views を増やさない(有効再生=視聴ビーコンの閾値超えのみ計上)
            c = get_content(m.group(1), q.get("uid"))
            return self._json(200, c) if c else self._json(404, {"error": "not found"})
        m = re.match(r"^/cover/([A-Za-z0-9]+)\.jpg$", path)
        if m:
            jpg = get_cover(m.group(1))
            if not jpg:
                return self._json(404, {"error": "no cover"})
            return self._send(200, jpg, "image/jpeg", {"Cache-Control": "public,max-age=300"})
        if path == "/thumb" or re.match(r"^/thumb/[A-Za-z0-9]+\.svg$", path):
            cid = path.split("/")[-1].replace(".svg", "")
            c = get_content(cid)
            svg = thumb_svg(cid, c["title"] if c else "")
            return self._send(200, svg, "image/svg+xml", {"Cache-Control": "public,max-age=86400"})
        if path == "/api/me":
            try:
                m0r = pub_to_m0r(q.get("pub", ""))
            except Exception:
                return self._json(400, {"error": "pub required (32-byte hex)"})
            return self._json(200, account_public(ensure_account(m0r)))
        if path == "/api/mine":
            # ★IDOR封鎖: 自投稿(status/rating含む=非公開のモデレーション状態)は本人のみ(/api/me と同型)。
            try:
                m0r = pub_to_m0r(q.get("pub", ""))
            except Exception:
                return self._json(400, {"error": "pub required (32-byte hex)"})
            conn = _db()
            rows = conn.execute("SELECT * FROM content WHERE uploader=? AND status!='reserved'"
                                " ORDER BY created_at DESC LIMIT 50", (m0r,)).fetchall()
            conn.close()
            return self._json(200, {"items": [
                {**_row_public(r), "status": r["status"], "rating": r["rating"]} for r in rows]})
        if path == "/api/admin/moderation/queue":
            # token は X-Admin-Token ヘッダ優先(URL/ログ/Referer 露出回避)。q.get はfallback(後方互換)。
            if not ADMIN_TOKEN or (self.headers.get("X-Admin-Token") or q.get("token")) != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            conn = _db()
            rows = conn.execute("SELECT * FROM content WHERE status IN ('pending_review','pending')"
                                " ORDER BY created_at DESC LIMIT 100").fetchall()
            npend = conn.execute("SELECT COUNT(*) FROM content WHERE status='pending'").fetchone()[0]
            conn.close()
            def _q_item(r):
                try:
                    labels = json.loads(r["mod_labels"] or "{}")
                except Exception:
                    labels = {}
                tg = [t for t in r["tags"].split(",") if t]
                cat = next((t for t in tg if t in _CATS), (tg[-1] if tg else "?"))
                return {**_row_public(r), "status": r["status"], "description": r["description"],
                        "rating": r["rating"], "mod_score": r["mod_score"], "labels": labels,
                        "duration": r["duration"], "uploader": r["uploader"], "category": cat}
            return self._json(200, {"items": [_q_item(r) for r in rows], "in_ai": npend})
        if path == "/api/mod/pull":  # worker用
            # token は X-Admin-Token ヘッダ優先(URL/ログ/Referer 露出回避)。q.get はfallback(後方互換)。
            if not ADMIN_TOKEN or (self.headers.get("X-Admin-Token") or q.get("token")) != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            return self._json(200, {"items": pull_pending(int(q.get("limit", "1")))})
        if path == "/api/admin/catalog":  # 再キャプション等の一括処理用(play_cid込み)
            # token は X-Admin-Token ヘッダ優先(URL/ログ/Referer 露出回避)。q.get はfallback(後方互換)。
            if not ADMIN_TOKEN or (self.headers.get("X-Admin-Token") or q.get("token")) != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            conn = _db()
            st = q.get("status", "approved")
            sql = ("SELECT id,play_cid,title,tags,rating,ar,uploader,status FROM content"
                   + ("" if st == "all" else " WHERE status=?") + " ORDER BY created_at DESC")
            rows = conn.execute(sql, () if st == "all" else (st,)).fetchall()
            conn.close()
            return self._json(200, {"items": [
                {"id": r["id"], "play_cid": r["play_cid"], "title": r["title"],
                 "tags": [t for t in r["tags"].split(",") if t], "rating": r["rating"],
                 "ar": r["ar"], "uploader": r["uploader"], "status": r["status"]} for r in rows]})
        if path == "/admin/moderation":
            return self._send(200, ADMIN_MOD_HTML, "text/html; charset=utf-8", {"Cache-Control": "no-store"})
        if path == "/upload":
            return self._send(200, UPLOAD_HTML, "text/html; charset=utf-8", {"Cache-Control": "no-store"})
        if path == "/health":
            with _lock:
                return self._json(200, {"ok": True, "healthy_edges": len(_state["healthy"]),
                                        "updated": _state["updated"]})
        if path in ("/", "/watch"):
            html = INDEX_HTML
            if os.path.exists(_idx_file):  # index.html を都度読込(編集を即反映・再起動不要)
                try:
                    with open(_idx_file, encoding="utf-8") as _f:
                        html = _f.read()
                except Exception:
                    pass
            return self._send(200, html, "text/html; charset=utf-8", {"Cache-Control": "no-store"})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        q = self._q()
        ln = int(self.headers.get("Content-Length", "0") or "0")
        # --- media upload (raw bytes, JSONではない) ---
        m = re.match(r"^/api/upload/([A-Za-z0-9]+)/media$", path)
        if m:
            return self._upload_media(m.group(1), q.get("token", ""))
        raw = self.rfile.read(ln) if ln else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except Exception:
            data = {}
        if path == "/api/upload/init":
            return self._upload_init(data)
        if path == "/api/admin/story/edge":  # グリッドチョイス: 分岐エッジの張り/更新/削除(v1オーサリング)
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            frm = (data.get("from") or "").strip()
            to = (data.get("to") or "").strip()
            if not frm or not to or frm == to:
                return self._json(400, {"error": "from/to required and must differ"})
            conn = _db()
            if data.get("op") == "delete":
                conn.execute("DELETE FROM story_edges WHERE from_cid=? AND to_cid=?", (frm, to))
                conn.commit()
                conn.close()
                return self._json(200, {"ok": True, "deleted": [frm, to]})
            n = conn.execute("SELECT COUNT(*) FROM content WHERE id IN (?,?)", (frm, to)).fetchone()[0]
            if n < 2:
                conn.close()
                return self._json(400, {"error": "from/to must be existing content ids"})
            conn.execute(
                "INSERT INTO story_edges(from_cid,to_cid,slot,label,cost,created_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(from_cid,to_cid) DO UPDATE SET slot=excluded.slot,label=excluded.label,cost=excluded.cost",
                (frm, to, int(data.get("slot", 0)), (data.get("label") or "")[:80],
                 max(0, int(data.get("cost", 0))), int(time.time())))
            conn.commit()
            conn.close()
            return self._json(200, {"ok": True, "node": story_node(frm)})
        if path == "/api/admin/set-stake":  # P5まで暫定: staked_morm/trust を手動設定
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            conn = _db()
            ensure_account(data["m0r"])
            if "staked_morm" in data:
                conn.execute("UPDATE accounts SET staked_morm=? WHERE m0r=?", (int(data["staked_morm"]), data["m0r"]))
            if "trust_score" in data:
                conn.execute("UPDATE accounts SET trust_score=? WHERE m0r=?", (int(data["trust_score"]), data["m0r"]))
            conn.commit()
            conn.close()
            return self._json(200, account_public(ensure_account(data["m0r"])))
        if path == "/api/admin/payout":  # 再生数・いいね数に応じた MORM 実配分(L1送金)
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            try:
                if data.get("m0r"):
                    return self._json(200, {**payout(data["m0r"]), "treasury": _treasury()["addr"]})
                # 全クリエイター(承認作品の投稿者)で pending>=min を配分
                conn = _db()
                creators = [r[0] for r in conn.execute(
                    "SELECT DISTINCT uploader FROM content WHERE status='approved'").fetchall()]
                conn.close()
                results = []
                for m in creators:
                    try:
                        r = payout(m)
                        if r.get("paid", 0) > 0:
                            results.append({"m0r": m, **r})
                    except Exception as e:
                        results.append({"m0r": m, "error": str(e)})
                return self._json(200, {"ok": True, "paid_count": len(results),
                                        "total_morm": sum(x.get("paid", 0) for x in results), "results": results})
            except Exception as e:
                return self._json(500, {"error": str(e)})
        if path == "/api/admin/referral/settle":  # 手動/cron: 成立・報酬をまとめて処理
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            return self._json(200, settle_referrals(int(data.get("limit", 50))))
        if path == "/api/admin/challenge/settle":  # 報酬プールを上位クリエイターへ配分
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            if not data.get("slug"):
                return self._json(400, {"error": "slug required"})
            return self._json(200, settle_challenge(data["slug"], data.get("pool"),
                                                    int(data.get("top", 3)), data.get("weights")))
        if path == "/api/admin/challenge/close":  # チャレンジ終了(status=closed)
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            conn = _db()
            conn.execute("UPDATE challenges SET status='closed' WHERE slug=?", (data.get("slug"),))
            n = conn.total_changes
            conn.commit()
            conn.close()
            return self._json(200, {"ok": True, "closed": n})
        if path == "/api/admin/dedup":  # 同一play_cidの重複を1本残し他をremoved(可逆)
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            dry = bool(data.get("dry"))
            conn = _db()
            rows = conn.execute("SELECT id,play_cid,views,likes,created_at,cover_ts"
                                " FROM content WHERE status='approved'").fetchall()
            groups = {}
            for r in rows:
                groups.setdefault(r["play_cid"], []).append(r)
            removed = []
            for pc, rs in groups.items():
                if len(rs) <= 1:
                    continue
                rs_sorted = sorted(rs, key=lambda r: (
                    1 if (r["cover_ts"] or 0) > 0 else 0, r["likes"] or 0,
                    r["views"] or 0, -(r["created_at"] or 0)), reverse=True)
                for r in rs_sorted[1:]:
                    removed.append(r["id"])
                    if not dry:
                        conn.execute("UPDATE content SET status='removed' WHERE id=?", (r["id"],))
            if not dry:
                conn.commit()
            conn.close()
            return self._json(200, {"ok": True, "dry": dry, "removed": len(removed),
                                    "distinct_kept": len(groups), "removed_ids": removed})
        if path == "/api/admin/recaption":  # 実フレームから起こしたタイトル/タグを書き戻す
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            cid = data.get("id")
            title = (data.get("title") or "").strip()[:80]
            tags = data.get("tags")
            if not cid or not title:
                return self._json(400, {"error": "id and title required"})
            conn = _db()
            if isinstance(tags, list):
                tg = ",".join(str(t).strip() for t in tags if str(t).strip())[:200]
                conn.execute("UPDATE content SET title=?, tags=? WHERE id=?", (title, tg, cid))
            else:
                conn.execute("UPDATE content SET title=? WHERE id=?", (title, cid))
            if data.get("rating") in ("sfw", "r15", "r18"):
                conn.execute("UPDATE content SET rating=? WHERE id=?", (data["rating"], cid))
            n = conn.total_changes
            conn.commit()
            conn.close()
            return self._json(200, {"ok": True, "updated": n, "id": cid, "title": title})
        if path == "/api/mod/verdict":  # worker が AI 判定を書き戻す
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            ok = apply_verdict(data.get("id"), data.get("verdict") or {})
            return self._json(200, {"ok": ok})
        if path == "/api/admin/moderation/decide":
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            cid, decision = data.get("id"), data.get("decision")
            if decision not in ("approved", "rejected"):
                return self._json(400, {"error": "decision must be approved|rejected"})
            conn = _db()
            conn.execute("UPDATE content SET status=? WHERE id=? AND status='pending_review'", (decision, cid))
            conn.execute("INSERT INTO moderation_log(target_type,target_id,model,score,labels,decision,reviewer,ts)"
                         " VALUES('content',?,'human',0,'{}',?,'admin',?)", (cid, decision, int(time.time())))
            conn.commit()
            conn.close()
            if decision == "approved":
                settle_async()   # 被招待者の実活動→紹介成立チェック
            return self._json(200, {"ok": True, "id": cid, "status": decision})
        if path == "/api/age/verify":  # 自己申告(生年月日)・署名必須 → age_verified + cookie
            m0r, payload = verify_signed(data, "age.verify")
            if not m0r:
                return self._json(400, {"error": payload})
            try:
                by = int(payload.get("birth_year"))
            except Exception:
                return self._json(400, {"error": "birth_year required"})
            age = time.gmtime().tm_year - by
            if age < 18 or age > 120:
                return self._json(403, {"error": "18歳以上である必要があります", "age": age})
            set_age_verified(m0r, by, "self")
            tok = make_age_token(m0r)
            return self._json(200, {"ok": True, "age_verified": True, "m0r": m0r},
                              extra={"Set-Cookie": f"morm_age={tok}; Path=/; Max-Age={AGE_TTL}; "
                                     "HttpOnly; Secure; SameSite=Lax"})
        if path == "/api/like":  # ★署名必須(ウォレット紐付)+レート制限。account=検証済みm0r
            m0r, payload = verify_signed(data, "like")
            if not m0r:
                return self._json(400, {"error": payload})
            iph = self._iph()
            if not _rl_allow("l:" + m0r, LIKE_IP_PER_MIN) or (iph and not _rl_allow("lip:" + iph, LIKE_IP_PER_MIN * 6)):
                return self._json(429, {"error": "rate limited"})
            cid = (payload.get("id") or "").strip()
            if not cid:
                return self._json(400, {"error": "id required"})
            res = toggle_like(cid, m0r, data.get("sig"))
            if res and res.get("liked"):   # 初回いいねのみ報酬(取消再いいねでは再取得不可=UNIQUE)
                res["awarded_points"] = grant_point(m0r, "like", cid)
            return self._json(200, res) if res else self._json(404, {"error": "not found"})
        if path == "/api/comment":  # ★署名必須化(ポイント報酬の整合性=なりすまし防止)
            m0r, payload = verify_signed(data, "comment")
            if not m0r:
                return self._json(400, {"error": payload})
            cid = (payload.get("id") or "").strip()
            text = payload.get("text", "")
            if not cid:
                return self._json(400, {"error": "id required"})
            iph = self._iph()
            if not _rl_allow("c:" + m0r, COMMENT_IP_PER_MIN) or (iph and not _rl_allow("cip:" + iph, COMMENT_IP_PER_MIN * 6)):
                return self._json(429, {"error": "rate limited"})
            res = add_comment(cid, m0r, text)
            if res.get("ok") and len((text or "").strip()) >= 3:  # 実コメント(3字以上)のみ報酬
                res["awarded_points"] = grant_point(m0r, "comment", cid)
            return self._json(200, res)
        if path == "/api/share":  # ★署名必須。自己申告ゆえ(account,share,content)恒久1回で厳しくdedup
            m0r, payload = verify_signed(data, "share")
            if not m0r:
                return self._json(400, {"error": payload})
            cid = (payload.get("id") or "").strip()
            if not cid:
                return self._json(400, {"error": "id required"})
            iph = self._iph()
            if not _rl_allow("s:" + m0r, COMMENT_IP_PER_MIN) or (iph and not _rl_allow("sip:" + iph, COMMENT_IP_PER_MIN * 6)):
                return self._json(429, {"error": "rate limited"})
            return self._json(200, {"ok": True, "awarded_points": grant_point(m0r, "share", cid)})
        if path == "/api/admin/points/settle":  # 手動でポイント集計・配分を実行(検証/運用)
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            return self._json(200, settle_points())
        if path == "/api/follow":  # フォロー/解除(署名必須=端末ウォレット)
            m0r, payload = verify_signed(data, "follow")
            if not m0r:
                return self._json(400, {"error": payload})
            iph = self._iph()
            if not _rl_allow("f:" + m0r, FOLLOW_IP_PER_MIN) or (iph and not _rl_allow("fip:" + iph, FOLLOW_IP_PER_MIN * 6)):
                return self._json(429, {"error": "rate limited"})
            to = (payload.get("to") or "").strip()
            res = toggle_follow(m0r, to, payload.get("op", "follow"))
            return self._json(400 if res.get("error") else 200, res)
        if path == "/api/profile":  # プロフィール編集(署名必須)
            m0r, payload = verify_signed(data, "set.profile")
            if not m0r:
                return self._json(400, {"error": payload})
            return self._json(200, set_profile(m0r, payload.get("display_name", ""),
                                               payload.get("bio", "")))
        if path == "/api/referral/attach":  # 招待コード紐付け(被招待者の署名必須・1回きり)
            m0r, payload = verify_signed(data, "referral.attach")
            if not m0r:
                return self._json(400, {"error": payload})
            res = attach_referral(m0r, (payload.get("code") or "").strip())
            return self._json(400 if res.get("error") else 200, res)
        if path == "/api/challenge/create":  # チャレンジ作成(admin=プール可 / 署名ユーザー=tier以上・pool不可)
            admin = bool(data.get("token") and ADMIN_TOKEN and data["token"] == ADMIN_TOKEN)
            if admin:
                creator = (data.get("creator") or "").strip()
                if not creator.startswith("m0r"):
                    return self._json(400, {"error": "creator (m0r) required"})
                pl, pool = data, data.get("reward_pool", 0)
            else:
                m0r, pl = verify_signed(data, "challenge.create")
                if not m0r:
                    return self._json(400, {"error": pl})
                acc = ensure_account(m0r)
                if effective_tier(acc) < CHALLENGE_MIN_TIER:
                    return self._json(403, {"gate": True,
                        "error": f"チャレンジ作成には信頼レベル T{CHALLENGE_MIN_TIER} 以上が必要です"})
                if not _rl_allow("chc:" + m0r, CHALLENGE_PER_DAY, window=86400):
                    return self._json(429, {"error": "本日の作成上限に達しました"})
                creator, pool = m0r, 0   # 資金移動を伴うプールは admin のみ
            res = create_challenge(creator, pl.get("title"), pl.get("description", ""),
                                   pl.get("ends_days", 0), pool)
            return self._json(400 if res.get("error") else 200, res)
        if path == "/api/watch":  # 視聴ビーコン(維持率+有効再生・dedup/レート制限)
            # 署名付き視聴(sig あり)= viewer を検証し view_by_other 報酬の対象に。
            # 未署名 = 従来通り uid の自己申告で view 計数のみ(無報酬)。
            verified = False
            if data.get("sig"):
                m0r, payload = verify_signed(data, "watch")
                if not m0r:
                    return self._json(400, {"error": payload})
                vid = (payload.get("id") or "").strip()
                watched = payload.get("watched", 0)
                completed = payload.get("completed")
                viewer = m0r
                verified = True
            else:
                vid = (data.get("id") or "").strip()
                watched = data.get("watched", 0)
                completed = data.get("completed")
                viewer = (data.get("uid") or "").strip()
            if not vid:
                return self._json(400, {"error": "id required"})
            return self._json(200, record_watch(vid, watched, completed,
                                                viewer, self._iph(), viewer_verified=verified))
        if path == "/api/cover":  # サムネのカット選択(所有者署名 or admin)
            cid = data.get("id")
            b64 = data.get("cover", "")
            ts = float(data.get("ts", 0) or 0)
            if not cid or not b64:
                return self._json(400, {"error": "id and cover required"})
            authed = False
            if data.get("token") and ADMIN_TOKEN and data["token"] == ADMIN_TOKEN:
                authed = True
            elif data.get("sig"):
                m0r, _ = verify_signed(data, "set.cover")
                if m0r and m0r == content_owner(cid):
                    authed = True
            if not authed:
                return self._json(403, {"error": "forbidden"})
            try:
                raw = base64.b64decode(b64.split(",", 1)[-1])
                if not raw:  # 空 = カット解除(ループに戻す)
                    clear_cover(cid)
                    return self._json(200, {"ok": True, "cleared": True})
                if len(raw) > 600 * 1024:
                    return self._json(413, {"error": "cover too large"})
                set_cover(cid, raw, ts)
                return self._json(200, {"ok": True, "cover": f"/cover/{cid}.jpg"})
            except Exception as e:
                return self._json(400, {"error": str(e)})
        if path == "/api/admin/ingest":
            if not ADMIN_TOKEN or data.get("token") != ADMIN_TOKEN:
                return self._json(403, {"error": "forbidden"})
            return self._json(200, self._ingest(data))
        return self._json(404, {"error": "not found"})

    def _ingest(self, data):
        cid = data.get("id") or ("m0v" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:13])
        conn = _db()
        conn.execute(
            "INSERT OR REPLACE INTO content(id,play_cid,title,tags,uploader,created_at,views,likes,hue,ar)"
            " VALUES(?,?,?,?,?,?,COALESCE((SELECT views FROM content WHERE id=?),0),"
            "COALESCE((SELECT likes FROM content WHERE id=?),0),?,?)",
            (cid, data["play_cid"], data.get("title", "untitled"), data.get("tags", ""),
             data.get("uploader", ""), int(data.get("created_at", time.time())), cid, cid,
             int(data.get("hue", random.randint(0, 359))), data.get("ar", "portrait")),
        )
        conn.commit()
        conn.close()
        return {"ok": True, "id": cid}

    # --- upload (署名検証 → ゲート → 予約) ---
    def _upload_init(self, data):
        m0r, payload = verify_signed(data, "upload.init")
        if not m0r:
            return self._json(400, {"error": payload})
        acc = ensure_account(m0r)
        dur = float(payload.get("duration") or 0)
        links = payload.get("links") or []
        ok, reason = gate_check_upload(acc, dur, links)
        if not ok:
            return self._json(403, {"error": reason, "gate": True})
        # 重複コンテンツ再発防止: 同一投稿者×同名(公開/審査中)の重複投稿を弾く。
        # reserved(=アップロード途中の再試行)や removed/rejected は対象外にして正当な再投稿は妨げない。
        _title = (payload.get("title") or "").strip()[:120]
        if _title:
            _conn = _db()
            _dup = _conn.execute(
                "SELECT id FROM content WHERE uploader=? AND status IN "
                "('approved','pending','pending_review','shadow') AND LOWER(TRIM(title))=? LIMIT 1",
                (m0r, _title.lower())).fetchone()
            _conn.close()
            if _dup:
                return self._json(409, {"error": "同じタイトルの投稿が既にあります。別のタイトルにしてください。",
                                        "dup_title": True})
        token = hashlib.sha1(f"{m0r}{time.time()}{random.random()}".encode()).hexdigest()[:20]
        cid = create_reservation(m0r, payload, token)
        return self._json(200, {"ok": True, "id": cid, "token": token})

    def _upload_media(self, cid, token):
        conn = _db()
        r = conn.execute("SELECT uploader,upload_token,status FROM content WHERE id=?", (cid,)).fetchone()
        conn.close()
        if not r or r["status"] != "reserved" or r["upload_token"] != token:
            return self._json(403, {"error": "invalid reservation"})
        ln = int(self.headers.get("Content-Length", "0") or "0")
        if ln <= 0 or ln > MAX_UPLOAD_BYTES:
            return self._json(413, {"error": f"ファイルサイズが上限（{MAX_UPLOAD_BYTES // (1024*1024)}MB）を超えています"})
        raw = self.rfile.read(ln)
        # 1) 変換(正規化): gateway で HLS へトランスコード
        try:
            play_cid = gateway_encode(raw, filename=f"{cid}.mp4")
        except Exception as e:
            return self._json(502, {"error": f"エンコード失敗（対応していない動画形式の可能性）: {e}"})
        # 2) 実尺・実解像度で検証(クライアント申告に依存しない)
        try:
            spec = probe_encoded(play_cid)
        except Exception:
            spec = {"duration": 0, "ar": "portrait", "w": 0, "h": 0}
        acc = ensure_account(r["uploader"])
        g = GATE[effective_tier(acc)]
        if spec["duration"] and spec["duration"] < MIN_DURATION:
            self._reject_reserved(cid, "too_short")
            return self._json(400, {"error": "動画が短すぎます（1秒以上必要）"})
        if spec["duration"] and spec["duration"] > g["max_dur"] + DUR_TOLERANCE:
            self._reject_reserved(cid, "over_duration")
            return self._json(403, {"gate": True,
                "error": f"実尺 {spec['duration']:.0f}s が上限（{g['max_dur']}s）を超えています"})
        # 3) status='pending'(AI審査待ち)へ。分類は mod_worker が非同期で処理。
        status = finalize_reservation(cid, token, play_cid, spec["duration"], spec["ar"])
        if not status:
            return self._json(409, {"error": "bind failed"})
        return self._json(200, {"ok": True, "id": cid, "play_cid": play_cid, "status": status,
                                "duration": spec["duration"], "ar": spec["ar"]})

    def _reject_reserved(self, cid, reason):
        conn = _db()
        conn.execute("UPDATE content SET status='rejected',upload_token='' WHERE id=?", (cid,))
        conn.execute("INSERT INTO moderation_log(target_type,target_id,model,score,labels,decision,reviewer,ts)"
                     " VALUES('content',?,'spec',0,'{}',?,'system',?)", (cid, "rejected:" + reason, int(time.time())))
        conn.commit()
        conn.close()

    # --- proxy impl ---
    def _proxy(self, cid, rest):
        rating, status = content_rating(cid)
        # ★admin(有効なX-Admin-Tokenヘッダ)は審査プレビューのため R18/未approved を配信可。
        is_admin = bool(ADMIN_TOKEN and self.headers.get("X-Admin-Token") == ADMIN_TOKEN)
        if rating == "r18" and not is_admin and not self._age_cookie_m0r():  # R18は年齢認証cookie必須
            return self._json(403, {"error": "age_verification_required", "adult": True})
        play_cid = resolve_play_cid(cid)
        if not play_cid and is_admin:   # pending/pending_review/rejected も審査のため配信(公開は404据置)
            play_cid = play_cid_any(cid)
        if not play_cid:
            return self._json(404, {"error": "not found"})
        is_playlist = rest.endswith(".m3u8")
        range_hdr = self.headers.get("Range")
        try:
            status, hdrs, body = _edge_fetch(play_cid, rest, None if is_playlist else range_hdr)
        except Exception:
            return self._json(502, {"error": "upstream"})
        hl = {k.lower(): v for k, v in hdrs.items()}  # CF は小文字ヘッダを返す
        if is_playlist:
            body = _rewrite_playlist(body, cid)
            ctype = "application/vnd.apple.mpegurl"
            extra = {"Cache-Control": "public,max-age=10"}
        else:
            ctype = hl.get("content-type", "application/octet-stream")
            extra = {"Cache-Control": "public,max-age=31536000,immutable",
                     "Accept-Ranges": "bytes"}
            cr = hl.get("content-range")
            if cr:
                extra["Content-Range"] = cr
            extra["Access-Control-Expose-Headers"] = "Content-Range,Content-Length,Accept-Ranges"
        # ノード識別ヘッダは一切転送しない(_send が最小限のヘッダのみ付与)
        self._send(status, body, ctype, extra)


class TS(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    _init_db()
    threading.Thread(target=_health_loop, daemon=True).start()
    threading.Thread(target=_points_loop, daemon=True).start()   # エンゲージ報酬の72h集計
    print(f"[morm-play] :{PORT} db={CATALOG_DB} edges={len(EDGES)}", flush=True)
    TS(("0.0.0.0", PORT), H).serve_forever()
