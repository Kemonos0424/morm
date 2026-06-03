#!/usr/bin/env python3
"""
MORM ダッシュボード ブランドアセット生成
docs/MORM_ASSET_SPEC.md の正本仕様に準拠。

方針:
- SVG（アイコン/ロゴ/イラスト）はコードで生成（§付記）。共通 <defs>（g-brand/g-tri/g-morm）と
  モチーフ M-1..M-4 を使い回して一貫性を担保。
- 群れ(swarm)要素を面積のあるアセットに必ず1つ（§2-6, §11）。
- トークン系のみアンバー g-morm を主役、それ以外は紫→青 g-brand（§2-3）。
- m0r の 0 は数字ゼロ、幾何サンセリフ Inter（§2-4）。
- PNG（hero/og）は別スクリプト関数で Gemini 生成 + 文字は PIL 合成。

実行:
    python scripts/generate_morm_assets.py --svg     # SVG 一式
    python scripts/generate_morm_assets.py --png     # ラスタ(Gemini)+favicon
    python scripts/generate_morm_assets.py --all
"""
import argparse
import math
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # morm-dashboard
ICONS = os.path.join(ROOT, "public", "icons")

# ---- §3 確定パレット ----
VIOLET = "#8b5cf6"
BLUE = "#3b82f6"
CYAN = "#00d2ff"
CYAN2 = "#22d3ee"
AMBER = "#fbbf24"
AMBER_DEEP = "#d97706"
GREEN = "#22c55e"
GREY = "#6b7280"
BG_INDIGO = "#0c0c1d"
TEXT = "#e2e8f0"

# ---- §3 共通グラデーション defs ----
DEFS = (
    '<defs>'
    '<linearGradient id="g-brand" x1="0" y1="0" x2="1" y2="1">'
    f'<stop offset="0%" stop-color="{VIOLET}"/><stop offset="100%" stop-color="{BLUE}"/>'
    '</linearGradient>'
    '<linearGradient id="g-tri" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0%" stop-color="#667eea"/><stop offset="45%" stop-color="#764ba2"/>'
    '<stop offset="100%" stop-color="#00d2ff"/>'
    '</linearGradient>'
    '<linearGradient id="g-morm" x1="0" y1="0" x2="1" y2="1">'
    f'<stop offset="0%" stop-color="{AMBER}"/><stop offset="100%" stop-color="{AMBER_DEEP}"/>'
    '</linearGradient>'
    '</defs>'
)

FONT = "Inter, Geist, system-ui, -apple-system, sans-serif"


def svg(w, h, body, defs=DEFS):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" fill="none">{defs}{body}</svg>'
    )


def write(name, content):
    p = os.path.join(ICONS, name)
    with open(p, "w") as f:
        f.write(content)
    print(f"  {name}  ({len(content)} B)")


# =====================================================================
# モチーフ・ヘルパー
# =====================================================================
def swarm_dots(cx, cy, count, spread, rmin=0.8, rmax=2.0, fill="url(#g-brand)",
               seed=7, op_base=0.7, density=1.7):
    """M-1/M-3: 中心ほど密、外周ほど疎な点群。SVG <circle> 群を返す。"""
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        a = rng.uniform(0, math.tau)
        rad = (rng.random() ** density) * spread
        x = cx + math.cos(a) * rad
        y = cy + math.sin(a) * rad
        r = rng.uniform(rmin, rmax)
        op = max(0.12, op_base * (1 - rad / spread) + rng.uniform(-0.1, 0.1))
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{fill}" opacity="{op:.2f}"/>')
    return "".join(out)


# =====================================================================
# 6-A ブランド根幹
# =====================================================================
def build_brand_root():
    print("[A] ブランド根幹")

    # --- morm-token.svg 48x48（§8 雛形ベース）---
    body = (
        '<g fill="url(#g-morm)" opacity="0.25">'
        + swarm_dots(24, 24, 7, 21, 1.0, 1.4, "url(#g-morm)", seed=3, op_base=0.5, density=2.2)
        + '</g>'
        '<circle cx="24" cy="24" r="20" fill="url(#g-morm)" opacity="0.15"/>'
        '<circle cx="24" cy="24" r="20" stroke="url(#g-morm)" stroke-width="2" fill="none"/>'
        '<circle cx="24" cy="24" r="16" stroke="url(#g-morm)" stroke-width="0.5" fill="none" opacity="0.35"/>'
        f'<text x="24" y="28.5" text-anchor="middle" font-family="{FONT}" '
        f'font-size="13" font-weight="700" letter-spacing="0.5" fill="url(#g-morm)">m0r</text>'
    )
    write("morm-token.svg", svg(48, 48, body))

    # --- morm-token-sm.svg 24x24（簡略・粒子省略）---
    body = (
        '<circle cx="12" cy="12" r="10" fill="url(#g-morm)" opacity="0.15"/>'
        '<circle cx="12" cy="12" r="10" stroke="url(#g-morm)" stroke-width="1.5" fill="none"/>'
        f'<text x="12" y="15" text-anchor="middle" font-family="{FONT}" '
        f'font-size="7" font-weight="700" fill="url(#g-morm)">m0r</text>'
    )
    write("morm-token-sm.svg", svg(24, 24, body))

    # --- logo.svg 40x40（M-1 群れ強化：3円三角 + 外周ドット）---
    core = (
        '<circle cx="12" cy="10" r="5" fill="url(#g-brand)" opacity="0.9"/>'
        '<circle cx="28" cy="10" r="5" fill="url(#g-brand)" opacity="0.9"/>'
        '<circle cx="20" cy="30" r="5" fill="url(#g-brand)" opacity="0.9"/>'
        '<line x1="12" y1="10" x2="28" y2="10" stroke="url(#g-brand)" stroke-width="1.5" opacity="0.6"/>'
        '<line x1="12" y1="10" x2="20" y2="30" stroke="url(#g-brand)" stroke-width="1.5" opacity="0.6"/>'
        '<line x1="28" y1="10" x2="20" y2="30" stroke="url(#g-brand)" stroke-width="1.5" opacity="0.6"/>'
    )
    dots = (
        '<g fill="url(#g-brand)">'
        '<circle cx="6" cy="6" r="1.3" opacity="0.7"/>'
        '<circle cx="34" cy="5" r="1.1" opacity="0.6"/>'
        '<circle cx="37" cy="22" r="1.4" opacity="0.7"/>'
        '<circle cx="5" cy="24" r="1.1" opacity="0.55"/>'
        '<circle cx="30" cy="36" r="1.2" opacity="0.6"/>'
        '<circle cx="10" cy="35" r="1.0" opacity="0.5"/>'
        '<circle cx="20" cy="3" r="0.9" opacity="0.45"/>'
        '<circle cx="3" cy="14" r="0.9" opacity="0.4"/>'
        '</g>'
    )
    write("logo.svg", svg(40, 40, dots + core))

    # --- logo-full.svg 200x40（マーク + MORM ワードマーク）---
    mark = (
        '<circle cx="12" cy="12" r="4" fill="url(#g-brand)"/>'
        '<circle cx="24" cy="12" r="4" fill="url(#g-brand)"/>'
        '<circle cx="18" cy="26" r="4" fill="url(#g-brand)"/>'
        '<line x1="12" y1="12" x2="24" y2="12" stroke="url(#g-brand)" stroke-width="1.2" opacity="0.5"/>'
        '<line x1="12" y1="12" x2="18" y2="26" stroke="url(#g-brand)" stroke-width="1.2" opacity="0.5"/>'
        '<line x1="24" y1="12" x2="18" y2="26" stroke="url(#g-brand)" stroke-width="1.2" opacity="0.5"/>'
        '<g fill="url(#g-brand)">'
        '<circle cx="4" cy="6" r="1" opacity="0.6"/><circle cx="32" cy="6" r="0.9" opacity="0.5"/>'
        '<circle cx="6" cy="30" r="0.9" opacity="0.5"/><circle cx="30" cy="28" r="1" opacity="0.55"/>'
        '</g>'
    )
    text = (
        f'<text x="44" y="27" font-family="{FONT}" font-size="20" font-weight="800" '
        f'letter-spacing="1.5" fill="url(#g-tri)">MORM</text>'
        f'<text x="112" y="27" font-family="{FONT}" font-size="9" font-weight="500" '
        f'letter-spacing="0.5" fill="{TEXT}" opacity="0.45">Node Network</text>'
    )
    write("logo-full.svg", svg(200, 40, mark + text))


# =====================================================================
# 6-B 機能アイコン
# =====================================================================
def build_functional():
    print("[B] 機能アイコン")

    body = (
        '<circle cx="16" cy="16" r="14" fill="#475569" opacity="0.10"/>'
        '<circle cx="16" cy="16" r="10" fill="#475569" opacity="0.18"/>'
        '<circle cx="16" cy="16" r="6" fill="#64748b"/>'
        '<circle cx="16" cy="16" r="6" stroke="#94a3b8" stroke-width="0.6" opacity="0.5"/>'
    )
    write("node-offline.svg", svg(32, 32, body))

    body = (
        '<circle cx="6" cy="6" r="5.5" fill="#64748b" opacity="0.18"/>'
        '<circle cx="6" cy="6" r="4" fill="#64748b" opacity="0.6"/>'
    )
    write("status-offline.svg", svg(12, 12, body))

    body = (
        '<circle cx="6" cy="6" r="5.5" fill="#22c55e" opacity="0.22"/>'
        '<circle cx="6" cy="6" r="4" fill="#22c55e"/>'
    )
    write("status-online.svg", svg(12, 12, body))

    body = (
        '<circle cx="16" cy="16" r="14" fill="#22c55e" opacity="0.08"/>'
        '<circle cx="16" cy="16" r="10" fill="#22c55e" opacity="0.20"/>'
        '<circle cx="16" cy="16" r="6" fill="#22c55e"/>'
    )
    write("node-online.svg", svg(32, 32, body))

    body = (
        '<rect x="6" y="12" width="34" height="26" rx="5" stroke="url(#g-brand)" stroke-width="2" fill="none"/>'
        '<path d="M6 19h34" stroke="url(#g-brand)" stroke-width="1.5" opacity="0.7"/>'
        '<path d="M40 24h3a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-3z" fill="url(#g-brand)" opacity="0.85"/>'
        '<circle cx="30" cy="28" r="5" fill="url(#g-morm)" opacity="0.9"/>'
        f'<text x="30" y="30.5" text-anchor="middle" font-family="{FONT}" font-size="4.4" '
        f'font-weight="700" fill="#1a1205">m0r</text>'
        '<g fill="url(#g-morm)" opacity="0.5">'
        '<circle cx="14" cy="28" r="1.1"/><circle cx="19" cy="31" r="0.9"/><circle cx="16" cy="24" r="0.8"/>'
        '</g>'
    )
    write("wallet-icon.svg", svg(48, 48, body))

    body = (
        '<path d="M16 8h16v12c0 6-4 10-8 10s-8-4-8-10V8z" stroke="url(#g-tri)" stroke-width="2" '
        'fill="url(#g-tri)" fill-opacity="0.16"/>'
        '<path d="M16 12H10c0 4 2 7 6 8" stroke="url(#g-tri)" stroke-width="1.5" fill="none"/>'
        '<path d="M32 12H38c0 4-2 7-6 8" stroke="url(#g-tri)" stroke-width="1.5" fill="none"/>'
        '<line x1="20" y1="36" x2="28" y2="36" stroke="url(#g-tri)" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="24" y1="30" x2="24" y2="36" stroke="url(#g-tri)" stroke-width="2"/>'
        '<g fill="url(#g-tri)">'
        '<circle cx="12" cy="6" r="1.2" opacity="0.6"/><circle cx="37" cy="7" r="1.1" opacity="0.55"/>'
        '<circle cx="24" cy="4" r="1.3" opacity="0.7"/><circle cx="40" cy="16" r="1" opacity="0.45"/>'
        '<circle cx="8" cy="16" r="1" opacity="0.45"/>'
        '</g>'
    )
    write("score-trophy.svg", svg(48, 48, body))

    edges = (
        '<g stroke="url(#g-brand)" stroke-width="1" opacity="0.35">'
        '<line x1="24" y1="12" x2="12" y2="20"/><line x1="24" y1="12" x2="36" y2="20"/>'
        '<line x1="12" y1="28" x2="6" y2="37"/><line x1="12" y1="28" x2="18" y2="37"/>'
        '<line x1="36" y1="28" x2="30" y2="37"/><line x1="36" y1="28" x2="42" y2="37"/>'
        '</g>'
    )
    nodes = (
        '<circle cx="24" cy="8" r="9" fill="url(#g-brand)" opacity="0.12"/>'
        '<circle cx="24" cy="8" r="6" fill="url(#g-brand)" opacity="0.30"/>'
        '<circle cx="24" cy="8" r="4" fill="url(#g-brand)"/>'
        '<circle cx="12" cy="24" r="4" fill="url(#g-brand)" opacity="0.7"/>'
        '<circle cx="36" cy="24" r="4" fill="url(#g-brand)" opacity="0.7"/>'
        '<g fill="url(#g-brand)" opacity="0.5">'
        '<circle cx="6" cy="40" r="3"/><circle cx="18" cy="40" r="3"/>'
        '<circle cx="30" cy="40" r="3"/><circle cx="42" cy="40" r="3"/>'
        '</g>'
    )
    write("merkle-icon.svg", svg(48, 48, edges + nodes))


# =====================================================================
# 6-C イラスト・装飾
# =====================================================================
def build_illustrations():
    print("[C] イラスト・装飾")

    # network-illustration 400x300（M-1 大規模群れ + cyan データ流）
    rng = random.Random(42)
    pts = []
    for _ in range(46):
        a = rng.uniform(0, math.tau)
        rad = (rng.random() ** 1.8) * 150
        x = 200 + math.cos(a) * rad * 1.25
        y = 150 + math.sin(a) * rad
        pts.append((x, y, rad))
    lines = []
    for i, (x1, y1, _) in enumerate(pts):
        for x2, y2, _ in pts[i + 1:]:
            d = math.hypot(x1 - x2, y1 - y2)
            if d < 42:
                op = max(0.05, 0.28 * (1 - d / 42))
                col = "#00d2ff" if rng.random() < 0.25 else "url(#g-brand)"
                lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                             f'stroke="{col}" stroke-width="0.8" opacity="{op:.2f}"/>')
    nodes = []
    for x, y, rad in pts:
        r = max(1.2, 4.2 * (1 - rad / 190) + rng.uniform(0, 1.2))
        op = max(0.25, 0.95 * (1 - rad / 220))
        nodes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="url(#g-brand)" opacity="{op:.2f}"/>')
    center = (
        '<circle cx="200" cy="150" r="22" fill="url(#g-morm)" opacity="0.16"/>'
        '<circle cx="200" cy="150" r="22" stroke="url(#g-morm)" stroke-width="1.5" fill="none" opacity="0.8"/>'
        f'<text x="200" y="155" text-anchor="middle" font-family="{FONT}" font-size="13" '
        f'font-weight="700" fill="url(#g-morm)">m0r</text>'
    )
    write("network-illustration.svg", svg(400, 300, "".join(lines) + "".join(nodes) + center))

    # network-map-bg 400x300（地図状の低彩度点群 + 微結線）
    rng = random.Random(11)
    mpts = [(rng.uniform(10, 390), rng.uniform(10, 290)) for _ in range(70)]
    mlines = []
    for i, (x1, y1) in enumerate(mpts):
        for x2, y2 in mpts[i + 1:]:
            d = math.hypot(x1 - x2, y1 - y2)
            if d < 46 and rng.random() < 0.6:
                mlines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                              f'stroke="{VIOLET}" stroke-width="0.5" opacity="0.12"/>')
    mdots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rng.uniform(0.8,1.8):.2f}" '
        f'fill="{BLUE if rng.random()<0.5 else VIOLET}" opacity="{rng.uniform(0.12,0.4):.2f}"/>'
        for x, y in mpts
    )
    write("network-map-bg.svg", svg(400, 300, "".join(mlines) + mdots))

    # claim-illustration 300x200（m0r コインが群れから1つ手元へ流れる）
    swarm = '<g>' + swarm_dots(70, 70, 26, 56, 0.8, 2.2, "url(#g-morm)", seed=5, op_base=0.55, density=2.0) + '</g>'
    flow = (
        '<g stroke="url(#g-morm)" stroke-width="1.2" stroke-linecap="round" opacity="0.5" fill="none">'
        '<path d="M92 84 C140 110, 180 130, 196 150"/>'
        '<path d="M104 70 C150 96, 188 120, 200 144" opacity="0.3"/>'
        '</g>'
        '<g fill="#00d2ff" opacity="0.6">'
        '<circle cx="130" cy="104" r="1.6"/><circle cx="158" cy="122" r="1.4"/><circle cx="178" cy="136" r="1.2"/>'
        '</g>'
    )
    coin = (
        '<circle cx="206" cy="150" r="26" fill="url(#g-morm)" opacity="0.16"/>'
        '<circle cx="206" cy="150" r="26" stroke="url(#g-morm)" stroke-width="2" fill="none"/>'
        '<circle cx="206" cy="150" r="20" stroke="url(#g-morm)" stroke-width="0.6" fill="none" opacity="0.4"/>'
        f'<text x="206" y="156" text-anchor="middle" font-family="{FONT}" font-size="15" '
        f'font-weight="700" fill="url(#g-morm)">m0r</text>'
    )
    hand = (
        '<path d="M150 196c-2-16 6-26 18-30l28-8c8-2 14 2 14 12" stroke="url(#g-brand)" '
        'stroke-width="2" fill="none" opacity="0.45" stroke-linecap="round"/>'
    )
    write("claim-illustration.svg", svg(300, 200, swarm + hand + flow + coin))

    # empty-state 200x200（霧に消える疎な群れ）
    rng = random.Random(9)
    dots = []
    for _ in range(22):
        a = rng.uniform(0, math.tau)
        rad = (rng.random() ** 0.8) * 78
        x = 100 + math.cos(a) * rad
        y = 78 + math.sin(a) * rad * 0.8
        r = rng.uniform(0.8, 2.0)
        op = max(0.08, 0.5 * (1 - rad / 90))
        col = VIOLET if rng.random() < 0.4 else GREY
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{col}" opacity="{op:.2f}"/>')
    body = (
        '<g stroke="#8b5cf6" stroke-width="0.6" opacity="0.12">'
        '<line x1="86" y1="70" x2="112" y2="64"/><line x1="112" y1="64" x2="120" y2="88"/>'
        '<line x1="86" y1="70" x2="92" y2="92"/></g>'
        + "".join(dots)
        + f'<text x="100" y="150" text-anchor="middle" font-family="{FONT}" font-size="12" '
        f'font-weight="500" fill="{GREY}" opacity="0.5">No Data</text>'
    )
    write("empty-state.svg", svg(200, 200, body))


def audit_tasks():
    print("[B+] task-* 配色監査（g-brand 連続性）")
    import glob
    for p in sorted(glob.glob(os.path.join(ICONS, "task-*.svg"))):
        s = open(p).read()
        has_brand = ("#8b5cf6" in s and "#3b82f6" in s)
        print(f"  {'OK ' if has_brand else 'NG!'} {os.path.basename(p)}")


def build_svgs():
    build_brand_root()
    build_functional()
    build_illustrations()
    audit_tasks()
    print("SVG 完了。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", action="store_true")
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.svg or args.all or not args.png:
        build_svgs()
    if args.png or args.all:
        import generate_morm_png
        generate_morm_png.run()
